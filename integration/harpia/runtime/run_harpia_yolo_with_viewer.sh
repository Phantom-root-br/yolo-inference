#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"

RUN_SCRIPT="$WS/src/simulation_bringup_eletroquad26/config/simulation/run_yolo_person.sh"

if [[ ! -f "$RUN_SCRIPT" ]]; then
  echo "run script not found: $RUN_SCRIPT" >&2
  exit 2
fi

# ROS setup scripts are not compatible with nounset in all environments.
set +u
source /opt/ros/humble/setup.bash

if [[ -f "$WS/install/setup.bash" ]]; then
  source "$WS/install/setup.bash"
fi
set -u

bash "$RUN_SCRIPT"

echo "[viewer] waiting for /yolo_person_detector"

for _ in $(seq 1 120); do
  if ros2 node list 2>/dev/null | grep -qx "/yolo_person_detector"; then
    break
  fi
  sleep 1
done

if ! tmux has-session -t HarpiaYolo 2>/dev/null; then
  echo "tmux session HarpiaYolo not found" >&2
  exit 3
fi

if tmux list-windows -t HarpiaYolo -F '#W' | grep -qx camera; then
  tmux kill-window -t HarpiaYolo:camera || true
fi

tmux new-window   -d   -t HarpiaYolo   -n camera

DISPLAY_VALUE="${DISPLAY:-:1}"
XAUTH_VALUE="${XAUTHORITY:-$HOME/.Xauthority}"

CMD="cd '$WS'; export DISPLAY='$DISPLAY_VALUE'; export XAUTHORITY='$XAUTH_VALUE'; export HARPIA_WS='$WS'; export YOLO_REPO='$REPO'; bash '$REPO/integration/harpia/runtime/open_annotated_camera.sh'"

tmux send-keys   -t HarpiaYolo:camera   "$CMD"   C-m

echo "[OK] HARPia started"
echo "[OK] annotated camera viewer launched in tmux window: camera"
echo "     tmux attach -t HarpiaYolo"
