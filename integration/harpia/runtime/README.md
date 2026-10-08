# HARPia final runtime fixes

This directory contains the two final simulation-runtime fixes found during the
2026-10-07 end-to-end run.

## 1. DISARM after LANDED

Observed final state:

```text
RETURN_HOME_COMPLETE
LANDED
LAND_HOME -> DISARM
DISARM -> ERROR_HOLD
```

PX4 still reported `arming_state=2` after the normal disarm timeout.

The patch keeps the normal disarm request first. In the **simulation launch
profile only**, after 5 seconds in `DISARM` and only after the FSM has already
entered that state from a confirmed `LANDED`, it sends the MAVLink
force-disarm value `param2=21196`.

The mission parameter default is deliberately:

```text
allow_force_disarm_after_landed = false
```

The HARPia simulation launcher patched by this helper explicitly sets it to
`true`.

Do **not** copy that simulation override to a real aircraft without a separate
safety review.

## 2. Annotated camera viewer

The failed run used a full-image `ros2 topic echo --once` gate before opening
the GUI. The subscriber reported repeated lost messages and the gate timed out,
so the viewer was never started.

The replacement viewer:

- opens independently once the detector node exists;
- subscribes directly to `/yolo/image_annotated`;
- uses best-effort sensor-style QoS and depth 1;
- waits for the first frame inside the viewer process;
- inherits `DISPLAY` and `XAUTHORITY` into its tmux window;
- never blocks mission execution.

## Apply to the current HARPia workspace

From the cloned repository:

```bash
export HARPIA_WS=/root/harpia_ws
export YOLO_REPO=$HARPIA_WS/src/yolo-inference

bash $YOLO_REPO/integration/harpia/runtime/apply_and_build.sh
```

Then run:

```bash
bash $YOLO_REPO/integration/harpia/runtime/run_harpia_yolo_with_viewer.sh
```

The tmux session contains a dedicated `camera` window.

## Expected final mission events

```text
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

The patch is idempotent: running `apply_and_build.sh` again should not keep
adding duplicate mission parameters or helper methods.


## Validation result

Validated on 2026-10-07 in the current HARPia SITL setup.

Observed final sequence:

```text
ASCEND_TRACK_COMPLETE
RETURN_HOME_COMPLETE
LANDED
DISARM normal did not confirm
force-disarm POST-LANDED (simulation only)
VEHICLE_DISARMED
MISSION_COMPLETE
DISARM -> COMPLETE
```

The annotated viewer also received its first `640x480` frame successfully.

This closes the two runtime defects for the validated simulation profile. The
force-disarm fallback remains disabled by default and must not be assumed safe
for a real aircraft.
