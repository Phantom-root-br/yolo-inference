#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
PX4_DIR="${PX4_DIR:-/root/PX4-Autopilot}"
PX4_MSGS_DIR="${PX4_MSGS_DIR:-$WS/src/px4_msgs}"

SIM_VENDOR="$REPO/vendor/simulation_bringup_eletroquad26"
SIM_LINK="$WS/src/simulation_bringup_eletroquad26"
MODEL="$REPO/models/harpia_person_topdown_pilot_v2.pt"
MANIFEST="$REPO/integration/harpia/repro/validated_stack.env"

echo "============================================================"
echo " HARPia :: BOOTSTRAP WORKSPACE"
echo "============================================================"

[[ -f /opt/ros/humble/setup.bash ]] || {
  echo "[ERROR] ROS 2 Humble is required at /opt/ros/humble" >&2
  exit 2
}

[[ -f "$MANIFEST" ]] || {
  echo "[ERROR] validated manifest missing: $MANIFEST" >&2
  exit 2
}

# shellcheck disable=SC1090
source "$MANIFEST"

mkdir -p "$WS/src"

echo
echo "===== 1. PX4 EXACT REVISION ====="

if [[ ! -d "$PX4_DIR/.git" ]]; then
  echo "[clone] PX4-Autopilot -> $PX4_DIR"
  git clone https://github.com/PX4/PX4-Autopilot.git "$PX4_DIR"
fi

current_px4="$(git -C "$PX4_DIR" rev-parse HEAD)"

if [[ "$current_px4" != "$PX4_COMMIT" ]]; then
  if [[ -n "$(git -C "$PX4_DIR" status --porcelain --untracked-files=no)" ]]; then
    echo "[ERROR] PX4 has tracked local changes; refusing checkout" >&2
    exit 3
  fi

  git -C "$PX4_DIR" fetch origin "$PX4_COMMIT"
  git -C "$PX4_DIR" checkout --detach "$PX4_COMMIT"
fi

git -C "$PX4_DIR" submodule update --init --recursive

echo "[OK] PX4_COMMIT=$(git -C "$PX4_DIR" rev-parse HEAD)"

echo
echo "===== 2. PX4_MSGS EXACT REVISION ====="

if [[ ! -d "$PX4_MSGS_DIR/.git" ]]; then
  rm -rf "$PX4_MSGS_DIR"
  git clone https://github.com/PX4/px4_msgs.git "$PX4_MSGS_DIR"
fi

current_msgs="$(git -C "$PX4_MSGS_DIR" rev-parse HEAD)"

if [[ "$current_msgs" != "$PX4_MSGS_COMMIT" ]]; then
  if [[ -n "$(git -C "$PX4_MSGS_DIR" status --porcelain --untracked-files=no)" ]]; then
    echo "[ERROR] px4_msgs has tracked local changes; refusing checkout" >&2
    exit 3
  fi

  git -C "$PX4_MSGS_DIR" fetch origin "$PX4_MSGS_COMMIT"
  git -C "$PX4_MSGS_DIR" checkout --detach "$PX4_MSGS_COMMIT"
fi

echo "[OK] PX4_MSGS_COMMIT=$(git -C "$PX4_MSGS_DIR" rev-parse HEAD)"

echo
echo "===== 3. DISTRIBUTED SIMULATION ====="

[[ -d "$SIM_VENDOR" ]] || {
  echo "[ERROR] vendored simulation package missing: $SIM_VENDOR" >&2
  exit 2
}

if [[ -e "$SIM_LINK" && ! -L "$SIM_LINK" ]]; then
  echo "[INFO] existing simulation package kept: $SIM_LINK"
else
  rm -f "$SIM_LINK"
  ln -s "$SIM_VENDOR" "$SIM_LINK"
  echo "[OK] simulation package linked into workspace"
fi

[[ -d "$SIM_LINK/models/eletroquad_26" ]] || {
  echo "[ERROR] bundled eletroquad_26 assets missing" >&2
  exit 2
}

[[ -d "$SIM_LINK/models/harpia/LW20" ]] || {
  echo "[ERROR] bundled LW20 assets missing" >&2
  exit 2
}

[[ -d "$SIM_LINK/models/harpia/realsense_d435" ]] || {
  echo "[ERROR] bundled RealSense assets missing" >&2
  exit 2
}

echo
echo "===== 4. VALIDATED GARDEN BRIDGE ====="

HARPIA_WS="$WS" YOLO_REPO="$REPO" bash "$REPO/integration/harpia/runtime/install_garden_bridge.sh"

echo
echo "===== 5. MODEL CHECKSUM ====="

[[ -f "$MODEL" ]] || {
  echo "[ERROR] validated model missing: $MODEL" >&2
  exit 2
}

actual_sha="$(sha256sum "$MODEL" | awk '{print $1}')"

if [[ "$MODEL_SHA256" != "$actual_sha" ]]; then
  echo "[ERROR] model checksum mismatch" >&2
  echo "expected=$MODEL_SHA256" >&2
  echo "actual=$actual_sha" >&2
  exit 3
fi

echo "[OK] model checksum verified"

echo
echo "===== 6. PYTHON ENVIRONMENT ====="

VENV="${YOLO_VENV:-/root/yolo_venv}"

if [[ ! -x "$VENV/bin/python3" ]]; then
  echo "[INFO] creating ROS-aware Python venv: $VENV"
  python3 -m venv --system-site-packages "$VENV"
fi

"$VENV/bin/python3" -m pip install --upgrade pip
"$VENV/bin/python3" -m pip install -r "$REPO/requirements-ros2.txt"

if [[ -x "$VENV/bin/colcon" ]]; then
  COLCON_BIN="$VENV/bin/colcon"
elif command -v colcon >/dev/null 2>&1; then
  COLCON_BIN="$(command -v colcon)"
else
  "$VENV/bin/python3" -m pip install colcon-common-extensions
  COLCON_BIN="$VENV/bin/colcon"
fi

echo
echo "===== 7. ROS BUILD ====="

set +u
source /opt/ros/humble/setup.bash
set -u

cd "$WS"

"$COLCON_BIN" build   --packages-select   px4_msgs   simulation_bringup   yolo_person_interfaces   yolo_person_detector   yolo_person_mission   --symlink-install

echo
echo "[OK] workspace bootstrap complete"
