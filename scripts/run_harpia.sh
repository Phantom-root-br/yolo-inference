#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HARPYA_PYTHON="${HARPYA_PYTHON:-/root/yolo_venv/bin/python}"

if [[ $# -lt 1 ]]; then
    echo "Uso:"
    echo "  $0 IMAGEM [argumentos extras do inference.py]"
    echo
    echo "Exemplo:"
    echo "  $0 /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m.jpg --json-output resultado.json"
    exit 2
fi

if [[ ! -x "$HARPYA_PYTHON" ]]; then
    echo "ERRO: Python YOLO do HARPia não encontrado em: $HARPYA_PYTHON" >&2
    echo "Defina HARPYA_PYTHON se o ambiente estiver em outro caminho." >&2
    exit 1
fi

exec "$HARPYA_PYTHON" "$ROOT_DIR/inference.py" "$@"
