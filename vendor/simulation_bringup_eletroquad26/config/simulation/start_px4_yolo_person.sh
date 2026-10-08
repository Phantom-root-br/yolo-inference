#!/usr/bin/env bash

# ============================================================
# HARPia YOLO Person
#
# Variante ADICIONAL do startup M1.
#
# O nome lógico do world continua eletroquad26_m1 porque o SDF
# YOLO preserva o mesmo <world name>. O arquivo carregado é
# harpia_yolo_person.sdf.
#
# M1/M2/M3 não são modificados por este script.
# ============================================================

# HARPia stochastic wind plugin
export GZ_SIM_SYSTEM_PLUGIN_PATH="/usr/local/lib/harpia/wind/lib:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"

WORLD="eletroquad26_m1"

export GZ_VERSION=garden
export GZ_IP=127.0.0.1
export IGN_IP=127.0.0.1

unset GZ_PARTITION
unset IGN_PARTITION
unset LIBGL_ALWAYS_SOFTWARE

mkdir -p /tmp/runtime-root
chmod 700 /tmp/runtime-root

export XDG_RUNTIME_DIR=/tmp/runtime-root
export QT_X11_NO_MITSHM=1
PX4_DIR="/root/PX4-Autopilot"
WORLD_FILE="/root/harpia_ws/src/simulation_bringup_eletroquad26/worlds/harpia_yolo_person.sdf"

SERVER_LOG="/tmp/harpia_yolo_person_gz_server.log"
GUI_LOG="/tmp/harpia_yolo_person_gz_gui.log"

# Caminhos que já foram validados manualmente.
export GZ_SIM_RESOURCE_PATH="/root/harpia_ws/src/simulation_bringup_eletroquad26/models:/root/harpia_ws/src/simulation_bringup_eletroquad26/worlds:/root/PX4-Autopilot/Tools/simulation/gz/models:/root/PX4-Autopilot/Tools/simulation/gz/worlds:/opt/ros/humble/share/as2_gazebo_assets/worlds:/opt/ros/humble/share/as2_gazebo_assets/models"

# Não usar a partição experimental dos testes anteriores.
unset GZ_PARTITION

cd "$PX4_DIR" || exit 1

echo "=============================================="
echo " ELETROQUAD M1 - GAZEBO + PX4"
echo "=============================================="
echo
echo "DISPLAY=${DISPLAY:-<vazio>}"
echo "GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH"
echo

rm -f "$SERVER_LOG" "$GUI_LOG"

echo "[1/3] Iniciando Gazebo Server..."

gz sim -r -s "$WORLD_FILE" >"$SERVER_LOG" 2>&1 &
GZ_SERVER_PID=$!

echo "Gazebo Server PID: $GZ_SERVER_PID"
echo

echo "[2/3] Aguardando inicialização do Gazebo..."
echo "Aguarde aproximadamente 12 segundos."

#
# NÃO usamos mais `gz service -l`.
# Já comprovamos que /world/eletroquad26_m1/create existe,
# mas essa consulta travava o bringup.
#
sleep 12

if ! kill -0 "$GZ_SERVER_PID" 2>/dev/null; then
    echo
    echo "ERRO: Gazebo Server encerrou."
    echo
    echo "===== LOG GAZEBO ====="
    tail -100 "$SERVER_LOG"
    echo
    exec bash
fi

echo
echo "Gazebo Server está ativo."
echo

if [ -n "${DISPLAY:-}" ]; then
    echo "Abrindo Gazebo GUI..."

    gz sim -g >"$GUI_LOG" 2>&1 &

    sleep 2
else
    echo "DISPLAY não definido."
    echo "Continuando sem GUI."
fi

echo
echo "[3/3] Iniciando PX4 + x500_0..."
echo

echo "Criando modelo HARPia como entidade x500_0..."

HARP_MODEL="/root/harpia_ws/src/simulation_bringup_eletroquad26/models/harpia_yolo_x500/model.sdf"

# O PX4 será conectado depois à entidade x500_0.
# O modelo físico é o HARPia customizado, que contém a câmera downward.
if timeout 4 gz model -m x500_0 -p >/dev/null 2>&1; then

    echo "[INFO] x500_0 já existe."

else

    echo "Spawn: $HARP_MODEL -> x500_0"

    SPAWN_REPLY="$(
        timeout 15 gz service             -s /world/eletroquad26_m1/create             --reqtype gz.msgs.EntityFactory             --reptype gz.msgs.Boolean             --timeout 10000             --req "sdf_filename: '${HARP_MODEL}', name: 'x500_0', allow_renaming: false"             2>&1
    )"

    SPAWN_RC=$?

    echo "spawn_rc=$SPAWN_RC"
    echo "$SPAWN_REPLY"

    if [ "$SPAWN_RC" -ne 0 ]; then
        echo "ERRO: serviço de criação do x500_0 falhou."
        exit 1
    fi

fi

echo
echo "Spawn confirmado pelo serviço /create."
echo "A entidade x500_0 será conectada pelo PX4_GZ_MODEL_NAME."

echo "Aguardando estabilização física curta do x500_0..."

for i in 1 2 3; do
    echo "  settle ${i}/3"
    sleep 1
done

echo "x500_0 liberado para conexão PX4."

echo "Restaurando bridge /clock..."

pkill -f 'parameter_bridge.*/world/eletroquad26_m1/clock@rosgraph_msgs/msg/Clock' \
    2>/dev/null || true

setsid -f bash -lc '
set +u
source /opt/ros/humble/setup.bash
export GZ_VERSION=garden
if [ -f /root/ros_gz_garden_ws/install/setup.bash ]; then
  source /root/ros_gz_garden_ws/install/setup.bash
fi
source /root/harpia_ws/install/setup.bash

exec ros2 run ros_gz_bridge parameter_bridge \
  "/world/eletroquad26_m1/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock" \
  --ros-args \
  -r "/world/eletroquad26_m1/clock:=/clock"
' </dev/null >/tmp/harpia_clock_bridge.log 2>&1

sleep 1


# ============================================================
# HARPia: camera bridge fornecida pelo bridge central
#
# /color_cam_downward -> /camera/image_raw
# ja esta definido em:
# config/ros_gz_bridge/bridge_params_eletroquad_26.yaml
#
# NAO iniciar ros_gz_image/image_bridge aqui.
# Manter dois bridges para o mesmo topico gera frames duplicados.
echo "Camera downward: bridge central ros_gz_bridge ativo; bridge redundante desabilitado."

PX4_GZ_STANDALONE=1 \
PX4_GZ_WORLD="$WORLD" \
PX4_GZ_MODEL_NAME=x500_0 \
make px4_sitl gz_x500

RC=$?

echo
echo "PX4 encerrou com código: $RC"
echo
echo "Gazebo Server log:"
echo "  $SERVER_LOG"
echo
echo "Gazebo GUI log:"
echo "  $GUI_LOG"
echo

exec bash
