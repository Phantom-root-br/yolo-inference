#!/usr/bin/env bash

SESSION="HarpiaSim"
WS="/root/harpia_ws"
SIM_DIR="$WS/src/simulation_bringup_eletroquad26/config/simulation"

export GZ_VERSION=garden
export GZ_IP=127.0.0.1
export IGN_IP=127.0.0.1

unset GZ_PARTITION
unset IGN_PARTITION
unset LIBGL_ALWAYS_SOFTWARE

export GZ_SIM_RESOURCE_PATH="/root/PX4-Autopilot/Tools/simulation/gz/models:/root/PX4-Autopilot/Tools/simulation/gz/worlds:/opt/ros/humble/share/as2_gazebo_assets/worlds:/opt/ros/humble/share/as2_gazebo_assets/models"

# ============================================================
# LIMPEZA
# Garante que nunca teremos dois Gazebo / PX4 / XRCE.
# ============================================================

tmux kill-session -t "$SESSION" 2>/dev/null || true

pkill -TERM -f 'square_mission' 2>/dev/null || true
pkill -TERM -f 'aruco_landing_mission' 2>/dev/null || true
pkill -TERM -f 'MicroXRCEAgent' 2>/dev/null || true
pkill -TERM -f 'px4_sitl_default/bin/px4' 2>/dev/null || true
pkill -TERM -f 'parameter_bridge' 2>/dev/null || true
pkill -TERM -f '^gz sim' 2>/dev/null || true

sleep 2

pkill -KILL -f 'MicroXRCEAgent' 2>/dev/null || true
pkill -KILL -f 'px4_sitl_default/bin/px4' 2>/dev/null || true
pkill -KILL -f 'parameter_bridge' 2>/dev/null || true
pkill -KILL -f '^gz sim' 2>/dev/null || true

# ============================================================
# TMUX - padrão Harpia
# ============================================================

tmux new-session -d -s "$SESSION" -n main
tmux new-window -t "$SESSION" -n sim-essentials

# 3 painéis: XRCE | PX4+Gazebo | Bridge
tmux split-window -t "$SESSION:sim-essentials"
tmux split-window -t "$SESSION:sim-essentials"
tmux select-layout -t "$SESSION:sim-essentials" tiled

mapfile -t PANES < <(
    tmux list-panes \
        -t "$SESSION:sim-essentials" \
        -F '#{pane_id}'
)

AGENT_PANE="${PANES[0]}"
PX4_PANE="${PANES[1]}"
BRIDGE_PANE="${PANES[2]}"

tmux select-pane -t "$AGENT_PANE" -T "XRCE"
tmux select-pane -t "$PX4_PANE" -T "PX4-GAZEBO"
tmux select-pane -t "$BRIDGE_PANE" -T "GARDEN-BRIDGE"

# MicroXRCEAgent
tmux send-keys -t "$AGENT_PANE" \
    "clear; echo '=== MicroXRCEAgent ==='; MicroXRCEAgent udp4 -p 8888" C-m

# Gazebo + PX4
tmux send-keys -t "$PX4_PANE" \
    "clear; echo '=== Gazebo + PX4 / Harpia ==='; bash '$SIM_DIR/start_px4_m1.sh'" C-m

# Bridge Garden
tmux send-keys -t "$BRIDGE_PANE" \
    "clear; echo '=== ROS-Gazebo Bridge / Garden ==='; cd '$WS'; source /opt/ros/humble/setup.bash; export GZ_VERSION=garden; source /root/ros_gz_garden_ws/install/setup.bash; source install/setup.bash; ros2 launch simulation_bringup ros_gz_bridge.launch.py" C-m

# Ferramentas / missões
tmux new-window -t "$SESSION" -n sim-tools

tmux send-keys -t "$SESSION:sim-tools" \
    "cd '$WS'; source /opt/ros/humble/setup.bash; export GZ_VERSION=garden; source /root/ros_gz_garden_ws/install/setup.bash; source install/setup.bash; clear; echo '=== SIM TOOLS ==='; echo; echo 'Square:'; echo '  ros2 run square_mission square_mission'; echo; echo 'ArUco:'; echo '  ros2 run movement_controler aruco_landing_mission'; echo" C-m

tmux select-window -t "$SESSION:sim-essentials"

echo "Sessão $SESSION criada."
echo "QGroundControl: DESATIVADO"
echo "Janelas:"
echo "  main"
echo "  sim-essentials"
echo "  sim-tools"
