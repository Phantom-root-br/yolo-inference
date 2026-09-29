#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LATEST="$(find logs -maxdepth 1 -type f -name 'video_poc_*.log' -printf '%T@ %p\n' 2>/dev/null \
  | sort -nr \
  | head -n 1 \
  | cut -d' ' -f2-)"

if [[ -z "$LATEST" ]]; then
  echo "Nenhum log video_poc_*.log encontrado em logs/." >&2
  exit 1
fi

echo "Acompanhando: $LATEST"
echo "Ctrl+C encerra apenas o acompanhamento; não mata o detector em outro terminal."
tail -n 40 -f "$LATEST"
