#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
SIM="$REPO/vendor/simulation_bringup_eletroquad26"
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

check_dir "$MISSION"
check_file "$MISSION/package.xml"
check_file "$MISSION/setup.py"
check_file "$MISSION/yolo_person_mission/person_mission_node.py"

check_dir "$SIM"
check_file "$SIM/package.xml"
check_file "$SIM/worlds/harpia_yolo_person.sdf"
check_file "$SIM/config/simulation/run_yolo_person.sh"
check_file "$SIM/config/simulation/wait_and_start_yolo_mission.sh"

check_file "$MODEL"
check_file "$MANIFEST"

if [[ -f "$MODEL" && -f "$MANIFEST" ]]; then
  # shellcheck disable=SC1090
  source "$MANIFEST"
  actual="$(sha256sum "$MODEL" | awk '{print $1}')"
  if [[ "$actual" == "${MODEL_SHA256:-}" ]]; then
    echo "[OK] model SHA256"
  else
    echo "[FAIL] model SHA256 mismatch"
    fail=1
  fi
fi

echo
echo "===== GIT TRACKING ====="

for path in   yolo_person_mission   vendor/simulation_bringup_eletroquad26   models/harpia_person_topdown_pilot_v2.pt   integration/harpia/repro/validated_stack.env
do
  if git -C "$REPO" ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    echo "[OK] tracked $path"
  else
    echo "[PENDING] not tracked yet: $path"
    fail=1
  fi
done

echo
echo "===== LARGE FILES ====="

large="$(
  find     "$MISSION"     "$SIM"     "$MODEL"     -type f     -size +95M     -print     2>/dev/null || true
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
