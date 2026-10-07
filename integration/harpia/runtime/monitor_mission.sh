#!/usr/bin/env bash
set -euo pipefail

SESSION="${HARPIA_TMUX_SESSION:-HarpiaYolo}"
WINDOW="${HARPIA_MISSION_WINDOW:-mission}"
INTERVAL="${HARPIA_MONITOR_INTERVAL_SEC:-3}"
TIMEOUT="${HARPIA_MONITOR_TIMEOUT_SEC:-1200}"
LOG="${HARPIA_MONITOR_LOG:-/tmp/harpia_mission_monitor_$(date +%Y%m%d-%H%M%S).log}"

START=$(date +%s)
LAST=""

echo "============================================================" | tee "$LOG"
echo " HARPia :: LIVE MISSION STATUS" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
echo "session=$SESSION window=$WINDOW timeout=${TIMEOUT}s" | tee -a "$LOG"

while true; do
  now_epoch=$(date +%s)
  elapsed=$((now_epoch - START))
  now=$(date '+%H:%M:%S')

  if (( elapsed >= TIMEOUT )); then
    echo "[$now] MONITOR_TIMEOUT after ${elapsed}s" | tee -a "$LOG"
    exit 4
  fi

  if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[$now] ERROR: tmux session disappeared: $SESSION" | tee -a "$LOG"
    exit 3
  fi

  current="$(
    tmux capture-pane       -p       -J       -t "$SESSION:$WINDOW"       -S -220       2>/dev/null |
    grep -E       'STATE:|MISSION_EVENT:|TAKEOFF|SPIRAL|TARGET LOCKED|PERSON_CONFIRMED|PERSON_CENTERED|BBOX_ACCEPT|BBOX_KEEP|BBOX_CHASE|BBOX_CENTERED|TRACK_HIGH|TRACK_LOW|DESCEND|TARGET_LOW|ASCEND|RETURN_HOME|LAND|LANDED|DISARM|VEHICLE_DISARMED|MISSION_COMPLETE|ERROR_HOLD' |
    tail -n 45 || true
  )"

  if [[ -n "$current" && "$current" != "$LAST" ]]; then
    echo "------------------------------------------------------------" | tee -a "$LOG"
    echo "[$now] elapsed=${elapsed}s" | tee -a "$LOG"
    printf '%s\n' "$current" | tee -a "$LOG"
    LAST="$current"
  fi

  if grep -q 'MISSION_COMPLETE' <<<"$current"; then
    echo "[$now] ✅ MISSION_COMPLETE" | tee -a "$LOG"
    echo "LOG=$LOG" | tee -a "$LOG"
    exit 0
  fi

  if grep -q 'ERROR_HOLD' <<<"$current"; then
    echo "[$now] ❌ ERROR_HOLD" | tee -a "$LOG"
    echo "LOG=$LOG" | tee -a "$LOG"
    exit 5
  fi

  sleep "$INTERVAL"
done
