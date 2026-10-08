#!/usr/bin/env bash
set +H 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /root/harpia_ws/install/setup.bash
CACHE="/root/.cache/harpia/ros_gzgarden"
BIN="$CACHE/opt/ros/humble/lib/ros_gz_bridge/parameter_bridge"
export GZ_IP=127.0.0.1
export IGN_IP=127.0.0.1
export GZ_VERSION=garden
export LD_LIBRARY_PATH="$CACHE/opt/ros/humble/lib:/opt/ros/humble/lib:${LD_LIBRARY_PATH:-}"
echo "=== HARPia YOLO / Garden Camera Bridge ==="
echo "BIN=$BIN"
if [ -x "$BIN" ]; then
  "$BIN" "/color_cam_downward@sensor_msgs/msg/Image[gz.msgs.Image" --ros-args -r /color_cam_downward:=/camera/image_raw
else
  echo "[ERRO] Garden parameter_bridge ausente"
fi
