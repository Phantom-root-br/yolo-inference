#!/usr/bin/env python3
"""Train/fine-tune a top-down person detector with Ultralytics YOLO."""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="YOLO dataset YAML")
    parser.add_argument("--base-model", default="yolo11n.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--project", default="runs/harpia_person")
    parser.add_argument("--name", default="harpia_person_topdown")
    parser.add_argument("--cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    data_path = Path(args.data).expanduser().resolve()
    if not data_path.exists():
        raise SystemExit(f"dataset YAML not found: {data_path}")

    model = YOLO(args.base_model)

    model.train(
        data=str(data_path),
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        patience=args.patience,
        seed=args.seed,
        project=args.project,
        name=args.name,
        cache=args.cache,
        pretrained=True,
        plots=True,
        verbose=True,
    )


if __name__ == "__main__":
    main()
