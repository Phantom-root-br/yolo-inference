#!/usr/bin/env bash

echo "Aguardando inicialização básica da simulação..."
sleep 8

RUNTIME="/tmp/runtime-harpia"

mkdir -p "$RUNTIME"
chown harpia:harpia "$RUNTIME"
chmod 700 "$RUNTIME"

echo "Iniciando QGroundControl como usuário harpia..."
echo "DISPLAY=${DISPLAY:-<vazio>}"

runuser -u harpia -- env \
    DISPLAY="${DISPLAY:-:1}" \
    XDG_RUNTIME_DIR="$RUNTIME" \
    QT_X11_NO_MITSHM=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    /usr/local/bin/QGroundControl.AppImage

echo
echo "QGroundControl encerrado."
exec bash
