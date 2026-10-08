#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
SIM_SRC="${HARPIA_SIM_SRC:-$WS/src/simulation_bringup_eletroquad26}"
MISSION_SRC="${HARPIA_MISSION_SRC:-$REPO/yolo_person_mission}"
MODEL_SRC="${HARPIA_MODEL_SRC:-$REPO/models/harpia_person_topdown_pilot_v2.pt}"

VENDOR_DIR="$REPO/vendor/simulation_bringup_eletroquad26"
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

echo "============================================================"
echo " HARPia :: PACKAGE VALIDATED STACK"
echo "============================================================"

[[ -d "$REPO/.git" || -f "$REPO/.git" ]] || fail "repository/worktree not found: $REPO"
[[ -d "$SIM_SRC" ]] || fail "simulation source not found: $SIM_SRC"
[[ -d "$MISSION_SRC" ]] || fail "mission package not found: $MISSION_SRC"
[[ -f "$MODEL_SRC" ]] || fail "model not found: $MODEL_SRC"

command -v rsync >/dev/null 2>&1 || fail "rsync is required"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required"

mkdir -p "$REPO/vendor"
mkdir -p "$REPO/models"
mkdir -p "$MANIFEST_DIR"

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
echo "===== 2. VENDOR EXACT SIMULATION PACKAGE ====="

rm -rf "$VENDOR_DIR"

rsync -a   --exclude='.git/'   --exclude='build/'   --exclude='install/'   --exclude='log/'   --exclude='__pycache__/'   --exclude='.pytest_cache/'   --exclude='.cache/'   --exclude='*.bak'   --exclude='*.bak-*'   --exclude='*.bak.*'   "$SIM_SRC/"   "$VENDOR_DIR/"

echo "[OK] vendored: $VENDOR_DIR"

echo
echo "===== 3. COPY VALIDATED MODEL ====="

if same_path "$MODEL_SRC" "$MODEL_DST"; then
  echo "[OK] model already inside target repository"
else
  cp -f "$MODEL_SRC" "$MODEL_DST"
  echo "[OK] model copied: $MODEL_DST"
fi

MODEL_SIZE="$(stat -c '%s' "$MODEL_DST")"
MODEL_SHA="$(sha256sum "$MODEL_DST" | awk '{print $1}')"

echo "model_size_bytes=$MODEL_SIZE"
echo "model_sha256=$MODEL_SHA"

if (( MODEL_SIZE >= 95000000 )); then
  fail "model is >=95 MB; use a Release asset or Git LFS instead of normal Git"
fi

echo
echo "===== 4. ENVIRONMENT FREEZE ====="

PX4_DIR="${PX4_DIR:-/root/PX4-Autopilot}"

git_rev_or_unknown() {
  local dir="$1"

  if git -C "$dir" rev-parse HEAD >/dev/null 2>&1; then
    git -C "$dir" rev-parse HEAD
  else
    printf 'unknown\n'
  fi
}

PX4_COMMIT="$(git_rev_or_unknown "$PX4_DIR")"
SIM_COMMIT="$(git_rev_or_unknown "$SIM_SRC")"

ROS_DISTRO_VALUE="${ROS_DISTRO:-humble}"
PYTHON_VERSION="$(python3 --version 2>&1 | tr ' ' '_')"

if command -v gz >/dev/null 2>&1; then
  GZ_VERSION="$(gz sim --version 2>&1 | head -n 1 | tr ' ' '_')"
else
  GZ_VERSION="unknown"
fi

cat > "$MANIFEST" <<EOF
# Generated from the workstation that passed the 2026-10-07 end-to-end run.
HARPIA_VALIDATED_DATE=2026-10-07
ROS_DISTRO=$ROS_DISTRO_VALUE
PYTHON_VERSION=$PYTHON_VERSION
GZ_SIM_VERSION=$GZ_VERSION
PX4_COMMIT=$PX4_COMMIT
SIMULATION_SOURCE_COMMIT=$SIM_COMMIT
MODEL_FILE=models/harpia_person_topdown_pilot_v2.pt
MODEL_SIZE_BYTES=$MODEL_SIZE
MODEL_SHA256=$MODEL_SHA
WORLD_FILE=harpia_yolo_person.sdf
TMUX_SESSION=HarpiaYolo
EOF

cat "$MANIFEST"

echo
echo "===== 5. DISTRIBUTION SIZE ====="

du -sh "$VENDOR_DIR" "$MISSION_DST" "$MODEL_DST"

echo
echo "===== 6. LARGE-FILE GATE ====="

LARGE_LIST="$(
  find     "$VENDOR_DIR"     "$MISSION_DST"     "$MODEL_DST"     -type f     -size +95M     -print     2>/dev/null || true
)"

if [[ -n "$LARGE_LIST" ]]; then
  printf '%s\n' "$LARGE_LIST"
  fail "one or more files exceed the normal GitHub 100 MB file limit"
fi

echo "[OK] no file exceeds 95 MB"

echo
echo "===== 7. REQUIRED PATHS ====="

required=(
  "$MISSION_DST/package.xml"
  "$MISSION_DST/setup.py"
  "$MISSION_DST/yolo_person_mission/person_mission_node.py"
  "$VENDOR_DIR/package.xml"
  "$VENDOR_DIR/worlds/harpia_yolo_person.sdf"
  "$VENDOR_DIR/config/simulation/run_yolo_person.sh"
  "$VENDOR_DIR/config/simulation/wait_and_start_yolo_mission.sh"
  "$MODEL_DST"
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

if (( missing != 0 )); then
  fail "validated-stack package is incomplete"
fi

echo
echo "[OK] validated stack staged inside target repository/worktree"
echo
echo "Next:"
echo "  bash integration/harpia/runtime/audit_distribution.sh"
