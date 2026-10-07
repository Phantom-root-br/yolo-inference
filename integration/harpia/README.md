# HARPia integration profile

This directory documents the adapter between the portable YOLO detector and
the HARPia/PX4 mission.

The simulation world, Gazebo actor, Garden bridge and PX4 startup remain HARPia
simulation concerns. They are deliberately not dependencies of the detector.

## Current data path

```text
Gazebo downward camera
    |
    | /camera/image_raw
    v
yolo_person_detector
    |
    +--> /yolo/image_annotated
    +--> /yolo/person_detection
    +--> /yolo/person_detections
    +--> /yolo/person_detected
             |
             v
      yolo_person_mission
             |
             v
            PX4
```

## Current mission contract

```text
WAIT_POSITION
-> WARMUP_OFFBOARD
-> ENGAGE_OFFBOARD
-> ARM
-> TAKEOFF 4 m
-> SEARCH_SQUARE_SPIRAL

first bbox >= lock threshold
-> TARGET_LOCKED
-> CENTER_TARGET
-> TRACK_HIGH_30S
-> DESCEND_TRACK_1M
-> TRACK_LOW_30S
-> ASCEND_TRACK_4M
-> RETURN_HOME
-> LAND_HOME
-> DISARM
-> COMPLETE
```

A new bbox always supersedes the previous visual waypoint. Empty inference
frames preserve the last waypoint for a bounded interval.

## Simulation profile

Detector:

```text
candidate confidence : 0.05
imgsz                : 512
device               : cpu
```

Mission:

See `mission_sim.yaml`.

Important distinction:

```text
candidate threshold = 0.05
lock threshold      = 0.10
tracking threshold  = 0.05
```

This is intended to reduce intermittent misses without letting a weak 0.05
candidate create a new target lock.

## Integrating into an existing HARPia workspace

Copy or symlink the two ROS packages from `ros2/` into the workspace `src`
directory, then build them with colcon.

The HARPia mission adapter may live in the main HARPia workspace because it
depends on `px4_msgs`. The detector should remain here because it does not.

## External events expected from the mission

Recommended event API:

```text
PERSON_CONFIRMED
TARGET_LOCKED
PERSON_CENTERED
TRACK_HIGH_30S_COMPLETE
TARGET_LOW_ALTITUDE_REACHED
TRACK_LOW_30S_COMPLETE
ASCEND_TRACK_COMPLETE
RETURN_HOME_COMPLETE
LANDED
VEHICLE_DISARMED
MISSION_COMPLETE
```

These events are integration surfaces for a UI, logger, supervisor or higher
level state machine.


## Final runtime fixes

The last end-to-end run validated the perception/navigation path through
`LANDED`, but exposed two final runtime issues:

1. the normal PX4 DISARM command did not confirm and the FSM entered
   `ERROR_HOLD`;
2. the annotated camera GUI was skipped because a full-image
   `ros2 topic echo --once` readiness gate lost messages and timed out.

The repository now contains the runtime fix kit in
[`integration/harpia/runtime/`](runtime/README.md).

Apply and rebuild the current HARPia workspace:

```bash
cd /root/harpia_ws/src/yolo-inference
git pull

export HARPIA_WS=/root/harpia_ws
export YOLO_REPO=$HARPIA_WS/src/yolo-inference

bash $YOLO_REPO/integration/harpia/runtime/apply_and_build.sh
```

Run HARPia with the independent annotated-camera viewer:

```bash
bash $YOLO_REPO/integration/harpia/runtime/run_harpia_yolo_with_viewer.sh
```

The DISARM fallback is deliberately **simulation-only**. The portable mission
parameter defaults to disabled; the HARPia simulation launcher explicitly
enables it after a confirmed `LANDED` state.
