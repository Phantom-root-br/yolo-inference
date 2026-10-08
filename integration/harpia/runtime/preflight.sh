#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
PX4_DIR="${PX4_DIR:-/root/PX4-Autopilot}"
PX4_MSGS_DIR="${PX4_MSGS_DIR:-$WS/src/px4_msgs}"
MANIFEST="$REPO/integration/harpia/repro/validated_stack.env"

fail=0

ok()   { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; }
err()  { printf '[ERROR] %s\n' "$*" >&2; fail=1; }

echo "============================================================"
echo " HARPia :: PREFLIGHT"
echo "============================================================"

for cmd in git tmux bash python3 ros2 gz MicroXRCEAgent; do
  command -v "$cmd" >/dev/null 2>&1     && ok "$cmd"     || err "$cmd not found"
done

[[ -f /opt/ros/humble/setup.bash ]]   && ok "ROS 2 Humble"   || err "/opt/ros/humble/setup.bash not found"

[[ -f "$MANIFEST" ]]   && ok "validated manifest"   || err "missing validated manifest"

if [[ -f "$MANIFEST" ]]; then
  # shellcheck disable=SC1090
  source "$MANIFEST"
fi

SIM="$WS/src/simulation_bringup_eletroquad26"
MISSION="$REPO/yolo_person_mission"
MODEL="$REPO/models/harpia_person_topdown_pilot_v2.pt"
BRIDGE="/root/.cache/harpia/ros_gzgarden/opt/ros/humble/lib/ros_gz_bridge/parameter_bridge"

[[ -d "$SIM" ]] && ok "simulation package" || err "simulation package missing"
[[ -d "$MISSION" ]] && ok "mission package" || err "mission package missing"
[[ -f "$MODEL" ]] && ok "validated YOLO model" || err "validated YOLO model missing"

[[ -d "$SIM/models/eletroquad_26" ]]   && ok "eletroquad_26 assets"   || err "eletroquad_26 assets missing"

[[ -d "$SIM/models/harpia/LW20" ]]   && ok "LW20 assets"   || err "LW20 assets missing"

[[ -d "$SIM/models/harpia/realsense_d435" ]]   && ok "RealSense assets"   || err "RealSense assets missing"

if [[ -d "$PX4_DIR/.git" ]]; then
  actual="$(git -C "$PX4_DIR" rev-parse HEAD)"
  [[ "$actual" == "${PX4_COMMIT:-}" ]]     && ok "PX4 exact commit $actual"     || err "PX4 commit mismatch: $actual"
else
  err "PX4 repository missing: $PX4_DIR"
fi

if [[ -d "$PX4_MSGS_DIR/.git" ]]; then
  actual="$(git -C "$PX4_MSGS_DIR" rev-parse HEAD)"
  [[ "$actual" == "${PX4_MSGS_COMMIT:-}" ]]     && ok "px4_msgs exact commit $actual"     || err "px4_msgs commit mismatch: $actual"
else
  err "px4_msgs repository missing: $PX4_MSGS_DIR"
fi

if [[ -x "$BRIDGE" ]]; then
  actual="$(sha256sum "$BRIDGE" | awk '{print $1}')"
  [[ "$actual" == "${GARDEN_PARAMETER_BRIDGE_SHA256:-}" ]]     && ok "validated Garden parameter_bridge"     || err "Garden parameter_bridge checksum mismatch"
else
  err "validated Garden parameter_bridge missing"
fi

if [[ "$fail" -ne 0 ]]; then
  echo
  echo "PREFLIGHT_READY=0"
  exit 2
fi

echo
echo "PREFLIGHT_READY=1"
