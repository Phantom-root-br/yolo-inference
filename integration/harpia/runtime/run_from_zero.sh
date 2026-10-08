#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
RUNTIME="$REPO/integration/harpia/runtime"

echo "============================================================"
echo " HARPia YOLO :: ONE-COMMAND DEMO"
echo "============================================================"
echo
echo "workspace : $WS"
echo "repo      : $REPO"
echo

echo "===== BOOTSTRAP DISTRIBUTED STACK ====="
bash "$RUNTIME/bootstrap_workspace.sh"

echo
bash "$RUNTIME/preflight.sh"

echo
echo "===== APPLY + BUILD ====="
bash "$RUNTIME/apply_and_build.sh"

echo
echo "===== RESET PREVIOUS SESSION ====="
if tmux has-session -t HarpiaYolo 2>/dev/null; then
  tmux kill-session -t HarpiaYolo
  sleep 2
fi

echo
echo "===== START HARPia + CAMERA VIEWER ====="
bash "$RUNTIME/run_harpia_yolo_with_viewer.sh"

echo
echo "===== LIVE MISSION STATUS ====="
echo "The command intentionally stays in the foreground until COMPLETE or ERROR_HOLD."
echo

exec bash "$RUNTIME/monitor_mission.sh"
