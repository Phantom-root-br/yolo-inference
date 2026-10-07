#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:-}"
IMAGE_TOPIC="${2:-/camera/image_raw}"

if [[ -z "$MODEL_PATH" ]]; then
  echo "usage: $0 /absolute/path/model.pt [/camera/image_raw]" >&2
  exit 2
fi

source /opt/ros/humble/setup.bash

ros2 run yolo_person_detector person_detector --ros-args   -p model_path:="$MODEL_PATH"   -p input_topic:="$IMAGE_TOPIC"   -p confidence_threshold:=0.05   -p imgsz:=512   -p iou_threshold:=0.45   -p device:=cpu
