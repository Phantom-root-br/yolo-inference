# Reproducing the validated HARPia YOLO mission

This is the supported procedure for reproducing the simulation that reached
`MISSION_COMPLETE` on 2026-10-07.

## 1. Supported host baseline

The repository distributes the mission-specific stack, but the computer still
needs the robotics base environment:

- Ubuntu environment compatible with ROS 2 Humble;
- ROS 2 Humble installed at `/opt/ros/humble`;
- Gazebo Garden / gz-sim7;
- PX4 build dependencies (`make`, compiler toolchain, CMake, etc.);
- `MicroXRCEAgent`;
- `git`, `tmux`, `python3-venv`, `rsync`, `dpkg-deb`;
- a valid graphical `DISPLAY` when Gazebo GUI and the annotated viewer are
  desired.

The entrypoint performs a host check before downloading/building anything
expensive.

## 2. Clone and run

Use the validated workspace layout:

```bash
mkdir -p /root/harpia_ws/src
cd /root/harpia_ws/src

git clone https://github.com/Phantom-root-br/yolo-inference.git
cd yolo-inference

bash integration/harpia/runtime/run_from_zero.sh
```

The same command can be rerun. It is designed to converge the mission stack to
the frozen revisions.

## 3. What the command does

`run_from_zero.sh` executes:

```text
HOST CHECK
-> clone/checkout PX4 at the validated commit
-> clone/checkout px4_msgs at the validated commit
-> expose the vendored simulation package in the ROS workspace
-> reconstruct the validated Garden bridge cache
-> verify the custom YOLO model checksum
-> create/update the Python environment
-> build px4_msgs + simulation + detector + mission packages
-> preflight exact revisions/checksums
-> reset a previous HarpiaYolo tmux session
-> start XRCE / Gazebo / PX4
-> start the Garden camera bridge
-> start the YOLO detector
-> start the mission FSM
-> open the annotated camera viewer
-> continuously print mission status
-> finish on MISSION_COMPLETE / ERROR_HOLD / monitor timeout
```

## 4. Windows and terminal behavior

The graphical run should reproduce the validated operator experience:

1. Gazebo GUI;
2. a separate annotated drone-camera window;
3. tmux session `HarpiaYolo`;
4. mission status continuously printed in the invoking terminal.

The camera viewer is independent from the mission. Close it with the
window-manager **X**, **Esc**, or **q**.

Run without the separate camera window:

```bash
HARPIA_VIEWER=0 bash integration/harpia/runtime/run_from_zero.sh
```

## 5. Frozen runtime artifacts

The repository contains the mission-specific artifacts that used to exist only
on the validated workstation:

```text
yolo_person_mission/
models/harpia_person_topdown_pilot_v2.pt
vendor/simulation_bringup_eletroquad26/
vendor/ros_gzgarden/
integration/harpia/repro/validated_stack.env
```

The simulation vendor tree includes:

- `harpia_yolo_person.sdf`;
- moving human actor;
- HARPia X500 model;
- `eletroquad_26` assets;
- LW20;
- RealSense D435.

The Garden bridge vendor tree contains the exact bridge/interface Debian
packages used to reconstruct the validated camera-bridge cache.

The manifest freezes:

- PX4 commit;
- px4_msgs commit;
- simulation source commit;
- YOLO model size and SHA256;
- SHA256 trees for Eletroquad, LW20 and RealSense;
- Garden bridge/interface package checksums;
- `parameter_bridge` checksum;
- ROS/Gazebo versions observed in the validated workstation.

## 6. Distribution audit

To verify that a checkout contains the complete distribution:

```bash
bash integration/harpia/runtime/audit_distribution.sh
```

Required result:

```text
DISTRIBUTION_READY=1
```

The audit fails on missing model/assets, wrong checksums, missing Garden
packages, workstation backup files, or oversized Git files.

## 7. Expected mission sequence

The successful mission should visibly reach:

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

In the validated SITL run, normal DISARM did not confirm after `LANDED`. The
simulation profile enabled a post-landing force-disarm fallback, after which
PX4 reported disarmed and the FSM reached `MISSION_COMPLETE`. The fallback is
not a real-aircraft validation and is disabled by default in the mission node.

## 8. First reproduction by another team member

The final acceptance test for repository handoff is intentionally simple:

1. use a different supported host/container;
2. clone `main` into `/root/harpia_ws/src/yolo-inference`;
3. run only `run_from_zero.sh`;
4. do not copy files manually from the original workstation;
5. verify Gazebo + annotated camera window;
6. verify the terminal reaches `MISSION_COMPLETE`.

If that test fails, keep the failure log and fix the bootstrap/README rather
than adding undocumented manual steps.

## 9. Model evolution

The frozen model is the simulation baseline. A new model follows:

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
