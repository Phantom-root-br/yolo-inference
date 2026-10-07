#!/usr/bin/env python3
"""Apply the final HARPia simulation runtime fixes.

This patcher targets the current HARPia workspace layout used during the
2026-10-07 integration work. It intentionally keeps PX4/Gazebo-specific changes
outside the portable detector packages.

Fixes:
1. DISARM: normal request first; optional force-disarm only after LANDED and
   only when explicitly enabled by the simulation launch profile.
2. Viewer: no Image topic-echo readiness gate is required; use the standalone
   best-effort annotated viewer instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re


PARAM_BLOCK = """        # Simulation-only post-landing DISARM fallback.
        #
        # Keep FALSE by default for portability/real-aircraft safety.
        self.declare_parameter(
            'allow_force_disarm_after_landed',
            False,
        )
        self.declare_parameter(
            'force_disarm_after_sec',
            5.0,
        )
        self.declare_parameter(
            'disarm_timeout_sec',
            20.0,
        )

"""

FORCED_HELPER = """    def send_forced_disarm_command(
        self,
    ) -> None:
        \"""Send MAV_CMD_COMPONENT_ARM_DISARM with force magic.

        This helper is only called after the FSM has already emitted LANDED
        and only when allow_force_disarm_after_landed is explicitly enabled.
        \"""

        msg = VehicleCommand()
        msg.param1 = 0.0
        msg.param2 = 21196.0
        msg.command = (
            VehicleCommand
            .VEHICLE_CMD_COMPONENT_ARM_DISARM
        )
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = int(
            self.get_clock().now().nanoseconds
            / 1000
        )

        self.command_pub.publish(msg)

"""

DISARM_BLOCK = """        if self.state == State.DISARM:

            age = self.state_age()

            allow_force = bool(
                self.get_parameter(
                    'allow_force_disarm_after_landed'
                ).value
            )

            force_after = float(
                self.get_parameter(
                    'force_disarm_after_sec'
                ).value
            )

            disarm_timeout = float(
                self.get_parameter(
                    'disarm_timeout_sec'
                ).value
            )

            # Always try the normal landed disarm first.
            self.maybe_repeat_command(
                VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
                param1=0.0,
            )

            # In the simulation profile only, use MAVLink force-disarm
            # after a grace period. DISARM is reachable only after the
            # LAND_HOME state has already emitted LANDED.
            if (
                allow_force
                and age >= force_after
                and self.is_armed()
            ):

                now = time.monotonic()

                last_force = float(
                    getattr(
                        self,
                        '_last_force_disarm_monotonic',
                        0.0,
                    )
                )

                if (
                    now - last_force
                    >= 1.0
                ):

                    self._last_force_disarm_monotonic = now

                    if not bool(
                        getattr(
                            self,
                            '_force_disarm_announced',
                            False,
                        )
                    ):

                        self._force_disarm_announced = True

                        self.get_logger().warning(
                            'DISARM normal nao confirmou; '
                            'enviando force-disarm '
                            'POS-LANDED (simulacao).'
                        )

                    self.send_forced_disarm_command()

            if not self.is_armed():

                self.publish_event(
                    'VEHICLE_DISARMED'
                )

                self.publish_event(
                    'MISSION_COMPLETE'
                )

                self.transition(
                    State.COMPLETE,
                    'missao concluida',
                )

            elif age > disarm_timeout:

                self.transition(
                    State.ERROR_HOLD,
                    'DISARM nao confirmou',
                )

            return

"""


def patch_mission(path: Path) -> bool:
    text = path.read_text()
    changed = False

    if "allow_force_disarm_after_landed" not in text:
        marker = "        self.declare_parameter("
        pos = text.find(marker)

        if pos < 0:
            raise RuntimeError(
                "could not find first declare_parameter"
            )

        text = text[:pos] + PARAM_BLOCK + text[pos:]
        changed = True

    if "def send_forced_disarm_command(" not in text:
        marker = "    def maybe_repeat_command("

        pos = text.find(marker)

        if pos < 0:
            marker = "    def position_valid("
            pos = text.find(marker)

        if pos < 0:
            raise RuntimeError(
                "could not find helper insertion point"
            )

        text = text[:pos] + FORCED_HELPER + text[pos:]
        changed = True

    start = text.find(
        "        if self.state == State.DISARM:"
    )

    if start < 0:
        raise RuntimeError(
            "DISARM state block not found"
        )

    complete_marker = (
        "        # -----------------------------------------------------\n"
        "        # COMPLETE"
    )

    end = text.find(
        complete_marker,
        start,
    )

    if end < 0:
        raise RuntimeError(
            "COMPLETE marker not found after DISARM"
        )

    current = text[start:end]

    if (
        "send_forced_disarm_command"
        not in current
        or "disarm_timeout_sec"
        not in current
    ):
        text = (
            text[:start]
            + DISARM_BLOCK
            + "\n"
            + text[end:]
        )
        changed = True

    if changed:
        path.write_text(text)

    return changed


def patch_ready_script(path: Path) -> bool:
    text = path.read_text()

    additions = {
        "allow_force_disarm_after_landed": "true",
        "force_disarm_after_sec": "5.0",
        "disarm_timeout_sec": "20.0",
    }

    lines = text.splitlines()
    changed = False

    for index, line in enumerate(lines):
        if (
            line.lstrip().startswith("exec ")
            and "yolo_person_mission/person_mission"
            in line
        ):
            for key, value in additions.items():
                pattern = (
                    r"\s+-p "
                    + re.escape(key)
                    + r":=[^\s]+"
                )

                if re.search(pattern, line):
                    new_line = re.sub(
                        pattern,
                        f" -p {key}:={value}",
                        line,
                    )

                    if new_line != line:
                        changed = True

                    line = new_line
                else:
                    line += f" -p {key}:={value}"
                    changed = True

            lines[index] = line

    if changed:
        path.write_text(
            "\n".join(lines) + "\n"
        )

    return changed


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--workspace",
        default="/root/harpia_ws",
    )

    args = parser.parse_args()

    ws = Path(args.workspace)

    mission = (
        ws
        / "src/yolo-inference"
        / "yolo_person_mission"
        / "yolo_person_mission"
        / "person_mission_node.py"
    )

    ready = (
        ws
        / "src/simulation_bringup_eletroquad26"
        / "config/simulation"
        / "wait_and_start_yolo_mission.sh"
    )

    if not mission.exists():
        raise SystemExit(
            f"mission source not found: {mission}"
        )

    if not ready.exists():
        raise SystemExit(
            f"mission launch script not found: {ready}"
        )

    mission_changed = patch_mission(
        mission
    )

    ready_changed = patch_ready_script(
        ready
    )

    print(
        "MISSION_PATCHED="
        + str(int(mission_changed))
    )

    print(
        "READY_PATCHED="
        + str(int(ready_changed))
    )

    print(
        "FORCE_DISARM_DEFAULT=false"
    )

    print(
        "SIM_LAUNCH_FORCE_DISARM=true"
    )


if __name__ == "__main__":
    main()
