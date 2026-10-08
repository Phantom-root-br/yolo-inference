#!/usr/bin/env bash
set +H 2>/dev/null || true
WS="${HARPIA_WS:-/root/harpia_ws}"
source /opt/ros/humble/setup.bash
source "$WS/install/setup.bash"

echo "============================================================"
echo " HARPia YOLO - PREPARANDO MISSAO"
echo "============================================================"

DETECTOR=0
while [ "$DETECTOR" -eq 0 ]; do
  ros2 node list 2>/dev/null | grep -qx "/yolo_person_detector" && DETECTOR=1
  if [ "$DETECTOR" -eq 0 ]; then echo "[WAIT] detector YOLO"; sleep 1; fi
done
echo "[OK] detector YOLO ativo"

ros2 param set /yolo_person_detector confidence_threshold 0.05
echo "[OK] threshold detector:"
ros2 param get /yolo_person_detector confidence_threshold

RAW=0
while [ "$RAW" -eq 0 ]; do
  timeout -s KILL 4s ros2 topic echo /camera/image_raw --once --field width > /tmp/harpia_ready_raw.txt 2>&1
  grep -q "640" /tmp/harpia_ready_raw.txt && RAW=1
  if [ "$RAW" -eq 0 ]; then echo "[WAIT] frame /camera/image_raw"; sleep 1; fi
done
echo "[OK] RAW 640 recebido"

ANN=0
while [ "$ANN" -eq 0 ]; do
  timeout -s KILL 6s ros2 topic echo /yolo/image_annotated --once --field width > /tmp/harpia_ready_ann.txt 2>&1
  grep -q "640" /tmp/harpia_ready_ann.txt && ANN=1
  if [ "$ANN" -eq 0 ]; then echo "[WAIT] frame /yolo/image_annotated"; sleep 1; fi
done
echo "[OK] YOLO annotated 640 recebido"

POS=0
while [ "$POS" -eq 0 ]; do
  timeout -s KILL 4s ros2 topic echo /fmu/out/vehicle_local_position --once > /tmp/harpia_ready_pos.txt 2>&1
  XY=0
  Z=0
  grep -q "^xy_valid: true" /tmp/harpia_ready_pos.txt && XY=1
  grep -q "^z_valid: true" /tmp/harpia_ready_pos.txt && Z=1
  if [ "$XY" -eq 1 ] && [ "$Z" -eq 1 ]; then POS=1; fi
  if [ "$POS" -eq 0 ]; then echo "[WAIT] PX4 local position valida"; sleep 1; fi
done
echo "[OK] PX4 local position valida"

echo "============================================================"
echo " PREPARO_OK"
echo " Camera + YOLO + PX4 prontos."
echo " Missao iniciara em 8 segundos."
echo "============================================================"
sleep 8

exec "$WS/install/yolo_person_mission/lib/yolo_person_mission/person_mission" --ros-args -p flight_altitude_m:=4.0 -p confirmation_confidence:=0.10 -p confirmation_frames:=1 -p detection_max_age_sec:=4.0 -p tracking_min_confidence:=0.05 -p track_duration_sec:=30.0 -p low_altitude_m:=1.0 -p low_track_duration_sec:=30.0 -p bbox_ema_alpha:=1.0 -p vertical_tolerance_m:=0.25 -p spiral_step_m:=2.0 -p spiral_max_radius_m:=4.0 -p visual_servo_gain:=1.80 -p visual_target_alpha:=1.0 -p visual_target_max_update_m:=3.50 -p visual_target_lead_sec:=0.0 -p visual_target_max_speed_mps:=0.80 -p alignment_hold_sec:=0.50 -p local_x_from_image_y_sign:=-1.0 -p local_y_from_image_x_sign:=1.0 -p bbox_priority_hold_sec:=1.25 -p bbox_confidence_epsilon:=0.0 -p allow_force_disarm_after_landed:=true -p force_disarm_after_sec:=5.0 -p disarm_timeout_sec:=20.0
