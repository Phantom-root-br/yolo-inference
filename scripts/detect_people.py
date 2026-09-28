#!/usr/bin/env python3
"""
Detecção de pessoas em vídeo com YOLO para o projeto HARPia.

Pipeline:
    vídeo -> OpenCV -> frame -> YOLO -> person -> bounding boxes
          -> vídeo anotado + métricas JSON + frames de exemplo

A inferência é offline. O vídeo de saída preserva o FPS do vídeo original,
independentemente da velocidade de processamento YOLO.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Any

os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")

DEFAULT_MODEL = "yolo11n.pt"
DEFAULT_IMGSZ = 640
DEFAULT_CONF = 0.25
DEFAULT_DEVICE = "cpu"
DEFAULT_EXAMPLES = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detecta exclusivamente pessoas em um vídeo usando YOLO."
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Vídeo de entrada.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Vídeo MP4 anotado de saída.",
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Modelo YOLO (padrão: {DEFAULT_MODEL}).",
    )

    parser.add_argument(
        "--imgsz",
        type=int,
        default=DEFAULT_IMGSZ,
        help=f"Tamanho da entrada YOLO (padrão: {DEFAULT_IMGSZ}).",
    )

    parser.add_argument(
        "--conf",
        type=float,
        default=DEFAULT_CONF,
        help=f"Confiança mínima (padrão: {DEFAULT_CONF}).",
    )

    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help=f"Dispositivo: cpu, 0, 1... (padrão: {DEFAULT_DEVICE}).",
    )

    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Limita o número de frames. Útil para testes.",
    )

    parser.add_argument(
        "--metrics",
        "--save-json",
        dest="metrics_path",
        type=Path,
        default=None,
        help="Caminho do JSON de métricas.",
    )

    parser.add_argument(
        "--examples",
        type=int,
        default=DEFAULT_EXAMPLES,
        help="Quantidade de frames representativos a salvar. Use 0 para desativar.",
    )

    parser.add_argument(
        "--examples-dir",
        type=Path,
        default=Path("results/examples"),
        help="Diretório para frames de exemplo.",
    )

    parser.add_argument(
        "--progress-every",
        type=int,
        default=30,
        help="Exibe progresso a cada N frames.",
    )

    return parser


def validate_args(args: argparse.Namespace) -> None:
    if not args.input.is_file():
        raise ValueError(f"Vídeo não encontrado: {args.input}")

    if not 0.0 <= args.conf <= 1.0:
        raise ValueError("--conf deve estar entre 0 e 1.")

    if args.imgsz <= 0:
        raise ValueError("--imgsz deve ser maior que zero.")

    if args.max_frames is not None and args.max_frames <= 0:
        raise ValueError("--max-frames deve ser maior que zero.")

    if args.examples < 0:
        raise ValueError("--examples não pode ser negativo.")

    if args.progress_every <= 0:
        raise ValueError("--progress-every deve ser maior que zero.")


def load_dependencies():
    try:
        import cv2  # type: ignore
        import torch  # type: ignore
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Dependências ausentes. Use /root/yolo_venv/bin/python."
        ) from exc

    # O HARPia usa um Intel i3-3217U antigo. O wheel CPU do PyTorch
    # contém suporte a NNPACK, mas esse processador não suporta o
    # backend necessário. Desabilitamos NNPACK explicitamente para
    # evitar centenas de warnings "Unsupported hardware".
    #
    # Isso NÃO desabilita a inferência em CPU e não tem relação
    # com CUDA/NVIDIA.
    if hasattr(torch.backends, "nnpack"):
        torch.backends.nnpack.set_flags(False)

    return cv2, YOLO


def find_person_class_id(names: Any) -> int:
    """
    Descobre programaticamente o ID da classe 'person'.

    Evita espalhar o número mágico da classe COCO pelo código.
    """
    if isinstance(names, dict):
        items = names.items()
    else:
        items = enumerate(names)

    matches = [
        int(class_id)
        for class_id, class_name in items
        if str(class_name).strip().lower() == "person"
    ]

    if not matches:
        raise RuntimeError(
            "O modelo carregado não possui uma classe chamada 'person'."
        )

    return matches[0]


def default_metrics_path(model_name: str) -> Path:
    model_stem = Path(model_name).stem
    return Path("results") / f"{model_stem}_metrics.json"


def model_size_mb(model_name: str) -> float | None:
    path = Path(model_name)

    if not path.is_file():
        return None

    return path.stat().st_size / (1024 * 1024)


def draw_detection(
    cv2,
    frame,
    bbox: list[float],
    confidence: float,
) -> None:
    x1, y1, x2, y2 = [int(round(value)) for value in bbox]

    label = f"person {confidence:.2f}"

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2,
    )

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.55
    thickness = 1

    (text_width, text_height), baseline = cv2.getTextSize(
        label,
        font,
        font_scale,
        thickness,
    )

    label_top = max(0, y1 - text_height - baseline - 6)

    cv2.rectangle(
        frame,
        (x1, label_top),
        (x1 + text_width + 6, y1),
        (0, 255, 0),
        -1,
    )

    cv2.putText(
        frame,
        label,
        (x1 + 3, max(text_height + 2, y1 - baseline - 3)),
        font,
        font_scale,
        (0, 0, 0),
        thickness,
        cv2.LINE_AA,
    )


def save_examples(
    cv2,
    examples_heap: list,
    examples_dir: Path,
) -> list[str]:
    if not examples_heap:
        return []

    examples_dir.mkdir(parents=True, exist_ok=True)

    saved = []

    # Ordena cronologicamente para facilitar a leitura.
    selected = sorted(
        examples_heap,
        key=lambda item: item[2],
    )

    for _, _, frame_index, annotated_frame in selected:
        path = examples_dir / f"frame_{frame_index:06d}.jpg"

        if not cv2.imwrite(str(path), annotated_frame):
            raise RuntimeError(
                f"Não foi possível salvar frame de exemplo: {path}"
            )

        saved.append(str(path))

    return saved


def run(args: argparse.Namespace) -> dict:
    validate_args(args)

    cv2, YOLO = load_dependencies()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    metrics_path = (
        args.metrics_path
        if args.metrics_path is not None
        else default_metrics_path(args.model)
    )

    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print(" HARPia | YOLO Person Detection")
    print("=" * 64)
    print(f"Modelo          : {args.model}")
    print(f"Entrada         : {args.input}")
    print(f"Saída           : {args.output}")
    print(f"Device          : {args.device}")
    print(f"imgsz           : {args.imgsz}")
    print(f"conf            : {args.conf}")
    print(f"max_frames      : {args.max_frames}")
    print()

    print("Carregando modelo...")

    model_load_start = time.perf_counter()
    model = YOLO(args.model)
    model_load_seconds = time.perf_counter() - model_load_start

    person_class_id = find_person_class_id(model.names)

    print(f"Modelo carregado em {model_load_seconds:.3f} s")
    print(f"Classe person ID: {person_class_id}")
    print()

    cap = cv2.VideoCapture(str(args.input))

    if not cap.isOpened():
        raise RuntimeError(
            f"OpenCV não conseguiu abrir o vídeo: {args.input}"
        )

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    original_fps = float(cap.get(cv2.CAP_PROP_FPS))
    source_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError("Resolução do vídeo inválida.")

    if original_fps <= 0:
        cap.release()
        raise RuntimeError("FPS do vídeo inválido.")

    print("Vídeo:")
    print(f"  resolução      : {width}x{height}")
    print(f"  FPS original   : {original_fps:.6f}")
    print(f"  frames origem  : {source_frame_count}")
    print()

    # IMPORTANTE:
    # O FPS usado no VideoWriter é o FPS do vídeo original.
    # A velocidade da inferência NÃO altera a velocidade de reprodução.
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        str(args.output),
        fourcc,
        original_fps,
        (width, height),
    )

    if not writer.isOpened():
        cap.release()
        raise RuntimeError(
            f"Não foi possível criar vídeo de saída: {args.output}"
        )

    frames_processed = 0
    total_person_detections = 0

    confidences: list[float] = []
    inference_times_ms: list[float] = []

    # Heap dos melhores frames:
    # (score, tie_breaker, frame_index, imagem)
    examples_heap: list = []

    processing_start = time.perf_counter()

    try:
        while True:
            if (
                args.max_frames is not None
                and frames_processed >= args.max_frames
            ):
                break

            ok, frame = cap.read()

            if not ok:
                break

            frame_index = frames_processed

            results = model.predict(
                source=frame,
                imgsz=args.imgsz,
                conf=args.conf,
                device=args.device,
                classes=[person_class_id],
                verbose=False,
            )

            result = results[0]

            speed = getattr(result, "speed", {}) or {}
            inference_ms = speed.get("inference")

            if inference_ms is not None:
                inference_times_ms.append(float(inference_ms))

            frame_detections = []

            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0])

                    # Defesa extra: a inferência já recebeu classes=[person_id].
                    if class_id != person_class_id:
                        continue

                    confidence = float(box.conf[0])

                    bbox = [
                        float(value)
                        for value in box.xyxy[0].tolist()
                    ]

                    frame_detections.append(
                        (bbox, confidence)
                    )

            annotated = frame.copy()

            for bbox, confidence in frame_detections:
                draw_detection(
                    cv2,
                    annotated,
                    bbox,
                    confidence,
                )

                confidences.append(confidence)

            people_this_frame = len(frame_detections)

            total_person_detections += people_this_frame

            cv2.putText(
                annotated,
                f"frame={frame_index} | persons={people_this_frame}",
                (15, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            writer.write(annotated)

            # Prioriza frames com mais pessoas.
            # Em empate, usa a soma das confidências.
            if args.examples > 0 and people_this_frame > 0:
                confidence_sum = sum(
                    confidence
                    for _, confidence in frame_detections
                )

                score = (
                    float(people_this_frame),
                    float(confidence_sum),
                )

                heap_item = (
                    score,
                    frame_index,
                    frame_index,
                    annotated.copy(),
                )

                if len(examples_heap) < args.examples:
                    heapq.heappush(
                        examples_heap,
                        heap_item,
                    )
                elif score > examples_heap[0][0]:
                    heapq.heapreplace(
                        examples_heap,
                        heap_item,
                    )

            frames_processed += 1

            if (
                frames_processed == 1
                or frames_processed % args.progress_every == 0
            ):
                elapsed = time.perf_counter() - processing_start
                processing_fps_now = (
                    frames_processed / elapsed
                    if elapsed > 0
                    else 0.0
                )

                print(
                    f"Progresso: {frames_processed} frames | "
                    f"detecções={total_person_detections} | "
                    f"processamento={processing_fps_now:.2f} FPS"
                )

    finally:
        cap.release()
        writer.release()

    processing_seconds = time.perf_counter() - processing_start

    processing_fps = (
        frames_processed / processing_seconds
        if processing_seconds > 0
        else 0.0
    )

    mean_ms_per_frame = (
        processing_seconds * 1000.0 / frames_processed
        if frames_processed > 0
        else 0.0
    )

    output_duration_seconds = (
        frames_processed / original_fps
        if original_fps > 0
        else 0.0
    )

    examples_saved = save_examples(
        cv2,
        examples_heap,
        args.examples_dir,
    )

    mean_confidence = (
        mean(confidences)
        if confidences
        else None
    )

    min_confidence = (
        min(confidences)
        if confidences
        else None
    )

    max_confidence = (
        max(confidences)
        if confidences
        else None
    )

    mean_inference_ms = (
        mean(inference_times_ms)
        if inference_times_ms
        else None
    )

    metrics = {
        "model": args.model,
        "model_size_mb": model_size_mb(args.model),
        "class": {
            "name": "person",
            "id": person_class_id,
        },
        "input_video": str(args.input),
        "output_video": str(args.output),
        "video": {
            "width": width,
            "height": height,
            "original_fps": original_fps,
            "source_frame_count": source_frame_count,
            "processed_frames": frames_processed,
            "output_duration_seconds": output_duration_seconds,
        },
        "parameters": {
            "imgsz": args.imgsz,
            "confidence_threshold": args.conf,
            "device": args.device,
            "max_frames": args.max_frames,
        },
        "timing": {
            "model_load_seconds": model_load_seconds,
            "processing_seconds": processing_seconds,
            "processing_fps": processing_fps,
            "mean_ms_per_frame": mean_ms_per_frame,
            "mean_yolo_inference_ms": mean_inference_ms,
        },
        "detections": {
            "total_person_detections": total_person_detections,
            "mean_confidence": mean_confidence,
            "min_confidence": min_confidence,
            "max_confidence": max_confidence,
        },
        "examples": examples_saved,
    }

    metrics_path.write_text(
        json.dumps(
            metrics,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 64)
    print(" RESULTADO")
    print("=" * 64)
    print(f"Modelo                    : {args.model}")
    print(f"Classe                    : person ({person_class_id})")
    print(f"Frames processados        : {frames_processed}")
    print(f"FPS vídeo original        : {original_fps:.3f}")
    print(f"Tempo de processamento    : {processing_seconds:.3f} s")
    print(f"Tempo médio/frame         : {mean_ms_per_frame:.3f} ms")
    print(f"FPS efetivo processamento : {processing_fps:.3f}")
    print(f"Pessoas detectadas        : {total_person_detections}")

    if mean_confidence is None:
        print("Confidence média          : n/a")
        print("Confidence mínima         : n/a")
        print("Confidence máxima         : n/a")
    else:
        print(f"Confidence média          : {mean_confidence:.4f}")
        print(f"Confidence mínima         : {min_confidence:.4f}")
        print(f"Confidence máxima         : {max_confidence:.4f}")

    if mean_inference_ms is not None:
        print(f"YOLO inference média      : {mean_inference_ms:.3f} ms/frame")

    print()
    print(f"Vídeo anotado             : {args.output}")
    print(f"Métricas JSON             : {metrics_path}")

    if examples_saved:
        print("Frames de exemplo:")
        for path in examples_saved:
            print(f"  - {path}")

    print("=" * 64)

    return metrics


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        run(args)
    except (ValueError, RuntimeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.", file=sys.stderr)
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
