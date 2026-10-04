#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import secrets
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPAWN_SCRIPT = ROOT / "scripts" / "gazebo_spawn_human.sh"
REMOVE_SCRIPT = ROOT / "scripts" / "gazebo_remove_human.sh"
DEFAULT_METADATA = ROOT / "output" / "gazebo_human_target.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Insere uma unica pessoa em pose pseudoaleatoria no world Gazebo ativo, "
            "sem modificar o arquivo do world."
        )
    )
    parser.add_argument("--world", default=None, help="World Gazebo; autodetecta se omitido.")
    parser.add_argument("--seed", type=int, default=None, help="Seed para repetir a mesma pose.")
    parser.add_argument("--xmin", type=float, default=-12.0)
    parser.add_argument("--xmax", type=float, default=12.0)
    parser.add_argument("--ymin", type=float, default=-12.0)
    parser.add_argument("--ymax", type=float, default=12.0)
    parser.add_argument(
        "--min-origin-distance",
        type=float,
        default=4.0,
        help="Distancia horizontal minima da origem do world, em metros.",
    )
    parser.add_argument("--z", type=float, default=1.0)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA,
        help="JSON local com seed e pose escolhida.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Nao tenta remover harpia_human_target antes do spawn.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sorteia e mostra a pose sem chamar Gazebo.",
    )
    return parser.parse_args()


def list_gz_services() -> list[str]:
    if shutil.which("gz") is None:
        raise RuntimeError("comando 'gz' nao encontrado")
    result = subprocess.run(
        ["gz", "service", "-l"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def detect_world(services: list[str]) -> str:
    worlds = []
    for service in services:
        prefix = "/world/"
        suffix = "/create"
        if service.startswith(prefix) and service.endswith(suffix):
            worlds.append(service[len(prefix) : -len(suffix)])
    if not worlds:
        raise RuntimeError("nenhum servico /world/<nome>/create encontrado")
    return sorted(worlds)[0]


def sample_pose(
    rng: random.Random,
    *,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    min_origin_distance: float,
) -> tuple[float, float, float]:
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("limites invalidos: minimo deve ser menor que maximo")
    if min_origin_distance < 0:
        raise ValueError("min_origin_distance deve ser >= 0")

    max_radius = max(
        math.hypot(x, y)
        for x in (xmin, xmax)
        for y in (ymin, ymax)
    )
    if min_origin_distance > max_radius:
        raise ValueError("raio de exclusao maior que a area de sorteio")

    for _ in range(10_000):
        x = rng.uniform(xmin, xmax)
        y = rng.uniform(ymin, ymax)
        if math.hypot(x, y) >= min_origin_distance:
            yaw = rng.uniform(-math.pi, math.pi)
            return x, y, yaw
    raise RuntimeError("nao foi possivel sortear pose valida")


def run_best_effort_remove(world: str) -> None:
    subprocess.run(
        [str(REMOVE_SCRIPT), world],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    args = parse_args()
    seed = args.seed if args.seed is not None else secrets.randbits(32)
    rng = random.Random(seed)
    x, y, yaw = sample_pose(
        rng,
        xmin=args.xmin,
        xmax=args.xmax,
        ymin=args.ymin,
        ymax=args.ymax,
        min_origin_distance=args.min_origin_distance,
    )

    services: list[str] = []
    if args.dry_run:
        world = args.world or "dry_run_world"
    else:
        services = list_gz_services()
        world = args.world or detect_world(services)
        create_service = f"/world/{world}/create"
        if create_service not in services:
            raise RuntimeError(f"servico nao encontrado: {create_service}")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "world": world,
        "entity_name": "harpia_human_target",
        "seed": seed,
        "pose": {"x": x, "y": y, "z": args.z, "yaw": yaw},
        "bounds": {
            "xmin": args.xmin,
            "xmax": args.xmax,
            "ymin": args.ymin,
            "ymax": args.ymax,
            "min_origin_distance": args.min_origin_distance,
        },
        "dry_run": args.dry_run,
        "obstacle_aware": False,
    }

    print("=" * 60)
    print(" HARPia - ALVO HUMANO ALEATORIO NO WORLD ATIVO")
    print("=" * 60)
    print(f"World : {world}")
    print(f"Seed  : {seed}")
    print(f"Pose  : x={x:.3f} y={y:.3f} z={args.z:.3f} yaw={yaw:.5f}")
    print(
        "Area  : "
        f"x=[{args.xmin:.1f},{args.xmax:.1f}] "
        f"y=[{args.ymin:.1f},{args.ymax:.1f}] "
        f"raio_exclusao={args.min_origin_distance:.1f}m"
    )
    print("Obs.  : sorteio planar; ainda nao e obstacle-aware")

    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Meta  : {args.metadata}")

    if args.dry_run:
        print("DRY-RUN: Gazebo nao foi alterado.")
        return 0

    if not args.keep_existing:
        run_best_effort_remove(world)

    subprocess.run(
        [
            str(SPAWN_SCRIPT),
            world,
            f"{x:.6f}",
            f"{y:.6f}",
            f"{args.z:.6f}",
            f"{yaw:.6f}",
        ],
        check=True,
    )
    print("Alvo solicitado ao Gazebo. Use a seed acima para repetir este caso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
