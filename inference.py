#!/usr/bin/env python3
"""Inferência simples com YOLO para imagens estáticas.

Este módulo mantém as dependências pesadas (Ultralytics/OpenCV) fora do import
inicial para que a CLI, os testes unitários e a documentação possam ser
validados sem carregar o modelo.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


DEFAULT_MODEL = "yolo11n.pt"
DEFAULT_CONFIDENCE = 0.25
DEFAULT_IMAGE_SIZE = 640
DEFAULT_DEVICE = "cpu"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Executa inferência YOLO em uma imagem e salva o resultado anotado."
    )
    parser.add_argument("image", type=Path, help="Caminho da imagem de entrada.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Modelo YOLO (padrão: {DEFAULT_MODEL}).")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Imagem anotada de saída. Padrão: <imagem>_yolo.jpg.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Opcional: salva as detecções também em JSON.",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=DEFAULT_CONFIDENCE,
        help=f"Confiança mínima entre 0 e 1 (padrão: {DEFAULT_CONFIDENCE}).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=DEFAULT_IMAGE_SIZE,
        help=f"Tamanho da entrada do modelo (padrão: {DEFAULT_IMAGE_SIZE}).",
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help="Dispositivo de inferência: cpu, 0, 1, ... (padrão: cpu).",
    )
    return parser


def default_output_path(image_path: Path) -> Path:
    return image_path.with_name(f"{image_path.stem}_yolo.jpg")


def calculate_center_error(
    bbox_xyxy: Sequence[float],
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float]:
    """Retorna centro da bbox (cx, cy) e erro (ex, ey) em pixels."""
    x1, y1, x2, y2 = bbox_xyxy
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    ex = cx - (image_width / 2.0)
    ey = cy - (image_height / 2.0)
    return cx, cy, ex, ey


def validate_args(args: argparse.Namespace) -> None:
    if not args.image.is_file():
        raise ValueError(f"Imagem não encontrada: {args.image}")
    if not 0.0 <= args.conf <= 1.0:
        raise ValueError("--conf deve estar entre 0 e 1.")
    if args.imgsz <= 0:
        raise ValueError("--imgsz deve ser maior que zero.")


def load_runtime_dependencies():
    try:
        import cv2  # type: ignore
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Dependências de inferência ausentes. Execute './scripts/setup.sh' "
            "ou 'pip install -r requirements.txt'."
        ) from exc
    return cv2, YOLO


def detection_to_dict(box, names, image_width: int, image_height: int) -> dict:
    class_id = int(box.cls[0])
    confidence = float(box.conf[0])
    bbox = [float(value) for value in box.xyxy[0].tolist()]
    cx, cy, ex, ey = calculate_center_error(bbox, image_width, image_height)

    return {
        "class_id": class_id,
        "class_name": names[class_id],
        "confidence": confidence,
        "bbox_xyxy": {
            "x1": bbox[0],
            "y1": bbox[1],
            "x2": bbox[2],
            "y2": bbox[3],
        },
        "center_px": {"x": cx, "y": cy},
        "error_from_image_center_px": {"x": ex, "y": ey},
    }


def print_detection(index: int, detection: dict) -> None:
    bbox = detection["bbox_xyxy"]
    center = detection["center_px"]
    error = detection["error_from_image_center_px"]

    print(f"Detecção {index}")
    print(f"  classe      : {detection['class_name']}")
    print(f"  class_id    : {detection['class_id']}")
    print(f"  confiança   : {detection['confidence']:.3f}")
    print(
        "  bbox         : "
        f"x1={bbox['x1']:.1f}, y1={bbox['y1']:.1f}, "
        f"x2={bbox['x2']:.1f}, y2={bbox['y2']:.1f}"
    )
    print(f"  centro bbox  : cx={center['x']:.1f}, cy={center['y']:.1f}")
    print(f"  erro centro  : ex={error['x']:.1f}, ey={error['y']:.1f}")
    print()


def run_inference(args: argparse.Namespace) -> dict:
    validate_args(args)
    cv2, YOLO = load_runtime_dependencies()

    output_path = args.output or default_output_path(args.image)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" YOLO Inference | HARPia")
    print("=" * 60)
    print(f"Modelo : {args.model}")
    print(f"Imagem : {args.image}")
    print(f"Device : {args.device}")
    print(f"imgsz  : {args.imgsz}")
    print(f"conf   : {args.conf}")
    print()

    model = YOLO(args.model)
    results = model.predict(
        source=str(args.image),
        imgsz=args.imgsz,
        conf=args.conf,
        device=args.device,
        verbose=False,
    )

    result = results[0]
    image_height, image_width = result.orig_shape
    boxes = result.boxes

    detections = []
    if boxes is not None:
        detections = [
            detection_to_dict(box, result.names, image_width, image_height)
            for box in boxes
        ]

    print(f"Resolução original: {image_width}x{image_height}")
    print(f"Detecções: {len(detections)}")
    print()

    for index, detection in enumerate(detections, start=1):
        print_detection(index, detection)

    annotated = result.plot()
    if not cv2.imwrite(str(output_path), annotated):
        raise RuntimeError(f"Não foi possível salvar a imagem em: {output_path}")

    speed = getattr(result, "speed", {}) or {}
    summary = {
        "model": args.model,
        "input_image": str(args.image),
        "output_image": str(output_path),
        "image_size": {"width": image_width, "height": image_height},
        "parameters": {
            "confidence": args.conf,
            "imgsz": args.imgsz,
            "device": args.device,
        },
        "timing_ms": {
            "preprocess": speed.get("preprocess"),
            "inference": speed.get("inference"),
            "postprocess": speed.get("postprocess"),
        },
        "detections": detections,
    }

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"JSON salvo em: {args.json_output}")

    print(f"Imagem anotada salva em: {output_path}")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        run_inference(args)
    except (ValueError, RuntimeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
