#!/usr/bin/env bash

# Tmux session and window names
SESSION="HarpiaSim"
WINDOW_0="main"
WINDOW_1="sim-essentials"
WINDOW_2="sim-tools"

# Commands to run in each pane
START_MICROXRCE_AGENT="MicroXRCEAgent udp4 -p 8888"
START_QGC='cd /root/harpia_ws/ && runuser -l harpia -c "DISPLAY=${DISPLAY} /usr/local/bin/QGroundControl.AppImage"'
START_PX4='cd /root/PX4-Autopilot && PX4_GZ_WORLD=eletroquad26_m1 make px4_sitl gz_harpia'
START_BRIDGE="ros2 launch simulation_bringup ros_gz_bridge.launch.py"

# Check if the tmux session already exists
if tmux has-session -t $SESSION 2>/dev/null; then
    echo "Session $SESSION already exists. Attaching to it..."
    tmux attach-session -t $SESSION
    exit 0
fi

# Create a new tmux session and set up the windows
tmux new-session -d -s $SESSION -n $WINDOW_0
tmux new-window -d -t $SESSION -n $WINDOW_1
tmux new-window -d -t $SESSION -n $WINDOW_2

# Set up the sim-essentials window with a tiled layout
tmux split-window -h -t $SESSION:$WINDOW_1
tmux split-window -v -t $SESSION:$WINDOW_1.0
tmux split-window -v -t $SESSION:$WINDOW_1.2
tmux select-layout -t $SESSION:$WINDOW_1 tiled

# Send commands to the respective panes in the sim-essentials window
tmux send-keys -t $SESSION:$WINDOW_1.0 "$START_MICROXRCE_AGENT" C-m
tmux send-keys -t $SESSION:$WINDOW_1.1 "$START_PX4" C-m
tmux send-keys -t $SESSION:$WINDOW_1.2 "$START_QGC" C-m
tmux send-keys -t $SESSION:$WINDOW_1.3 "$START_BRIDGE" C-m

#Attach to the session
tmux select-window -t $SESSION:$WINDOW_0
tmux attach-session -t $SESSION