# ROS 2 portability: extracting YOLO from HARPia

## Goal

The perception layer is intentionally independent from Gazebo and PX4.

```text
SIMULATION ONLY
Gazebo world + actor + ros_gz_bridge
                  |
                  | sensor_msgs/Image
                  v
PORTABLE PERCEPTION
yolo_person_interfaces + yolo_person_detector + .pt model
                  |
                  | typed ROS 2 detections
                  v
VEHICLE / MISSION ADAPTER
HARPia mission + PX4
```

Anything that can publish a ROS 2 `sensor_msgs/Image` can feed the detector:
Gazebo, rosbag, USB camera, CSI camera, RealSense bridge, or another machine.

The detector does **not** import PX4 or Gazebo packages.

## ROS topics

Input:

- `/camera/image_raw` — `sensor_msgs/msg/Image`

Outputs:

- `/yolo/image_annotated` — annotated `sensor_msgs/msg/Image`
- `/yolo/person_detection` — best fresh detection
- `/yolo/person_detections` — all fresh person detections
- `/yolo/person_detected` — `std_msgs/msg/Bool`

The mission should consume `/yolo/person_detections`. The single-detection
topic is useful for simple consumers and debugging.

## Build in another ROS 2 Humble workspace

Example:

```bash
mkdir -p ~/harpia_yolo_ws/src
cd ~/harpia_yolo_ws/src

git clone https://github.com/Phantom-root-br/yolo-inference.git

cp -r yolo-inference/ros2/yolo_person_interfaces .
cp -r yolo-inference/ros2/yolo_person_detector .

cd ~/harpia_yolo_ws

source /opt/ros/humble/setup.bash

colcon build   --packages-select   yolo_person_interfaces   yolo_person_detector   --symlink-install

source install/setup.bash
```

Install the Python inference dependencies in the Python environment used by the
ROS node. On HARPia this has been done with a dedicated venv that can import
`rclpy`, `cv_bridge`, OpenCV and Ultralytics.

Typical non-ROS Python dependencies:

```text
ultralytics
opencv-python
numpy
```

ROS packages such as `rclpy`, `sensor_msgs` and `cv_bridge` should normally
come from the ROS installation.

## Model

The current simulation-specific model is named:

```text
harpia_person_topdown_pilot_v2.pt
```

Weights are intentionally not stored in normal Git history. Put the model in a
known path and configure `model_path`.

The generic `yolo11n.pt` can be used as a bootstrap model, but it is not a
replacement for a model trained on top-down humans.

## Run

```bash
source /opt/ros/humble/setup.bash
source ~/harpia_yolo_ws/install/setup.bash

ros2 run yolo_person_detector person_detector --ros-args   -p model_path:=/absolute/path/harpia_person_topdown_pilot_v2.pt   -p input_topic:=/camera/image_raw   -p confidence_threshold:=0.05   -p imgsz:=512   -p device:=cpu
```

For a GPU machine, set `device:=0` after validating the PyTorch/CUDA stack.

## Why detector confidence can be lower than mission lock confidence

Do not use one threshold for every purpose.

Recommended current simulation profile:

```text
YOLO candidate threshold : 0.05
mission TARGET_LOCK      : 0.10
tracking/reacquire       : 0.05
```

The detector publishes weak-but-plausible candidates. The mission applies
hysteresis:

1. a stronger detection locks the target;
2. after lock, lower-confidence detections can continue updating the target;
3. brief missed frames preserve the last visual target instead of restarting
   the search.

This reduces flicker without making a 0.05 detection sufficient to trigger a
new mission lock.

## Porting to another camera

Only the image source changes on the perception side.

Validate:

1. image encoding accepted by `cv_bridge`;
2. image width/height;
3. field of view and mounting orientation;
4. inference latency;
5. threshold calibration on real validation frames.

The vehicle-control mapping from image axes to local PX4 axes belongs to the
mission adapter, not to the detector.

## Porting to another airframe / PX4 configuration

The perception package remains unchanged.

The adapter must own:

- PX4 topic names and message versions;
- OFFBOARD / arm / land commands;
- local-frame sign convention;
- altitude policy;
- visual-servo gains;
- mission state machine.

This separation is the main requirement for keeping the YOLO component
reusable.
