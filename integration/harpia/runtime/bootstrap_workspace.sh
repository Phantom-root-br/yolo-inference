#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
SIM_VENDOR="$REPO/vendor/simulation_bringup_eletroquad26"
SIM_LINK="$WS/src/simulation_bringup_eletroquad26"
MODEL="$REPO/models/harpia_person_topdown_pilot_v2.pt"
MANIFEST="$REPO/integration/harpia/repro/validated_stack.env"

echo "============================================================"
echo " HARPia :: BOOTSTRAP WORKSPACE"
echo "============================================================"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "[ERROR] ROS 2 Humble is required at /opt/ros/humble" >&2
  exit 2
fi

mkdir -p "$WS/src"

if [[ ! -d "$SIM_VENDOR" ]]; then
  echo "[ERROR] vendored simulation package is missing:" >&2
  echo "        $SIM_VENDOR" >&2
  exit 2
fi

if [[ -e "$SIM_LINK" && ! -L "$SIM_LINK" ]]; then
  echo "[INFO] existing simulation package kept: $SIM_LINK"
else
  rm -f "$SIM_LINK"
  ln -s "$SIM_VENDOR" "$SIM_LINK"
  echo "[OK] simulation package linked into workspace"
fi

if [[ ! -d "$REPO/yolo_person_mission" ]]; then
  echo "[ERROR] yolo_person_mission is missing from the repository" >&2
  exit 2
fi

if [[ ! -f "$MODEL" ]]; then
  echo "[ERROR] validated model is missing: $MODEL" >&2
  exit 2
fi

if [[ -f "$MANIFEST" ]]; then
  # shellcheck disable=SC1090
  source "$MANIFEST"

  actual_sha="$(sha256sum "$MODEL" | awk '{print $1}')"

  if [[ "${MODEL_SHA256:-}" != "$actual_sha" ]]; then
    echo "[ERROR] model checksum mismatch" >&2
    echo "expected=${MODEL_SHA256:-missing}" >&2
    echo "actual=$actual_sha" >&2
    exit 3
  fi

  echo "[OK] model checksum verified"
fi

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
  echo "[INFO] installing colcon into YOLO venv"
  "$VENV/bin/python3" -m pip install colcon-common-extensions
  COLCON_BIN="$VENV/bin/colcon"
fi

set +u
source /opt/ros/humble/setup.bash
set -u

cd "$WS"

"$COLCON_BIN" build   --packages-select   simulation_bringup   yolo_person_interfaces   yolo_person_detector   yolo_person_mission   --symlink-install

echo
echo "[OK] workspace bootstrap complete"
