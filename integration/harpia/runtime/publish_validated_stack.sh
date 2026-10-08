#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
SOURCE_REPO="${HARPIA_SOURCE_REPO:-$WS/src/yolo-inference}"
MISSION_SRC="${HARPIA_MISSION_SRC:-$SOURCE_REPO/yolo_person_mission}"
SIM_SRC="${HARPIA_SIM_SRC:-$WS/src/simulation_bringup_eletroquad26}"
MODEL_SRC="${HARPIA_MODEL_SRC:-$SOURCE_REPO/models/harpia_person_topdown_pilot_v2.pt}"

REMOTE="${HARPIA_GIT_REMOTE:-origin}"
REMOTE_BRANCH="${HARPIA_REPRO_BRANCH:-reproducible-harpia-demo}"
STAMP="$(date +%Y%m%d-%H%M%S)"
STAGE="${HARPIA_REPRO_STAGE:-/tmp/harpia_repro_worktree_$STAMP}"
TEMP_BRANCH="harpia-repro-stage-$STAMP"

fail() {
  echo "[ERROR] $*" >&2
  exit 2
}

cleanup() {
  if [[ -d "$STAGE" ]]; then
    git -C "$SOURCE_REPO" worktree remove --force "$STAGE" >/dev/null 2>&1 || true
  fi
  git -C "$SOURCE_REPO" branch -D "$TEMP_BRANCH" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "============================================================"
echo " HARPia :: PUBLISH VALIDATED STACK"
echo "============================================================"
echo "source repo : $SOURCE_REPO"
echo "mission     : $MISSION_SRC"
echo "simulation  : $SIM_SRC"
echo "model       : $MODEL_SRC"
echo "remote      : $REMOTE"
echo "branch      : $REMOTE_BRANCH"
echo

[[ -d "$SOURCE_REPO/.git" ]] || fail "source repository not found: $SOURCE_REPO"
[[ -d "$MISSION_SRC" ]] || fail "mission package not found: $MISSION_SRC"
[[ -d "$SIM_SRC" ]] || fail "simulation package not found: $SIM_SRC"
[[ -f "$MODEL_SRC" ]] || fail "validated model not found: $MODEL_SRC"

echo "===== SOURCE WORKTREE STATUS (READ ONLY) ====="
git -C "$SOURCE_REPO" status --short || true

echo
echo "===== FETCH MAIN ====="
git -C "$SOURCE_REPO" fetch "$REMOTE" main

BASE_REF="$REMOTE/main"

if git -C "$SOURCE_REPO" ls-remote --exit-code --heads "$REMOTE" "$REMOTE_BRANCH" >/dev/null 2>&1; then
  fail "remote branch already exists: $REMOTE_BRANCH. Audit/merge it instead of overwriting it."
fi

echo
echo "===== ISOLATED CLEAN WORKTREE ====="
rm -rf "$STAGE"
git -C "$SOURCE_REPO" worktree add --detach "$STAGE" "$BASE_REF"
git -C "$STAGE" switch -c "$TEMP_BRANCH"

echo
echo "===== PACKAGE EXACT LOCAL VALIDATED ARTIFACTS ====="

HARPIA_WS="$WS" YOLO_REPO="$STAGE" HARPIA_MISSION_SRC="$MISSION_SRC" HARPIA_SIM_SRC="$SIM_SRC" HARPIA_MODEL_SRC="$MODEL_SRC" bash "$STAGE/integration/harpia/runtime/package_validated_stack.sh"

echo
echo "===== STAGE ONLY REQUIRED DISTRIBUTION FILES ====="

git -C "$STAGE" add   yolo_person_mission   vendor/simulation_bringup_eletroquad26   models/harpia_person_topdown_pilot_v2.pt   integration/harpia/repro/validated_stack.env

echo
git -C "$STAGE" status --short

if git -C "$STAGE" diff --cached --quiet; then
  fail "nothing was staged; expected validated artifacts are already identical to main"
fi

echo
echo "===== COMMIT ====="

git -C "$STAGE" commit   -m "repro(harpia): publish validated mission simulation stack"

COMMIT_SHA="$(git -C "$STAGE" rev-parse HEAD)"

echo "COMMIT_SHA=$COMMIT_SHA"

echo
echo "===== PUSH ====="

git -C "$STAGE" push   -u   "$REMOTE"   "HEAD:refs/heads/$REMOTE_BRANCH"

echo
echo "===== POST-PUSH AUDIT ====="

HARPIA_WS="$WS" YOLO_REPO="$STAGE" bash "$STAGE/integration/harpia/runtime/audit_distribution.sh"

echo
echo "[OK] validated stack published without modifying the dirty source worktree"
echo "REMOTE_BRANCH=$REMOTE_BRANCH"
echo "COMMIT_SHA=$COMMIT_SHA"
