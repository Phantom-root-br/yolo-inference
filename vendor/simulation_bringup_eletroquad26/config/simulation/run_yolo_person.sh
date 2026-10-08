#!/usr/bin/env bash

set -u

WS="${HARPIA_WS:-/root/harpia_ws}"
SIM="${HARPIA_SIM_DIR:-$WS/src/simulation_bringup_eletroquad26}"
YOLO="${YOLO_REPO:-$WS/src/yolo-inference}"

SESSION="${HARPIA_TMUX_SESSION:-HarpiaYolo}"

START_PX4="$SIM/config/simulation/start_px4_yolo_person.sh"
MODEL="${HARPIA_YOLO_MODEL:-$YOLO/models/harpia_person_topdown_pilot_v2.pt}"

AUTO_MISSION="${HARPIA_YOLO_AUTOSTART_MISSION:-1}"

echo "============================================================"
echo " HARPia YOLO Person - Bringup"
echo "============================================================"
echo
echo "Session       : $SESSION"
echo "World         : harpia_yolo_person.sdf"
echo "YOLO model    : $MODEL"
echo "Auto mission  : $AUTO_MISSION"
echo

# ------------------------------------------------------------
# Não mata processos globais do HARPia.
#
# Se existe outro simulador ativo, aborta este script.
# O shell que chamou este arquivo permanece intacto.
# ------------------------------------------------------------

CONFLICT=0

if pgrep -af 'px4_sitl_default/bin/px4' >/dev/null 2>&1; then
    echo "[ERRO] PX4 SITL já está ativo."
    CONFLICT=1
fi

if pgrep -af 'MicroXRCEAgent' >/dev/null 2>&1; then
    echo "[ERRO] MicroXRCEAgent já está ativo."
    CONFLICT=1
fi

if pgrep -af '^gz sim' >/dev/null 2>&1; then
    echo "[ERRO] Gazebo já está ativo."
    CONFLICT=1
fi

if [ "$CONFLICT" -ne 0 ]; then
    echo
    echo "Bringup não iniciado."
    echo "Nenhum processo existente foi encerrado."
    exit 20
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[ERRO] sessão tmux já existe: $SESSION"
    echo "Nenhuma sessão foi encerrada automaticamente."
    exit 21
fi

# ------------------------------------------------------------
# Sessão própria.
# ------------------------------------------------------------

tmux new-session \
    -d \
    -s "$SESSION" \
    -n xrce

tmux new-window \
    -t "$SESSION" \
    -n px4-gazebo

tmux new-window \
    -t "$SESSION" \
    -n bridge

tmux new-window \
    -t "$SESSION" \
    -n yolo

tmux new-window \
    -t "$SESSION" \
    -n mission

# ------------------------------------------------------------
# XRCE Agent
# ------------------------------------------------------------

tmux send-keys \
    -t "$SESSION:xrce" \
    "clear; echo '=== HARPia YOLO / MicroXRCEAgent ==='; MicroXRCEAgent udp4 -p 8888" \
    C-m

# ------------------------------------------------------------
# Gazebo + PX4.
#
# start_px4_yolo_person.sh é uma variante isolada do startup M1.
# ------------------------------------------------------------

tmux send-keys \
    -t "$SESSION:px4-gazebo" \
    "clear; echo '=== HARPia YOLO / Gazebo + PX4 ==='; bash '$START_PX4'" \
    C-m

# ------------------------------------------------------------
# Bridge central.
#
# IMPORTANTE:
# não iniciar ros_gz_image/image_bridge.
# O YAML central já publica /camera/image_raw.
# ------------------------------------------------------------

BRIDGE_CMD="cd '$WS'; \
source /opt/ros/humble/setup.bash; \
export GZ_VERSION=garden; \
source '$WS/install/setup.bash'; \
clear; \
echo '=== HARPia YOLO / ROS-Gazebo Bridge ==='; \
bash '$SIM/config/simulation/start_garden_camera_bridge.sh'"

tmux send-keys \
    -t "$SESSION:bridge" \
    "$BRIDGE_CMD" \
    C-m

# ------------------------------------------------------------
# Detector YOLO.
#
# Aguarda /camera/image_raw existir.
# ------------------------------------------------------------

YOLO_CMD="cd '$WS'; \
source /opt/ros/humble/setup.bash; \
source '$WS/install/setup.bash'; \
clear; \
echo '=== HARPia YOLO / Person Detector ==='; \
echo 'Aguardando /camera/image_raw ...'; \
until ros2 topic list 2>/dev/null | grep -qx '/camera/image_raw'; do sleep 1; done; \
echo '[OK] camera topic encontrado'; \
ros2 run yolo_person_detector detector_node \
--ros-args \
-p model_path:='$MODEL' \
-p confidence_threshold:=0.05 \
-p imgsz:=512 \
-p process_hz:=30.0"

tmux send-keys \
    -t "$SESSION:yolo" \
    "$YOLO_CMD" \
    C-m

# ------------------------------------------------------------
# Mission.
#
# Por padrão executa a missão completa em SITL.
#
# Para futura execução integral:
#
# HARPIA_YOLO_AUTOSTART_MISSION=0 \
#   bash run_yolo_person.sh
# ------------------------------------------------------------

if [ "$AUTO_MISSION" = "1" ]; then

    MISSION_CMD="cd '$WS'; \
source /opt/ros/humble/setup.bash; \
source '$WS/install/setup.bash'; \
clear; \
echo '=== HARPia YOLO / Person Mission ==='; \
echo 'Iniciando FSM YOLO diretamente ...'; bash '$SIM/config/simulation/wait_and_start_yolo_mission.sh'"

    tmux send-keys \
        -t "$SESSION:mission" \
        "$MISSION_CMD" \
        C-m

else

    tmux send-keys \
        -t "$SESSION:mission" \
        "clear; \
echo '=== HARPia YOLO / Mission ==='; \
echo; \
echo 'MISSAO NAO INICIADA NESTE TESTE.'; \
echo; \
echo 'Primeiro validar:'; \
echo '  Gazebo'; \
echo '  PX4'; \
echo '  /camera/image_raw'; \
echo '  /yolo/person_detections'; \
echo '  /yolo/image_annotated'; \
echo; \
echo 'Depois iniciaremos yolo_person_mission.'" \
        C-m

fi

tmux select-window \
    -t "$SESSION:px4-gazebo"

echo
echo "[OK] sessão criada:"
echo "     $SESSION"
echo
echo "Acompanhar:"
echo "     tmux attach -t $SESSION"
echo
echo "Janelas:"
tmux list-windows \
    -t "$SESSION" \
    -F '  #{window_index}: #{window_name}'
