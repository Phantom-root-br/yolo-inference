#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
PX4="${PX4_DIR:-/root/PX4-Autopilot}"

echo "============================================================"
echo " HARPia :: LOCATE FINAL EXTERNAL ASSETS"
echo "============================================================"

echo
echo "===== 1. ELETROQUAD_26 ====="

SEARCH_ROOTS=(
  "/root/.gz"
  "/root/.ignition"
  "/root/.cache"
  "/root/harpia_ws"
  "/root/PX4-Autopilot"
  "/opt/ros/humble/share"
  "/usr/share"
)

FOUND_ELETRO=""

for root in "${SEARCH_ROOTS[@]}"; do
  [[ -d "$root" ]] || continue

  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    echo "[FOUND] $path"

    if [[ -z "$FOUND_ELETRO" ]]; then
      FOUND_ELETRO="$path"
    fi
  done < <(
    timeout -s KILL 20s       find "$root"         -type d         -name eletroquad_26         -print         2>/dev/null || true
  )
done

if [[ -z "$FOUND_ELETRO" ]]; then
  echo "[NOT FOUND] eletroquad_26"
else
  echo
  echo "ELETROQUAD_26_CANDIDATE=$FOUND_ELETRO"
  du -sh "$FOUND_ELETRO" 2>/dev/null || true

  echo "--- required children ---"
  for rel in     miscs/default_platform     miscs/takeoff_platform     miscs/ground_level     miscs/arenas/rectangle     bouncing/shapes/hexagon     bouncing/shapes/star     bouncing/shapes/triangle     bouncing/nums/num_3     bouncing/nums/num_4     bouncing/nums/num_5
  do
    if [[ -e "$FOUND_ELETRO/$rel" ]]; then
      echo "[OK] $rel"
    else
      echo "[MISSING] $rel"
    fi
  done
fi

echo
echo "===== 2. PX4 MODEL TRACKING ====="

for rel in   Tools/simulation/gz/models/x500   Tools/simulation/gz/models/harpia/LW20   Tools/simulation/gz/models/harpia/realsense_d435
do
  path="$PX4/$rel"

  if [[ ! -d "$path" ]]; then
    echo "[MISSING] $rel"
    continue
  fi

  echo "[FOUND] $rel"
  du -sh "$path" 2>/dev/null || true

  tracked="$(git -C "$PX4" ls-files "$rel" | wc -l)"
  untracked="$(git -C "$PX4" ls-files --others --exclude-standard "$rel" | wc -l)"

  echo "TRACKED_FILES=$tracked"
  echo "UNTRACKED_FILES=$untracked"
done

echo
echo "===== 3. GARDEN BRIDGE CACHE ====="

CACHE="/root/.cache/harpia/ros_gzgarden"
BIN="$CACHE/opt/ros/humble/lib/ros_gz_bridge/parameter_bridge"

if [[ -d "$CACHE" ]]; then
  echo "[FOUND] $CACHE"
  du -sh "$CACHE"

  echo "--- largest files ---"
  find "$CACHE" -type f -printf '%s %p\n' 2>/dev/null     | sort -nr     | head -n 30     | awk '{printf "%.2f MiB %s\n", $1/1048576, $2}'
else
  echo "[MISSING] $CACHE"
fi

if [[ -x "$BIN" ]]; then
  echo
  echo "--- parameter_bridge ---"
  sha256sum "$BIN"
  file "$BIN" || true

  echo "--- ldd ---"
  ldd "$BIN" 2>&1 || true
fi

echo
echo "===== 4. INSTALLED ROS-GZ PACKAGES ====="

dpkg-query -W   -f='${binary:Package} ${Version}\n'   'ros-humble-ros-gz*'   'ros-humble-ros-ign*'   2>/dev/null   | sort -u || true

echo
echo "===== 5. PX4 / PX4_MSGS REMOTES ====="

git -C "$PX4" remote -v 2>/dev/null || true
echo "PX4_COMMIT=$(git -C "$PX4" rev-parse HEAD 2>/dev/null || echo unknown)"

for p in   "$WS/src/px4_msgs"   "/root/px4_ws/src/px4_msgs"   "/root/px4_msgs"
do
  if [[ -d "$p/.git" ]]; then
    echo "--- $p"
    git -C "$p" remote -v || true
    echo "PX4_MSGS_COMMIT=$(git -C "$p" rev-parse HEAD)"
  fi
done
