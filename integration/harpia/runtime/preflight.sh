#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"

fail=0

ok()   { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; }
err()  { printf '[ERROR] %s\n' "$*" >&2; fail=1; }

command -v tmux >/dev/null 2>&1 && ok "tmux" || err "tmux not found"
command -v bash >/dev/null 2>&1 && ok "bash" || err "bash not found"

[[ -f /opt/ros/humble/setup.bash ]]   && ok "ROS 2 Humble"   || err "/opt/ros/humble/setup.bash not found"

[[ -d "$WS" ]]   && ok "workspace: $WS"   || err "workspace not found: $WS"

[[ -d "$REPO" ]]   && ok "repository: $REPO"   || err "repository not found: $REPO"

SIM="$WS/src/simulation_bringup_eletroquad26"
MISSION="$REPO/yolo_person_mission"
MODEL="$REPO/models/harpia_person_topdown_pilot_v2.pt"

[[ -d "$SIM" ]]   && ok "simulation_bringup_eletroquad26"   || err "missing external HARPia simulation dependency: $SIM"

[[ -d "$MISSION" ]]   && ok "local yolo_person_mission package"   || err "missing yolo_person_mission package: $MISSION"

[[ -f "$MODEL" ]]   && ok "model: harpia_person_topdown_pilot_v2.pt"   || err "model artifact missing: $MODEL"

[[ -x /root/yolo_venv/bin/python3 ]]   && ok "YOLO Python venv"   || warn "/root/yolo_venv/bin/python3 not found; scripts may fall back to python3"

[[ -x /root/yolo_venv/bin/colcon ]]   && ok "colcon"   || warn "/root/yolo_venv/bin/colcon not found"

if [[ "$fail" -ne 0 ]]; then
  cat <<'EOF'

Preflight failed.

This means the complete HARPia demo is not yet a standalone clone-and-run
artifact on this machine. The portable YOLO package remains usable by itself,
but the full simulation also requires the HARPia/PX4 simulation workspace and
the custom model artifact.
EOF
  exit 2
fi

ok "preflight complete"
