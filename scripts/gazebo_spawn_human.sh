#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$ROOT/sim/gazebo/human_actor.sdf"
NAME="harpia_human_target"

WORLD="${1:-}"
X="${2:-8.0}"
Y="${3:-0.0}"
Z="${4:-1.0}"
YAW="${5:-3.14159}"

if ! command -v gz >/dev/null 2>&1; then
  echo "ERRO: comando 'gz' não encontrado." >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERRO: template não encontrado: $TEMPLATE" >&2
  exit 1
fi

if [[ -z "$WORLD" ]]; then
  WORLD="$(gz service -l 2>/dev/null | sed -n 's#^/world/\([^/]*\)/create$#\1#p' | head -n 1)"
fi

if [[ -z "$WORLD" ]]; then
  echo "ERRO: não encontrei serviço /world/<nome>/create." >&2
  echo "Confirme que o Gazebo está rodando e que o world carrega UserCommands." >&2
  exit 1
fi

CREATE_SERVICE="/world/$WORLD/create"
if ! gz service -l 2>/dev/null | grep -Fxq "$CREATE_SERVICE"; then
  echo "ERRO: serviço não encontrado: $CREATE_SERVICE" >&2
  exit 1
fi

TMP_SDF="$(mktemp /tmp/harpia_human_target.XXXXXX.sdf)"
trap 'rm -f "$TMP_SDF"' EXIT

sed -E \
  "s#<pose>[^<]+</pose>#<pose>${X} ${Y} ${Z} 0 0 ${YAW}</pose>#" \
  "$TEMPLATE" > "$TMP_SDF"

echo "============================================================"
echo " HARPia - SPAWN ALVO HUMANO NO GAZEBO"
echo "============================================================"
echo "World : $WORLD"
echo "Nome  : $NAME"
echo "Pose  : x=$X y=$Y z=$Z yaw=$YAW"
echo "SDF   : $TEMPLATE"
echo

gz service \
  -s "$CREATE_SERVICE" \
  --reqtype gz.msgs.EntityFactory \
  --reptype gz.msgs.Boolean \
  --timeout 5000 \
  --req "sdf_filename: \"$TMP_SDF\", name: \"$NAME\", allow_renaming: false"

echo
echo "Se a resposta for data: true, o ator foi solicitado ao Gazebo."
echo "Na primeira execução, o mesh humano pode ser baixado do Gazebo Fuel."
echo "Para remover: ./scripts/gazebo_remove_human.sh $WORLD"
