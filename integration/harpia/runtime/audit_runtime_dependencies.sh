#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
PX4_DIR="${PX4_DIR:-/root/PX4-Autopilot}"
SIM_SRC="${HARPIA_SIM_SRC:-$WS/src/simulation_bringup_eletroquad26}"

echo "============================================================"
echo " HARPia :: AUDIT RUNTIME DEPENDENCIES"
echo "============================================================"

echo "workspace=$WS"
echo "repo=$REPO"
echo "px4=$PX4_DIR"
echo "sim=$SIM_SRC"
echo

fail=0

ok()   { echo "[OK] $*"; }
warn() { echo "[WARN] $*"; }
bad()  { echo "[MISSING] $*"; fail=1; }

check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "$1 -> $(command -v "$1")"
  else
    bad "command $1"
  fi
}

echo "===== 1. HOST COMMANDS ====="
for cmd in git tmux python3 ros2 gz MicroXRCEAgent sha256sum rsync; do
  check_cmd "$cmd"
done

echo
echo "===== 2. ROS / PX4 ====="

[[ -f /opt/ros/humble/setup.bash ]]   && ok "ROS 2 Humble"   || bad "/opt/ros/humble/setup.bash"

if [[ -d "$PX4_DIR/.git" ]]; then
  ok "PX4 repository"
  echo "PX4_COMMIT=$(git -C "$PX4_DIR" rev-parse HEAD)"
else
  bad "PX4 repository at $PX4_DIR"
fi

echo
echo "===== 3. PX4_MSGS ====="

PX4_MSGS_FOUND=""

for p in   "$WS/src/px4_msgs"   "/root/px4_ws/src/px4_msgs"   "/root/px4_msgs"
do
  if [[ -d "$p" ]]; then
    PX4_MSGS_FOUND="$p"
    break
  fi
done

if [[ -n "$PX4_MSGS_FOUND" ]]; then
  ok "px4_msgs: $PX4_MSGS_FOUND"

  if git -C "$PX4_MSGS_FOUND" rev-parse HEAD >/dev/null 2>&1; then
    echo "PX4_MSGS_COMMIT=$(git -C "$PX4_MSGS_FOUND" rev-parse HEAD)"
  fi
else
  bad "px4_msgs source not found in known workspaces"
fi

echo
echo "===== 4. GARDEN ROS-GZ BRIDGE ====="

CACHE_BRIDGE="/root/.cache/harpia/ros_gzgarden/opt/ros/humble/lib/ros_gz_bridge/parameter_bridge"
GARDEN_WS="/root/ros_gz_garden_ws/install/setup.bash"

[[ -x "$CACHE_BRIDGE" ]]   && ok "cached Garden parameter_bridge: $CACHE_BRIDGE"   || bad "cached Garden parameter_bridge: $CACHE_BRIDGE"

[[ -f "$GARDEN_WS" ]]   && ok "Garden overlay: $GARDEN_WS"   || warn "Garden overlay missing: $GARDEN_WS"

if [[ -x "$CACHE_BRIDGE" ]]; then
  echo "BRIDGE_SHA256=$(sha256sum "$CACHE_BRIDGE" | awk '{print $1}')"
fi

echo
echo "===== 5. WIND PLUGIN ====="

WIND_DIR="/usr/local/lib/harpia/wind/lib"

if [[ -d "$WIND_DIR" ]]; then
  ok "wind plugin dir: $WIND_DIR"
  find "$WIND_DIR" -maxdepth 1 -type f -printf '%f\n' | sort
else
  bad "wind plugin dir: $WIND_DIR"
fi

echo
echo "===== 6. GAZEBO MODEL DEPENDENCIES ====="

RESOURCE_ROOTS=(
  "$SIM_SRC/models"
  "$PX4_DIR/Tools/simulation/gz/models"
  "/opt/ros/humble/share/as2_gazebo_assets/models"
)

find_model_dir() {
  local rel="$1"
  local root

  for root in "${RESOURCE_ROOTS[@]}"; do
    if [[ -d "$root/$rel" ]]; then
      printf '%s\n' "$root/$rel"
      return 0
    fi
  done

  return 1
}

MODEL_DEPS=(
  "eletroquad_26"
  "harpia/LW20"
  "harpia/realsense_d435"
  "x500"
)

for rel in "${MODEL_DEPS[@]}"; do
  if path="$(find_model_dir "$rel")"; then
    ok "model $rel -> $path"
    du -sh "$path" 2>/dev/null || true
  else
    bad "Gazebo model dependency: $rel"
  fi
done

echo
echo "===== 7. WORLD URI INVENTORY ====="

WORLD="$SIM_SRC/worlds/harpia_yolo_person.sdf"

if [[ -f "$WORLD" ]]; then
  grep -oE '<uri>[^<]+' "$WORLD"     | sed 's#<uri>##'     | sort -u
else
  bad "world file: $WORLD"
fi

echo
echo "===== 8. X500 URI INVENTORY ====="

X500="$SIM_SRC/models/harpia_yolo_x500/model.sdf"

if [[ -f "$X500" ]]; then
  grep -oE '<uri>[^<]+' "$X500"     | sed 's#<uri>##'     | sort -u
else
  bad "x500 model: $X500"
fi

echo
echo "===== 9. HARD-CODED HOST PATHS ====="

for f in   "$SIM_SRC/config/simulation/start_px4_yolo_person.sh"   "$SIM_SRC/config/simulation/start_garden_camera_bridge.sh"   "$SIM_SRC/config/simulation/run_yolo_person.sh"   "$SIM_SRC/config/simulation/wait_and_start_yolo_mission.sh"
do
  echo "--- $f"
  grep -nE '/root/|/usr/local/lib/harpia|/opt/ros/humble' "$f" || true
done

echo
echo "===== 10. DISPLAY ====="
echo "DISPLAY=${DISPLAY:-<unset>}"
echo "XAUTHORITY=${XAUTHORITY:-<unset>}"

echo
echo "===== RESULT ====="

if (( fail != 0 )); then
  echo "RUNTIME_DEPENDENCIES_READY=0"
  exit 4
fi

echo "RUNTIME_DEPENDENCIES_READY=1"
