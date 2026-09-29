#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-full}"
PYTHON="${HARPIA_PYTHON:-/root/yolo_venv/bin/python}"
INPUT="${HARPIA_YOLO_INPUT:-input/people_cc.mp4}"

case "$MODE" in
  full)
    OUTPUT="output/yolo11n_people.mp4"
    METRICS="results/yolo11n_metrics.json"
    EXTRA_ARGS=(--examples 3 --examples-dir results/examples)
    ;;
  test)
    OUTPUT="output/yolo11n_test60.mp4"
    METRICS="results/yolo11n_test60_metrics.json"
    EXTRA_ARGS=(--max-frames 60 --examples 0)
    ;;
  *)
    echo "Uso: $0 [full|test]" >&2
    exit 2
    ;;
esac

if [[ ! -x "$PYTHON" ]]; then
  echo "ERRO: Python do YOLO não executável: $PYTHON" >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "ERRO: vídeo de entrada não encontrado: $INPUT" >&2
  echo "Execute ./scripts/download_video.sh primeiro." >&2
  exit 1
fi

mkdir -p logs output results/examples
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="logs/video_poc_${MODE}_${STAMP}.log"
REPORT="output/video_report.html"

echo "============================================================" | tee "$LOG"
echo " HARPia - YOLO VIDEO POC" | tee -a "$LOG"
echo " Modo: $MODE" | tee -a "$LOG"
echo " Data: $(date)" | tee -a "$LOG"
echo " Python: $PYTHON" | tee -a "$LOG"
echo " Entrada: $INPUT" | tee -a "$LOG"
echo " Saída: $OUTPUT" | tee -a "$LOG"
echo " Métricas: $METRICS" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"

set +e
"$PYTHON" scripts/detect_people.py \
  --input "$INPUT" \
  --output "$OUTPUT" \
  --model yolo11n.pt \
  --imgsz 640 \
  --conf 0.25 \
  --device cpu \
  --metrics "$METRICS" \
  --progress-every 30 \
  "${EXTRA_ARGS[@]}" 2>&1 | tee -a "$LOG"
STATUS=${PIPESTATUS[0]}
set -e

if [[ "$STATUS" -ne 0 ]]; then
  echo "ERRO: detector terminou com código $STATUS" | tee -a "$LOG"
  if command -v harpia-copylog >/dev/null 2>&1; then
    harpia-copylog "$LOG" || true
  fi
  exit "$STATUS"
fi

"$PYTHON" scripts/video_report.py \
  --metrics "$METRICS" \
  --comparison results/comparison.csv \
  --source results/video_source.json \
  --video "$OUTPUT" \
  --log "$LOG" \
  --output "$REPORT" 2>&1 | tee -a "$LOG"

echo | tee -a "$LOG"
echo "Execução concluída." | tee -a "$LOG"
echo "Log: $LOG" | tee -a "$LOG"
echo "Painel: $REPORT" | tee -a "$LOG"
echo "Para acompanhar outro run: ./scripts/watch_video_log.sh" | tee -a "$LOG"

if command -v harpia-copylog >/dev/null 2>&1; then
  harpia-copylog "$LOG" || true
fi
