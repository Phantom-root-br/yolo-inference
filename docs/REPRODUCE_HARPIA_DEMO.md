# Reproducing the HARPia YOLO mission

This document defines the supported path for reproducing the simulation that
reached `MISSION_COMPLETE` on 2026-10-07.

## Team member workflow

The intended user experience is:

```bash
mkdir -p /root/harpia_ws/src
cd /root/harpia_ws/src

git clone https://github.com/Phantom-root-br/yolo-inference.git
cd yolo-inference

bash integration/harpia/runtime/run_from_zero.sh
```

`run_from_zero.sh` performs:

```text
bootstrap distributed stack
-> preflight
-> build ROS packages
-> reset previous HARPiaYolo tmux session
-> start XRCE/PX4/Gazebo
-> start ROS-Gazebo bridge
-> start YOLO
-> start mission
-> open annotated camera viewer
-> continuously print mission state
-> finish on MISSION_COMPLETE / ERROR_HOLD / timeout
```

The default graphical behavior matches the validated run:

- Gazebo simulation window;
- separate annotated drone-camera window;
- tmux session `HarpiaYolo`;
- continuous mission-state output in the terminal.

Close the camera viewer with its window-manager **X**, **Esc**, or **q**. To
run without the camera viewer:

```bash
HARPIA_VIEWER=0 bash integration/harpia/runtime/run_from_zero.sh
```

## Base-machine requirements

The repository can distribute the mission, detector, model and simulation
package, but the host still needs the robotics runtime:

- Ubuntu environment compatible with ROS 2 Humble;
- ROS 2 Humble at `/opt/ros/humble`;
- Gazebo Garden / `gz sim`;
- PX4 build/runtime dependencies;
- `git`, `tmux`, `python3-venv`, `rsync`.

The validated PX4 revision and model checksum are stored in
`integration/harpia/repro/validated_stack.env` after the stack freeze is
published.

## What must be inside the repository

A distribution is considered complete only when all these paths are tracked:

```text
yolo_person_mission/
vendor/simulation_bringup_eletroquad26/
models/harpia_person_topdown_pilot_v2.pt
integration/harpia/repro/validated_stack.env
```

Run:

```bash
bash integration/harpia/runtime/audit_distribution.sh
```

The required final result is:

```text
DISTRIBUTION_READY=1
```

## Maintainer: freeze the exact validated workstation

On the workstation that produced the successful simulation:

```bash
cd /root/harpia_ws/src/yolo-inference
git pull

bash integration/harpia/runtime/publish_validated_stack.sh
```

This publishes a dedicated branch named `reproducible-harpia-demo` containing
only the exact missing runtime artifacts:

- local `yolo_person_mission` package;
- current `simulation_bringup_eletroquad26` package and assets;
- validated custom model;
- generated revision/checksum manifest.

The script does **not** add local datasets, training runs or unrelated untracked
files.

After CI and distribution audit pass, merge that branch into `main`. From
that point, the team-member workflow at the top of this document is the
supported entry point.

## Expected mission sequence

A successful run should visibly reach:

```text
HOME_CAPTURED
VEHICLE_ARMED
TAKEOFF_COMPLETE
SEARCH_SQUARE_SPIRAL
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
COMPLETE
```

In the validated SITL run, normal DISARM did not confirm after `LANDED`; the
simulation-only post-landing fallback completed the disarm. That fallback is
disabled by default outside the simulation launch profile.

## Model evolution

Do not replace the validated model in-place while changing mission logic.

Model improvements follow:

```text
new dataset
-> supervised bounding-box annotation
-> candidate model
-> offline baseline comparison
-> continuous-video regression
-> ROS regression
-> complete mission regression
-> promote model
```

See `docs/MODEL_UPGRADE_POLICY.md`.
