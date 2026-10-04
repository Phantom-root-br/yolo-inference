#!/usr/bin/env bash
set -euo pipefail

NAME="harpia_human_target"
WORLD="${1:-}"

if ! command -v gz >/dev/null 2>&1; then
  echo "ERRO: comando 'gz' não encontrado." >&2
  exit 1
fi

if [[ -z "$WORLD" ]]; then
  WORLD="$(gz service -l 2>/dev/null | sed -n 's#^/world/\([^/]*\)/remove$#\1#p' | head -n 1)"
fi

if [[ -z "$WORLD" ]]; then
  echo "ERRO: não encontrei serviço /world/<nome>/remove." >&2
  exit 1
fi

REMOVE_SERVICE="/world/$WORLD/remove"
if ! gz service -l 2>/dev/null | grep -Fxq "$REMOVE_SERVICE"; then
  echo "ERRO: serviço não encontrado: $REMOVE_SERVICE" >&2
  exit 1
fi

echo "Removendo ator '$NAME' do world '$WORLD'..."
gz service \
  -s "$REMOVE_SERVICE" \
  --reqtype gz.msgs.Entity \
  --reptype gz.msgs.Boolean \
  --timeout 5000 \
  --req "name: \"$NAME\", type: ACTOR"
