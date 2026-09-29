#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="https://www.youtube.com/watch?v=OEFv_pvFQyk"
OUTPUT="$REPO_DIR/input/people_cc.mp4"

if [[ -n "${YT_DLP:-}" ]]; then
  YTDLP_BIN="$YT_DLP"
elif command -v yt-dlp >/dev/null 2>&1; then
  YTDLP_BIN="$(command -v yt-dlp)"
elif [[ -x /root/yolo_venv/bin/yt-dlp ]]; then
  YTDLP_BIN="/root/yolo_venv/bin/yt-dlp"
else
  echo "ERRO: yt-dlp não encontrado." >&2
  echo "Defina YT_DLP=/caminho/para/yt-dlp ou instale-o no ambiente Python isolado." >&2
  exit 1
fi

mkdir -p "$REPO_DIR/input"

echo "============================================================"
echo " HARPia - DOWNLOAD DO VIDEO DA POC"
echo "============================================================"
echo "Fonte : $URL"
echo "Saída : $OUTPUT"
echo "yt-dlp: $YTDLP_BIN"
echo

"$YTDLP_BIN" \
  --no-playlist \
  --no-overwrites \
  -f 'bestvideo[ext=mp4][height<=720]/best[ext=mp4][height<=720]/best[height<=720]' \
  -o "$OUTPUT" \
  "$URL"

echo
ls -lh "$OUTPUT"

echo
printf '%s\n' "Download concluído. O vídeo é ignorado pelo Git e não será versionado."
