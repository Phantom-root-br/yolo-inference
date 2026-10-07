#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
PYTHON_BIN="${YOLO_PYTHON:-/root/yolo_venv/bin/python3}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

source /opt/ros/humble/setup.bash

if [[ -f "$WS/install/setup.bash" ]]; then
  source "$WS/install/setup.bash"
fi

if [[ -z "${DISPLAY:-}" ]]; then
  export DISPLAY=:1
fi

if [[ -z "${XAUTHORITY:-}" && -f "$HOME/.Xauthority" ]]; then
  export XAUTHORITY="$HOME/.Xauthority"
fi

echo "[viewer] DISPLAY=$DISPLAY"
echo "[viewer] topic=/yolo/image_annotated"
echo "[viewer] waiting for frames inside viewer; no ros2 topic echo gate"

exec "$PYTHON_BIN"   "$REPO/integration/harpia/runtime/annotated_camera_viewer.py"   --topic /yolo/image_annotated   --width 960
