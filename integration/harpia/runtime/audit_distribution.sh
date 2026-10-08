#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
SIM="$REPO/vendor/simulation_bringup_eletroquad26"
BRIDGE_VENDOR="$REPO/vendor/ros_gzgarden"
MODEL="$REPO/models/harpia_person_topdown_pilot_v2.pt"
MISSION="$REPO/yolo_person_mission"
MANIFEST="$REPO/integration/harpia/repro/validated_stack.env"

echo "============================================================"
echo " HARPia :: DISTRIBUTION AUDIT"
echo "============================================================"

fail=0

check_file() {
  if [[ -f "$1" ]]; then
    echo "[OK] file $1"
  else
    echo "[FAIL] missing file $1"
    fail=1
  fi
}

check_dir() {
  if [[ -d "$1" ]]; then
    echo "[OK] dir  $1"
  else
    echo "[FAIL] missing dir $1"
    fail=1
  fi
}

tree_sha256() {
  local dir="$1"

  (
    cd "$dir"
    find . -type f -print0       | sort -z       | xargs -0 sha256sum
  ) | sha256sum | awk '{print $1}'
}

check_dir "$MISSION"
check_file "$MISSION/package.xml"
check_file "$MISSION/setup.py"
check_file "$MISSION/yolo_person_mission/person_mission_node.py"

check_dir "$SIM"
check_file "$SIM/package.xml"
check_file "$SIM/worlds/harpia_yolo_person.sdf"
check_file "$SIM/config/simulation/run_yolo_person.sh"
check_file "$SIM/config/simulation/start_px4_yolo_person.sh"
check_file "$SIM/config/simulation/start_garden_camera_bridge.sh"
check_file "$SIM/config/simulation/wait_and_start_yolo_mission.sh"

check_dir "$SIM/models/eletroquad_26"
check_dir "$SIM/models/harpia/LW20"
check_dir "$SIM/models/harpia/realsense_d435"

check_dir "$BRIDGE_VENDOR"
check_file "$MODEL"
check_file "$MANIFEST"

if [[ -f "$MANIFEST" ]]; then
  # shellcheck disable=SC1090
  source "$MANIFEST"

  echo
  echo "===== CHECKSUMS ====="

  actual="$(sha256sum "$MODEL" | awk '{print $1}')"

  if [[ "$actual" == "$MODEL_SHA256" ]]; then
    echo "[OK] model SHA256"
  else
    echo "[FAIL] model SHA256 mismatch"
    fail=1
  fi

  if [[ -d "$SIM/models/eletroquad_26" ]]; then
    actual="$(tree_sha256 "$SIM/models/eletroquad_26")"
    [[ "$actual" == "$ELETROQUAD_TREE_SHA256" ]]       && echo "[OK] eletroquad_26 tree SHA256"       || { echo "[FAIL] eletroquad_26 tree SHA256"; fail=1; }
  fi

  if [[ -d "$SIM/models/harpia/LW20" ]]; then
    actual="$(tree_sha256 "$SIM/models/harpia/LW20")"
    [[ "$actual" == "$LW20_TREE_SHA256" ]]       && echo "[OK] LW20 tree SHA256"       || { echo "[FAIL] LW20 tree SHA256"; fail=1; }
  fi

  if [[ -d "$SIM/models/harpia/realsense_d435" ]]; then
    actual="$(tree_sha256 "$SIM/models/harpia/realsense_d435")"
    [[ "$actual" == "$REALSENSE_TREE_SHA256" ]]       && echo "[OK] RealSense tree SHA256"       || { echo "[FAIL] RealSense tree SHA256"; fail=1; }
  fi

  BRIDGE_DEB_PATH="$BRIDGE_VENDOR/$GARDEN_BRIDGE_DEB"
  INTERFACES_DEB_PATH="$BRIDGE_VENDOR/$GARDEN_INTERFACES_DEB"

  check_file "$BRIDGE_DEB_PATH"
  check_file "$INTERFACES_DEB_PATH"

  if [[ -f "$BRIDGE_DEB_PATH" ]]; then
    actual="$(sha256sum "$BRIDGE_DEB_PATH" | awk '{print $1}')"
    [[ "$actual" == "$GARDEN_BRIDGE_DEB_SHA256" ]]       && echo "[OK] Garden bridge .deb SHA256"       || { echo "[FAIL] Garden bridge .deb SHA256"; fail=1; }
  fi

  if [[ -f "$INTERFACES_DEB_PATH" ]]; then
    actual="$(sha256sum "$INTERFACES_DEB_PATH" | awk '{print $1}')"
    [[ "$actual" == "$GARDEN_INTERFACES_DEB_SHA256" ]]       && echo "[OK] Garden interfaces .deb SHA256"       || { echo "[FAIL] Garden interfaces .deb SHA256"; fail=1; }
  fi
fi

echo
echo "===== GIT TRACKING ====="

for path in   yolo_person_mission   vendor/simulation_bringup_eletroquad26   vendor/ros_gzgarden   models/harpia_person_topdown_pilot_v2.pt   integration/harpia/repro/validated_stack.env
do
  if git -C "$REPO" ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    echo "[OK] tracked $path"
  else
    echo "[PENDING] not tracked yet: $path"
    fail=1
  fi
done

echo
echo "===== BACKUP / WORKSTATION JUNK ====="

backup_files="$(
  find "$SIM" -type f     \( -name '*.bak' -o -name '*.bak-*' -o -name '*.bak.*' \)     -print     2>/dev/null || true
)"

if [[ -n "$backup_files" ]]; then
  printf '%s\n' "$backup_files"
  echo "[FAIL] local backup files are present in distribution"
  fail=1
else
  echo "[OK] no local backup files"
fi

echo
echo "===== LARGE FILES ====="

large="$(
  find     "$MISSION"     "$SIM"     "$BRIDGE_VENDOR"     "$MODEL"     -type f     -size +95M     -print     2>/dev/null || true
)"

if [[ -n "$large" ]]; then
  printf '%s\n' "$large"
  echo "[FAIL] file exceeds 95 MB"
  fail=1
else
  echo "[OK] no file exceeds 95 MB"
fi

echo
echo "===== README ENTRYPOINT ====="

if grep -q 'run_from_zero.sh' "$REPO/README.md"; then
  echo "[OK] README points to run_from_zero.sh"
else
  echo "[FAIL] README missing one-command entrypoint"
  fail=1
fi

if (( fail != 0 )); then
  echo
  echo "DISTRIBUTION_READY=0"
  exit 4
fi

echo
echo "DISTRIBUTION_READY=1"
