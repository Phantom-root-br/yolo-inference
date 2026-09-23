#!/usr/bin/env python3
"""Monta e valida um dataset YOLO Detection a partir de dados brutos.

Estrutura de entrada recomendada:

raw/
├── images/
│   ├── mission_001/
│   │   ├── frame_0001.jpg
│   │   └── frame_0002.jpg
│   └── mission_002/
│       └── frame_0001.jpg
└── labels/
    ├── mission_001/
    │   ├── frame_0001.txt
    │   └── frame_0002.txt
    └── mission_002/
        └── frame_0001.txt

O primeiro diretório abaixo de images/ é tratado como grupo. Todos os frames do
mesmo grupo vão para o mesmo split, reduzindo leakage entre train/val/test.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_TRAIN = 0.70
DEFAULT_VAL = 0.20
DEFAULT_TEST = 0.10
DEFAULT_SEED = 42


@dataclass(frozen=True)
class Sample:
    image: Path
    label: Path
    relative_image: Path
    relative_label: Path
    group: str
    class_counts: Counter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Valida imagens/anotações YOLO e monta um dataset com split por "
            "missão/sequência para reduzir leakage."
        )
    )
    parser.add_argument("source", type=Path, help="Diretório contendo images/ e labels/.")
    parser.add_argument("output", type=Path, help="Diretório do dataset final.")

    classes = parser.add_mutually_exclusive_group(required=True)
    classes.add_argument(
        "--classes",
        help="Classes separadas por vírgula. Ex.: platform,takeoff",
    )
    classes.add_argument(
        "--classes-file",
        type=Path,
        help="Arquivo texto com uma classe por linha.",
    )

    parser.add_argument("--train", type=float, default=DEFAULT_TRAIN, help="Fração de treino.")
    parser.add_argument("--val", type=float, default=DEFAULT_VAL, help="Fração de validação.")
    parser.add_argument("--test", type=float, default=DEFAULT_TEST, help="Fração de teste.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed do split.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Apaga o diretório de saída existente antes de montar o dataset.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida e calcula o split sem copiar arquivos.",
    )
    return parser


def load_classes(args: argparse.Namespace) -> list[str]:
    if args.classes:
        names = [item.strip() for item in args.classes.split(",") if item.strip()]
    else:
        if not args.classes_file.is_file():
            raise ValueError(f"Arquivo de classes não encontrado: {args.classes_file}")
        names = [
            line.strip()
            for line in args.classes_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    if not names:
        raise ValueError("Nenhuma classe foi informada.")
    if len(names) != len(set(names)):
        raise ValueError("Existem nomes de classe duplicados.")
    return names


def validate_ratios(train: float, val: float, test: float) -> None:
    ratios = (train, val, test)
    if any(value < 0 for value in ratios):
        raise ValueError("As frações train/val/test não podem ser negativas.")
    if not math.isclose(sum(ratios), 1.0, abs_tol=1e-6):
        raise ValueError("As frações train + val + test devem somar 1.0.")
    if train <= 0:
        raise ValueError("O split de treino deve ser maior que zero.")


def group_for(relative_image: Path) -> str:
    parent_parts = relative_image.parent.parts
    if parent_parts:
        return parent_parts[0]
    # Se não houver diretórios de missão/sequência, cada imagem vira seu próprio
    # grupo. Isso permite o split, mas não protege contra frames correlacionados.
    return relative_image.stem


def parse_label_file(path: Path, class_count: int) -> Counter:
    counts: Counter = Counter()
    lines = path.read_text(encoding="utf-8").splitlines()

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 5:
            raise ValueError(
                f"{path}:{line_number}: esperado '<class_id> <x> <y> <w> <h>', "
                f"recebido {len(parts)} campos."
            )

        try:
            class_id = int(parts[0])
            x, y, width, height = (float(value) for value in parts[1:])
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: valor inválido na anotação.") from exc

        if not 0 <= class_id < class_count:
            raise ValueError(
                f"{path}:{line_number}: class_id={class_id} fora do intervalo "
                f"0..{class_count - 1}."
            )

        values = (x, y, width, height)
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"{path}:{line_number}: coordenada não finita.")
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(f"{path}:{line_number}: centro x/y deve estar entre 0 e 1.")
        if not (0.0 < width <= 1.0 and 0.0 < height <= 1.0):
            raise ValueError(f"{path}:{line_number}: largura/altura deve estar em (0, 1].")

        # Também detecta caixas que ultrapassam claramente os limites da imagem.
        eps = 1e-6
        if x - width / 2 < -eps or x + width / 2 > 1.0 + eps:
            raise ValueError(f"{path}:{line_number}: bounding box ultrapassa o eixo X.")
        if y - height / 2 < -eps or y + height / 2 > 1.0 + eps:
            raise ValueError(f"{path}:{line_number}: bounding box ultrapassa o eixo Y.")

        counts[class_id] += 1

    # Arquivos vazios são aceitos: representam imagens negativas, sem objetos.
    return counts


def discover_samples(source: Path, class_count: int) -> tuple[list[Sample], list[Path]]:
    images_root = source / "images"
    labels_root = source / "labels"

    if not images_root.is_dir():
        raise ValueError(f"Diretório não encontrado: {images_root}")
    if not labels_root.is_dir():
        raise ValueError(f"Diretório não encontrado: {labels_root}")

    image_paths = sorted(
        path for path in images_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not image_paths:
        raise ValueError(f"Nenhuma imagem encontrada em: {images_root}")

    samples: list[Sample] = []
    expected_labels: set[Path] = set()

    for image_path in image_paths:
        relative_image = image_path.relative_to(images_root)
        relative_label = relative_image.with_suffix(".txt")
        label_path = labels_root / relative_label
        expected_labels.add(label_path.resolve())

        if not label_path.is_file():
            raise ValueError(f"Label ausente para {image_path}: esperado {label_path}")

        class_counts = parse_label_file(label_path, class_count)
        samples.append(
            Sample(
                image=image_path,
                label=label_path,
                relative_image=relative_image,
                relative_label=relative_label,
                group=group_for(relative_image),
                class_counts=class_counts,
            )
        )

    orphan_labels = sorted(
        path
        for path in labels_root.rglob("*.txt")
        if path.resolve() not in expected_labels
    )
    return samples, orphan_labels


def split_groups(
    samples: Sequence[Sample],
    ratios: dict[str, float],
    seed: int,
) -> dict[str, list[Sample]]:
    grouped: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.group].append(sample)

    active_splits = [name for name in ("train", "val", "test") if ratios[name] > 0]
    if len(grouped) < len(active_splits):
        raise ValueError(
            f"Há apenas {len(grouped)} grupo(s), mas {len(active_splits)} splits ativos. "
            "Organize os dados em mais missões/sequências ou desative algum split."
        )

    rng = random.Random(seed)
    group_items = list(grouped.items())
    rng.shuffle(group_items)
    # Grupos grandes primeiro; o shuffle anterior randomiza empates de tamanho.
    group_items.sort(key=lambda item: len(item[1]), reverse=True)

    total_samples = len(samples)
    targets = {name: total_samples * ratios[name] for name in active_splits}
    assigned_counts = {name: 0 for name in active_splits}
    assignments: dict[str, list[Sample]] = {"train": [], "val": [], "test": []}

    # Garante pelo menos um grupo em cada split ativo.
    split_order = sorted(active_splits, key=lambda name: ratios[name], reverse=True)
    for split_name, (_, group_samples) in zip(split_order, group_items):
        assignments[split_name].extend(group_samples)
        assigned_counts[split_name] += len(group_samples)

    for _, group_samples in group_items[len(split_order):]:
        def deficit(split_name: str) -> float:
            target = targets[split_name]
            return (target - assigned_counts[split_name]) / max(target, 1.0)

        split_name = max(active_splits, key=deficit)
        assignments[split_name].extend(group_samples)
        assigned_counts[split_name] += len(group_samples)

    for split_name in assignments:
        assignments[split_name].sort(key=lambda sample: sample.relative_image.as_posix())

    return assignments


def prepare_output(output: Path, overwrite: bool) -> None:
    if output.exists():
        if not overwrite:
            raise ValueError(
                f"Diretório de saída já existe: {output}. Use --overwrite se quiser recriá-lo."
            )
        if output.resolve() == Path("/"):
            raise ValueError("Recusando apagar '/'.")
        shutil.rmtree(output)

    for split in ("train", "val", "test"):
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)


def destination_name(sample: Sample) -> str:
    # Prefixar o grupo evita colisões entre frame_0001.jpg de missões diferentes.
    safe_group = sample.group.replace("/", "_").replace("\\", "_")
    return f"{safe_group}__{sample.relative_image.name}"


def copy_dataset(assignments: dict[str, list[Sample]], output: Path) -> None:
    for split_name, samples in assignments.items():
        for sample in samples:
            image_name = destination_name(sample)
            label_name = Path(image_name).with_suffix(".txt").name
            shutil.copy2(sample.image, output / "images" / split_name / image_name)
            shutil.copy2(sample.label, output / "labels" / split_name / label_name)


def write_data_yaml(output: Path, classes: Sequence[str]) -> None:
    lines = [
        f"path: {json.dumps(str(output.resolve()), ensure_ascii=False)}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        "names:",
    ]
    for class_id, class_name in enumerate(classes):
        lines.append(f"  {class_id}: {json.dumps(class_name, ensure_ascii=False)}")
    (output / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_metadata(assignments: dict[str, list[Sample]], output: Path) -> None:
    with (output / "metadata.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["split", "group", "source_image", "source_label", "dataset_image"])
        for split_name, samples in assignments.items():
            for sample in samples:
                writer.writerow(
                    [
                        split_name,
                        sample.group,
                        str(sample.image),
                        str(sample.label),
                        destination_name(sample),
                    ]
                )


def print_summary(
    assignments: dict[str, list[Sample]],
    classes: Sequence[str],
    orphan_labels: Sequence[Path],
) -> None:
    print("=" * 68)
    print(" YOLO Dataset Builder | HARPia")
    print("=" * 68)

    total_images = sum(len(samples) for samples in assignments.values())
    all_groups = {sample.group for samples in assignments.values() for sample in samples}
    print(f"Imagens válidas : {total_images}")
    print(f"Grupos          : {len(all_groups)}")
    print(f"Classes         : {len(classes)}")
    print()

    for split_name in ("train", "val", "test"):
        samples = assignments[split_name]
        groups = sorted({sample.group for sample in samples})
        object_counts: Counter = Counter()
        negatives = 0
        for sample in samples:
            object_counts.update(sample.class_counts)
            if not sample.class_counts:
                negatives += 1

        pct = (len(samples) / total_images * 100.0) if total_images else 0.0
        print(f"{split_name.upper():5s}: {len(samples):4d} imagens ({pct:5.1f}%) | {len(groups):3d} grupo(s)")
        print(f"       grupos: {', '.join(groups)}")
        print(f"       negativas: {negatives}")
        for class_id, class_name in enumerate(classes):
            print(f"       classe {class_id:2d} {class_name}: {object_counts[class_id]} objeto(s)")
        print()

    if orphan_labels:
        print(f"AVISO: {len(orphan_labels)} label(s) sem imagem correspondente foram ignorados.")
        for path in orphan_labels[:10]:
            print(f"  - {path}")
        if len(orphan_labels) > 10:
            print(f"  ... e mais {len(orphan_labels) - 10}")
        print()


def run(args: argparse.Namespace) -> None:
    source = args.source.resolve()
    output = args.output.resolve()

    if source == output:
        raise ValueError("Source e output não podem ser o mesmo diretório.")
    if not source.is_dir():
        raise ValueError(f"Diretório source não encontrado: {source}")

    classes = load_classes(args)
    validate_ratios(args.train, args.val, args.test)
    samples, orphan_labels = discover_samples(source, len(classes))
    assignments = split_groups(
        samples,
        {"train": args.train, "val": args.val, "test": args.test},
        args.seed,
    )

    print_summary(assignments, classes, orphan_labels)

    if args.dry_run:
        print("DRY-RUN: nenhum arquivo foi copiado.")
        return

    prepare_output(output, args.overwrite)
    copy_dataset(assignments, output)
    write_data_yaml(output, classes)
    write_metadata(assignments, output)

    print(f"Dataset criado em : {output}")
    print(f"Config YOLO        : {output / 'data.yaml'}")
    print(f"Metadados do split : {output / 'metadata.csv'}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except ValueError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
