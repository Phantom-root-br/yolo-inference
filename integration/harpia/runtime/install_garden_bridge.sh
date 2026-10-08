#!/usr/bin/env bash
set -euo pipefail

WS="${HARPIA_WS:-/root/harpia_ws}"
REPO="${YOLO_REPO:-$WS/src/yolo-inference}"
CACHE="${HARPIA_GARDEN_CACHE:-/root/.cache/harpia/ros_gzgarden}"
VENDOR="$REPO/vendor/ros_gzgarden"
MANIFEST="$REPO/integration/harpia/repro/validated_stack.env"
BIN="$CACHE/opt/ros/humble/lib/ros_gz_bridge/parameter_bridge"

echo "============================================================"
echo " HARPia :: INSTALL VALIDATED GARDEN BRIDGE"
echo "============================================================"

[[ -d "$VENDOR" ]] || {
  echo "[ERROR] vendored Garden bridge packages missing: $VENDOR" >&2
  exit 2
}

command -v dpkg-deb >/dev/null 2>&1 || {
  echo "[ERROR] dpkg-deb not found" >&2
  exit 2
}

shopt -s nullglob
debs=("$VENDOR"/*.deb)
shopt -u nullglob

if (( ${#debs[@]} < 2 )); then
  echo "[ERROR] expected bridge + interfaces .deb files in $VENDOR" >&2
  exit 2
fi

rm -rf "$CACHE"
mkdir -p "$CACHE"

for deb in "${debs[@]}"; do
  echo "[extract] $(basename "$deb")"
  dpkg-deb -x "$deb" "$CACHE"
done

[[ -x "$BIN" ]] || {
  echo "[ERROR] parameter_bridge missing after extraction: $BIN" >&2
  exit 3
}

if [[ -f "$MANIFEST" ]]; then
  # shellcheck disable=SC1090
  source "$MANIFEST"

  actual="$(sha256sum "$BIN" | awk '{print $1}')"

  if [[ -n "${GARDEN_PARAMETER_BRIDGE_SHA256:-}" &&
        "$actual" != "$GARDEN_PARAMETER_BRIDGE_SHA256" ]]; then
    echo "[ERROR] Garden parameter_bridge checksum mismatch" >&2
    echo "expected=$GARDEN_PARAMETER_BRIDGE_SHA256" >&2
    echo "actual=$actual" >&2
    exit 4
  fi

  echo "[OK] parameter_bridge SHA256 verified"
fi

echo "[OK] validated Garden bridge installed at $CACHE"
