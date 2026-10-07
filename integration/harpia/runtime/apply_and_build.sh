#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
PYTHON_BIN="${YOLO_PYTHON:-/root/yolo_venv/bin/python3}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

"$PYTHON_BIN"   "$REPO/integration/harpia/runtime/apply_final_runtime_fixes.py"   --workspace "$WS"

source /opt/ros/humble/setup.bash

cd "$WS"

"${YOLO_COLCON:-/root/yolo_venv/bin/colcon}" build   --packages-select   yolo_person_mission   --symlink-install

echo "[OK] runtime fixes applied and mission rebuilt"
echo "Next:"
echo "  bash $REPO/integration/harpia/runtime/run_harpia_yolo_with_viewer.sh"
