#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
PX4_DIR="${PX4_DIR:-/root/PX4-Autopilot}"

SIM_SRC="${HARPIA_SIM_SRC:-$WS/src/simulation_bringup_eletroquad26}"
MISSION_SRC="${HARPIA_MISSION_SRC:-$REPO/yolo_person_mission}"
MODEL_SRC="${HARPIA_MODEL_SRC:-$REPO/models/harpia_person_topdown_pilot_v2.pt}"

ELETROQUAD_SRC="${HARPIA_ELETROQUAD_SRC:-$PX4_DIR/Tools/simulation/gz/worlds/models/eletroquad_26}"
LW20_SRC="${HARPIA_LW20_SRC:-$PX4_DIR/Tools/simulation/gz/models/harpia/LW20}"
REALSENSE_SRC="${HARPIA_REALSENSE_SRC:-$PX4_DIR/Tools/simulation/gz/models/harpia/realsense_d435}"
BRIDGE_CACHE_SRC="${HARPIA_GARDEN_CACHE_SRC:-/root/.cache/harpia/ros_gzgarden}"

VENDOR_DIR="$REPO/vendor/simulation_bringup_eletroquad26"
BRIDGE_VENDOR="$REPO/vendor/ros_gzgarden"
MISSION_DST="$REPO/yolo_person_mission"
MODEL_DST="$REPO/models/harpia_person_topdown_pilot_v2.pt"
MANIFEST_DIR="$REPO/integration/harpia/repro"
MANIFEST="$MANIFEST_DIR/validated_stack.env"

fail() {
  echo "[ERROR] $*" >&2
  exit 2
}

same_path() {
  [[ "$(readlink -f "$1")" == "$(readlink -f "$2")" ]]
}

tree_sha256() {
  local dir="$1"

  (
    cd "$dir"
    find . -type f -print0       | sort -z       | xargs -0 sha256sum
  ) | sha256sum | awk '{print $1}'
}

git_rev_or_unknown() {
  local dir="$1"

  if git -C "$dir" rev-parse HEAD >/dev/null 2>&1; then
    git -C "$dir" rev-parse HEAD
  else
    printf 'unknown\n'
  fi
}

echo "============================================================"
echo " HARPia :: PACKAGE VALIDATED STACK V2"
echo "============================================================"

for path in   "$SIM_SRC"   "$MISSION_SRC"   "$ELETROQUAD_SRC"   "$LW20_SRC"   "$REALSENSE_SRC"   "$BRIDGE_CACHE_SRC"
do
  [[ -d "$path" ]] || fail "required source directory missing: $path"
done

[[ -f "$MODEL_SRC" ]] || fail "model not found: $MODEL_SRC"

for cmd in rsync sha256sum dpkg-deb; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done

mkdir -p "$REPO/vendor" "$REPO/models" "$MANIFEST_DIR"

echo
echo "===== 1. COPY EXACT MISSION PACKAGE ====="

if same_path "$MISSION_SRC" "$MISSION_DST"; then
  echo "[OK] mission already inside target repository"
else
  rm -rf "$MISSION_DST"
  mkdir -p "$MISSION_DST"

  rsync -a     --delete     --exclude='__pycache__/'     --exclude='.pytest_cache/'     --exclude='*.pyc'     "$MISSION_SRC/"     "$MISSION_DST/"

  echo "[OK] mission copied: $MISSION_DST"
fi

echo
echo "===== 2. VENDOR SIMULATION PACKAGE ====="

rm -rf "$VENDOR_DIR"

rsync -a   --exclude='.git/'   --exclude='build/'   --exclude='install/'   --exclude='log/'   --exclude='__pycache__/'   --exclude='.pytest_cache/'   --exclude='.cache/'   --exclude='*.bak'   --exclude='*.bak-*'   --exclude='*.bak.*'   "$SIM_SRC/"   "$VENDOR_DIR/"

echo "[OK] simulation package copied"

echo
echo "===== 3. VENDOR HIDDEN GAZEBO ASSETS ====="

mkdir -p "$VENDOR_DIR/models/harpia"

rm -rf   "$VENDOR_DIR/models/eletroquad_26"   "$VENDOR_DIR/models/harpia/LW20"   "$VENDOR_DIR/models/harpia/realsense_d435"

rsync -a "$ELETROQUAD_SRC/" "$VENDOR_DIR/models/eletroquad_26/"
rsync -a "$LW20_SRC/" "$VENDOR_DIR/models/harpia/LW20/"
rsync -a "$REALSENSE_SRC/" "$VENDOR_DIR/models/harpia/realsense_d435/"

echo "[OK] eletroquad_26"
echo "[OK] harpia/LW20"
echo "[OK] harpia/realsense_d435"

echo
echo "===== 4. NORMALIZE VALIDATED STARTUP ====="

PX4_START="$VENDOR_DIR/config/simulation/start_px4_yolo_person.sh"

python3 - "$PX4_START" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

old = "source /root/ros_gz_garden_ws/install/setup.bash"
new = (
    "if [ -f /root/ros_gz_garden_ws/install/setup.bash ]; then\n"
    "  source /root/ros_gz_garden_ws/install/setup.bash\n"
    "fi"
)

if old in text:
    text = text.replace(old, new)

path.write_text(text)
PY

echo "[OK] missing Garden overlay is no longer fatal/noisy"

echo
echo "===== 5. VENDOR EXACT GARDEN BRIDGE PACKAGES ====="

rm -rf "$BRIDGE_VENDOR"
mkdir -p "$BRIDGE_VENDOR"

shopt -s nullglob
bridge_debs=("$BRIDGE_CACHE_SRC"/ros-humble-ros-gzgarden-bridge_*.deb)
interface_debs=("$BRIDGE_CACHE_SRC"/ros-humble-ros-gzgarden-interfaces_*.deb)
shopt -u nullglob

(( ${#bridge_debs[@]} == 1 ))   || fail "expected exactly one ros-gzgarden-bridge .deb"

(( ${#interface_debs[@]} == 1 ))   || fail "expected exactly one ros-gzgarden-interfaces .deb"

cp -f "${bridge_debs[0]}" "$BRIDGE_VENDOR/"
cp -f "${interface_debs[0]}" "$BRIDGE_VENDOR/"

BRIDGE_DEB="$BRIDGE_VENDOR/$(basename "${bridge_debs[0]}")"
INTERFACES_DEB="$BRIDGE_VENDOR/$(basename "${interface_debs[0]}")"

echo "[OK] $(basename "$BRIDGE_DEB")"
echo "[OK] $(basename "$INTERFACES_DEB")"

echo
echo "===== 6. COPY VALIDATED MODEL ====="

if same_path "$MODEL_SRC" "$MODEL_DST"; then
  echo "[OK] model already inside target repository"
else
  cp -f "$MODEL_SRC" "$MODEL_DST"
fi

MODEL_SIZE="$(stat -c '%s' "$MODEL_DST")"
MODEL_SHA="$(sha256sum "$MODEL_DST" | awk '{print $1}')"

if (( MODEL_SIZE >= 95000000 )); then
  fail "model is >=95 MB; use a Release asset or Git LFS"
fi

echo "MODEL_SIZE_BYTES=$MODEL_SIZE"
echo "MODEL_SHA256=$MODEL_SHA"

echo
echo "===== 7. ENVIRONMENT FREEZE ====="

PX4_COMMIT="$(git_rev_or_unknown "$PX4_DIR")"
SIM_COMMIT="$(git_rev_or_unknown "$SIM_SRC")"

PX4_MSGS_SRC="${PX4_MSGS_DIR:-}"

if [[ -z "$PX4_MSGS_SRC" ]]; then
  for p in     "$WS/src/px4_msgs"     "/root/px4_ws/src/px4_msgs"     "/root/px4_msgs"
  do
    if [[ -d "$p" ]]; then
      PX4_MSGS_SRC="$p"
      break
    fi
  done
fi

PX4_MSGS_COMMIT="unknown"

if [[ -n "$PX4_MSGS_SRC" ]]; then
  PX4_MSGS_COMMIT="$(git_rev_or_unknown "$PX4_MSGS_SRC")"
fi

ROS_DISTRO_VALUE="${ROS_DISTRO:-humble}"
PYTHON_VERSION="$(python3 --version 2>&1 | tr ' ' '_')"

if command -v gz >/dev/null 2>&1; then
  GZ_VERSION="$(gz sim --version 2>&1 | head -n 1 | tr ' ' '_')"
else
  GZ_VERSION="unknown"
fi

GARDEN_PARAMETER_BRIDGE="$BRIDGE_CACHE_SRC/opt/ros/humble/lib/ros_gz_bridge/parameter_bridge"

[[ -x "$GARDEN_PARAMETER_BRIDGE" ]]   || fail "validated Garden parameter_bridge missing"

GARDEN_PARAMETER_BRIDGE_SHA256="$(sha256sum "$GARDEN_PARAMETER_BRIDGE" | awk '{print $1}')"
BRIDGE_DEB_SHA256="$(sha256sum "$BRIDGE_DEB" | awk '{print $1}')"
INTERFACES_DEB_SHA256="$(sha256sum "$INTERFACES_DEB" | awk '{print $1}')"

ELETROQUAD_TREE_SHA256="$(tree_sha256 "$VENDOR_DIR/models/eletroquad_26")"
LW20_TREE_SHA256="$(tree_sha256 "$VENDOR_DIR/models/harpia/LW20")"
REALSENSE_TREE_SHA256="$(tree_sha256 "$VENDOR_DIR/models/harpia/realsense_d435")"

cat > "$MANIFEST" <<EOF
# Frozen from the workstation that passed the 2026-10-07 end-to-end run.
HARPIA_VALIDATED_DATE=2026-10-07
ROS_DISTRO=$ROS_DISTRO_VALUE
PYTHON_VERSION=$PYTHON_VERSION
GZ_SIM_VERSION=$GZ_VERSION
PX4_COMMIT=$PX4_COMMIT
PX4_MSGS_COMMIT=$PX4_MSGS_COMMIT
SIMULATION_SOURCE_COMMIT=$SIM_COMMIT
MODEL_FILE=models/harpia_person_topdown_pilot_v2.pt
MODEL_SIZE_BYTES=$MODEL_SIZE
MODEL_SHA256=$MODEL_SHA
ELETROQUAD_TREE_SHA256=$ELETROQUAD_TREE_SHA256
LW20_TREE_SHA256=$LW20_TREE_SHA256
REALSENSE_TREE_SHA256=$REALSENSE_TREE_SHA256
GARDEN_BRIDGE_DEB=$(basename "$BRIDGE_DEB")
GARDEN_BRIDGE_DEB_SHA256=$BRIDGE_DEB_SHA256
GARDEN_INTERFACES_DEB=$(basename "$INTERFACES_DEB")
GARDEN_INTERFACES_DEB_SHA256=$INTERFACES_DEB_SHA256
GARDEN_PARAMETER_BRIDGE_SHA256=$GARDEN_PARAMETER_BRIDGE_SHA256
WORLD_FILE=harpia_yolo_person.sdf
TMUX_SESSION=HarpiaYolo
EOF

cat "$MANIFEST"

echo
echo "===== 8. DISTRIBUTION SIZE ====="

du -sh   "$VENDOR_DIR"   "$BRIDGE_VENDOR"   "$MISSION_DST"   "$MODEL_DST"

echo
echo "===== 9. LARGE-FILE GATE ====="

LARGE_LIST="$(
  find     "$VENDOR_DIR"     "$BRIDGE_VENDOR"     "$MISSION_DST"     "$MODEL_DST"     -type f     -size +95M     -print     2>/dev/null || true
)"

if [[ -n "$LARGE_LIST" ]]; then
  printf '%s\n' "$LARGE_LIST"
  fail "one or more files exceed 95 MB"
fi

echo "[OK] no file exceeds 95 MB"

echo
echo "===== 10. REQUIRED PATHS ====="

required=(
  "$MISSION_DST/package.xml"
  "$MISSION_DST/setup.py"
  "$MISSION_DST/yolo_person_mission/person_mission_node.py"
  "$VENDOR_DIR/package.xml"
  "$VENDOR_DIR/worlds/harpia_yolo_person.sdf"
  "$VENDOR_DIR/config/simulation/run_yolo_person.sh"
  "$VENDOR_DIR/config/simulation/wait_and_start_yolo_mission.sh"
  "$VENDOR_DIR/models/eletroquad_26/miscs/default_platform"
  "$VENDOR_DIR/models/harpia/LW20/model.sdf"
  "$VENDOR_DIR/models/harpia/realsense_d435/model.sdf"
  "$MODEL_DST"
  "$BRIDGE_DEB"
  "$INTERFACES_DEB"
  "$MANIFEST"
)

missing=0

for path in "${required[@]}"; do
  if [[ -e "$path" ]]; then
    echo "[OK] $path"
  else
    echo "[MISSING] $path"
    missing=1
  fi
done

(( missing == 0 )) || fail "validated-stack package is incomplete"

echo
echo "[OK] validated stack V2 staged inside target repository/worktree"
