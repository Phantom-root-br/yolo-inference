#!/usr/bin/env python3
"""Treino simples de modelos YOLO a partir de um dataset no formato Ultralytics.

A CLI mantém o treino separado do pipeline de inferência e evita caminhos
específicos do HARPia no código. O Ultralytics é importado apenas quando o
treino realmente começa, permitindo testar a CLI sem carregar PyTorch.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


DEFAULT_MODEL = "yolo11n.pt"
DEFAULT_EPOCHS = 50
DEFAULT_IMAGE_SIZE = 640
DEFAULT_BATCH = 8
DEFAULT_DEVICE = "cpu"
DEFAULT_WORKERS = 2
DEFAULT_PROJECT = "runs/train"
DEFAULT_NAME = "harpia-yolo"
DEFAULT_PATIENCE = 20
DEFAULT_SEED = 42


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Treina um modelo YOLO usando um data.yaml no formato Ultralytics."
    )
    parser.add_argument("data", type=Path, help="Caminho para o data.yaml do dataset.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Peso/modelo inicial (padrão: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=DEFAULT_EPOCHS,
        help=f"Número de épocas (padrão: {DEFAULT_EPOCHS}).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=DEFAULT_IMAGE_SIZE,
        help=f"Tamanho de entrada (padrão: {DEFAULT_IMAGE_SIZE}).",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=DEFAULT_BATCH,
        help=f"Batch size; use -1 para auto (padrão: {DEFAULT_BATCH}).",
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help="Dispositivo: cpu, 0, 1, ... (padrão: cpu).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Workers do dataloader (padrão: {DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        help=f"Diretório base dos resultados (padrão: {DEFAULT_PROJECT}).",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help=f"Nome da execução (padrão: {DEFAULT_NAME}).",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=DEFAULT_PATIENCE,
        help=f"Early stopping patience (padrão: {DEFAULT_PATIENCE}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Seed para reprodutibilidade (padrão: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Mantém imagens em cache quando houver memória suficiente.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Solicita retomada de um treino interrompido pelo Ultralytics.",
    )
    parser.add_argument(
        "--exist-ok",
        action="store_true",
        help="Permite reutilizar o diretório project/name existente.",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if not args.data.is_file():
        raise ValueError(f"data.yaml não encontrado: {args.data}")
    if args.data.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("O dataset deve ser informado por um arquivo .yaml ou .yml.")
    if args.epochs <= 0:
        raise ValueError("--epochs deve ser maior que zero.")
    if args.imgsz <= 0:
        raise ValueError("--imgsz deve ser maior que zero.")
    if args.batch == 0 or args.batch < -1:
        raise ValueError("--batch deve ser -1 (auto) ou um inteiro positivo.")
    if args.workers < 0:
        raise ValueError("--workers não pode ser negativo.")
    if args.patience < 0:
        raise ValueError("--patience não pode ser negativo.")
    if args.seed < 0:
        raise ValueError("--seed não pode ser negativo.")


def load_yolo():
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Ultralytics não encontrado. Execute './scripts/setup.sh' ou "
            "'pip install -r requirements.txt'."
        ) from exc
    return YOLO


def run_training(args: argparse.Namespace) -> Path:
    validate_args(args)
    YOLO = load_yolo()

    data_path = args.data.resolve()

    print("=" * 64)
    print(" YOLO Dataset Training | HARPia")
    print("=" * 64)
    print(f"Dataset : {data_path}")
    print(f"Modelo  : {args.model}")
    print(f"Device  : {args.device}")
    print(f"Epochs  : {args.epochs}")
    print(f"imgsz   : {args.imgsz}")
    print(f"Batch   : {args.batch}")
    print(f"Workers : {args.workers}")
    print(f"Saída   : {args.project}/{args.name}")
    print()

    model = YOLO(args.model)
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=args.project,
        name=args.name,
        patience=args.patience,
        seed=args.seed,
        cache=args.cache,
        resume=args.resume,
        exist_ok=args.exist_ok,
        plots=True,
        verbose=True,
    )

    trainer = getattr(model, "trainer", None)
    save_dir = Path(getattr(trainer, "save_dir", Path(args.project) / args.name))
    best = save_dir / "weights" / "best.pt"
    last = save_dir / "weights" / "last.pt"

    print()
    print("=" * 64)
    print(" TREINO FINALIZADO")
    print("=" * 64)
    print(f"Resultados : {save_dir}")
    print(f"best.pt    : {best}")
    print(f"last.pt    : {last}")

    return save_dir


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        run_training(args)
    except (ValueError, RuntimeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
