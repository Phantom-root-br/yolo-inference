# Reproducing the HARPia YOLO demo

## One command on a prepared HARPia workstation

Once the machine has the same HARPia/PX4 simulation dependencies and the model
artifact, the intended team workflow is:

```bash
cd /root/harpia_ws/src/yolo-inference
git pull

bash integration/harpia/runtime/run_from_zero.sh
```

The command performs:

```text
preflight
-> apply runtime integration fixes
-> colcon build
-> clean previous tmux session
-> start XRCE/PX4/Gazebo/bridge/YOLO/mission
-> open annotated camera viewer
-> continuously print mission state
-> exit only on MISSION_COMPLETE / ERROR_HOLD / timeout
```

This is deliberately different from the lower-level launcher:
`run_harpia_yolo_with_viewer.sh` starts the processes and returns. The
`run_from_zero.sh` wrapper is the recommended human-facing entry point and
keeps showing mission progress.

## What “from zero” currently means

There are two different meanings of reproducibility and they should not be
confused.

### A. Fresh clone inside a prepared HARPia workstation

Supported by `run_from_zero.sh`, provided the machine already has:

- ROS 2 Humble;
- PX4/HARPia workspace;
- Gazebo Garden and the required ROS-Gazebo bridge;
- `simulation_bringup_eletroquad26`;
- local `yolo_person_mission` package;
- the model artifact `harpia_person_topdown_pilot_v2.pt`.

### B. Brand-new machine with only this repository

**Not yet fully supported.**

The portable YOLO detector can be installed from this repository, but the
complete PX4/Gazebo mission still depends on HARPia assets and a model binary
that are not all stored in normal Git history.

The preflight script intentionally fails with an explicit missing-dependency
message instead of silently producing a partial demo.

## Expected terminal flow

A successful run should visibly progress through:

```text
WAIT_POSITION
WARMUP_OFFBOARD
ENGAGE_OFFBOARD
ARM
TAKEOFF_4M
SEARCH_SQUARE_SPIRAL
TARGET_LOCKED
CENTER_TARGET
PERSON_CENTERED
TRACK_CENTER_30S
DESCEND_TRACK_1M
TRACK_LOW_30S
ASCEND_TRACK_4M
RETURN_HOME
LAND_HOME
DISARM
VEHICLE_DISARMED
MISSION_COMPLETE
COMPLETE
```

The annotated camera viewer should open independently and display
`/yolo/image_annotated`.

## Recommended next packaging milestone

To make **B** true, publish/version all of the following:

1. `yolo_person_mission` package;
2. minimal HARPia simulation world/model/actor/camera assets;
3. exact `simulation_bringup_eletroquad26` runner or a pinned dependency;
4. custom model artifact, preferably a GitHub Release asset with SHA256;
5. supported PX4 commit/version;
6. supported ROS/Gazebo versions;
7. one setup/bootstrap script or container image.

Until then, describe the repository as a reproducible YOLO/ROS integration plus
a one-command demo for an already prepared HARPia workstation, not as a
self-contained PX4 simulator distribution.
