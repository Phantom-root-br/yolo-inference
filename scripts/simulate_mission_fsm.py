#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from harpia_mission import Detection, MissionConfig, MissionFSM, MissionInput, TargetSelector

WIDTH = 1280
HEIGHT = 720


def show(label: str, decision) -> None:
    suffix = f" reason={decision.reason}" if decision.reason else ""
    print(f"{label:<20} state={decision.state.value:<18} action={decision.action:<26} payload={decision.payload}{suffix}")


def main() -> None:
    selector = TargetSelector(confirm_hits=3, max_misses=3)
    mission = MissionFSM(
        MissionConfig(
            takeoff_height_m=5.0,
            approach_deadband=0.10,
            stable_cycles_required=3,
            search_step_m=2.0,
            search_max_leg_m=10.0,
        )
    )

    show("preflight", mission.tick(MissionInput(preflight_ok=True)))
    show("takeoff", mission.tick(MissionInput(takeoff_reached=True)))
    for index in range(4):
        show(f"search leg {index}", mission.tick(MissionInput(search_step_complete=index > 0)))

    frames = [
        Detection((140, 210, 360, 650), 0.80),
        Detection((170, 205, 390, 650), 0.82),
        Detection((220, 200, 440, 650), 0.84),
        Detection((420, 190, 640, 650), 0.86),
        Detection((520, 130, 740, 590), 0.88),
        Detection((535, 130, 755, 590), 0.89),
        Detection((540, 130, 760, 590), 0.90),
    ]

    for index, detection in enumerate(frames, start=1):
        target = selector.update([detection], frame_width=WIDTH, frame_height=HEIGHT)
        show(f"camera frame {index}", mission.tick(MissionInput(target=target)))

    show(
        "safe zone ready",
        mission.tick(MissionInput(safe_landing_zone_ready=True)),
    )
    show("landing", mission.tick(MissionInput()))
    show("landed", mission.tick(MissionInput(landed=True)))


if __name__ == "__main__":
    main()
