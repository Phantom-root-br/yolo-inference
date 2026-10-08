#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
BRANCH="${HARPIA_REPRO_BRANCH:-reproducible-harpia-demo}"

echo "============================================================"
echo " HARPia :: PUBLISH VALIDATED STACK"
echo "============================================================"

cd "$REPO"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "[ERROR] tracked local modifications exist." >&2
  echo "Commit/stash them before publishing the reproducibility bundle." >&2
  git status --short >&2
  exit 2
fi

git fetch origin main

current="$(git branch --show-current)"

if [[ "$current" != "$BRANCH" ]]; then
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git switch "$BRANCH"
    git merge --ff-only origin/main
  else
    git switch -c "$BRANCH" origin/main
  fi
fi

bash integration/harpia/runtime/package_validated_stack.sh

git add   yolo_person_mission   vendor/simulation_bringup_eletroquad26   models/harpia_person_topdown_pilot_v2.pt   integration/harpia/repro/validated_stack.env

echo
echo "===== STAGED FILES ====="
git status --short

if git diff --cached --quiet; then
  echo "[INFO] nothing new to commit"
else
  git commit -m "repro(harpia): publish validated mission simulation stack"
fi

git push -u origin "$BRANCH"

echo
echo "[OK] published branch: $BRANCH"
echo "Next: audit/merge this branch after GitHub checks pass."
