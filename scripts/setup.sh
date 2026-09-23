#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "==> Repositório: $ROOT_DIR"
echo "==> Python:      $PYTHON_BIN"
echo "==> Ambiente:    $VENV_DIR"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
    echo "ERRO: '$PYTHON_BIN' não encontrado." >&2
    exit 1
}

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"

echo
echo "Setup concluído."
echo "Ative o ambiente com:"
echo "  source \"$VENV_DIR/bin/activate\""
echo
echo "Teste a CLI com:"
echo "  python \"$ROOT_DIR/inference.py\" --help"
