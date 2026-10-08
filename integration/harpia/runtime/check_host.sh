#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo " HARPia :: HOST CHECK"
echo "============================================================"

fail=0

ok()   { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; }
bad()  { printf '[MISSING] %s\n' "$*" >&2; fail=1; }

for cmd in \
  git \
  bash \
  make \
  cmake \
  g++ \
  tmux \
  python3 \
  rsync \
  sha256sum \
  dpkg-deb \
  gz \
  ros2 \
  MicroXRCEAgent
do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd -> $(command -v "$cmd")"
  else
    bad "$cmd"
  fi
done

if [[ -f /opt/ros/humble/setup.bash ]]; then
  ok "ROS 2 Humble: /opt/ros/humble"
else
  bad "ROS 2 Humble at /opt/ros/humble"
fi

if command -v gz >/dev/null 2>&1; then
  gz_version="$(gz sim --version 2>&1 | head -n 1 || true)"
  echo "GZ_SIM_VERSION=$gz_version"

  if grep -Eq 'version[ _]7\.' <<<"$gz_version"; then
    ok "Gazebo Garden / gz-sim7"
  else
    warn "validated run used Gazebo Sim 7.9.0; detected: $gz_version"
  fi
fi

if python3 -m venv --help >/dev/null 2>&1; then
  ok "python3 venv module"
else
  bad "python3 venv module"
fi

if [[ -n "${DISPLAY:-}" ]]; then
  ok "DISPLAY=${DISPLAY}"
else
  warn "DISPLAY is unset; Gazebo and camera viewer will run without GUI"
fi

if command -v xclip >/dev/null 2>&1 || command -v wl-copy >/dev/null 2>&1; then
  ok "clipboard helper"
else
  warn "xclip/wl-copy missing; only log copy-to-clipboard is affected"
fi

echo

if (( fail != 0 )); then
  echo "HOST_READY=0"
  echo
  echo "Install the missing host-level robotics dependencies before running the demo."
  echo "The repository itself bootstraps the exact PX4/px4_msgs revisions,"
  echo "simulation assets, custom YOLO model, and validated Garden camera bridge."
  exit 2
fi

echo "HOST_READY=1"
