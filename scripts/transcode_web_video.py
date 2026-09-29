#!/usr/bin/env python3
"""Transcodifica o vídeo anotado para H.264 compatível com navegadores."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Converte um MP4 anotado para H.264/yuv420p preservando os frames."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--crf", type=int, default=20)
    return parser


def find_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError(
            "imageio-ffmpeg não está instalado. Execute: "
            "/root/yolo_venv/bin/python -m pip install -r requirements.txt"
        ) from exc

    return imageio_ffmpeg.get_ffmpeg_exe()


def transcode(input_path: Path, output_path: Path, crf: int) -> None:
    if not input_path.is_file():
        raise ValueError(f"Vídeo de entrada não encontrado: {input_path}")
    if not 0 <= crf <= 51:
        raise ValueError("--crf deve estar entre 0 e 51.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(output_path),
    ]

    print(f"Transcodificando para navegador: {input_path} -> {output_path}")
    subprocess.run(command, check=True)

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg não gerou um arquivo válido: {output_path}")

    print(
        f"Vídeo H.264 pronto: {output_path} "
        f"({output_path.stat().st_size / 1024 / 1024:.1f} MB)"
    )


def main() -> int:
    args = build_parser().parse_args()
    transcode(args.input, args.output, args.crf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
