# Validation snapshot — 2026-10-07

This document records the simulation state validated on 2026-10-07 for the
current portable configuration. It is **not** a real-flight qualification
report.

## What is already working

- ROS 2 camera bridge publishes 640-pixel-wide frames.
- Custom top-down model loads and produces person detections.
- First qualifying person detection interrupts the square-spiral search.
- `TARGET_LOCKED` is externally observable.
- The mission preserves the latest visual target instead of requiring every
  inference frame to contain a detection.
- X and Y visual errors are available explicitly from the bounding-box center.
- The current simulation camera mapping under test is:
  - image Y -> local X: -1
  - image X -> local Y: +1

## Main remaining perception issue

The person can remain visibly inside the camera image while YOLO misses several
frames. Long gaps make the vehicle keep pursuing a stale visual target.

This is why the detector/mission thresholds are separated:

```text
candidate detector threshold = 0.05
new target lock threshold     = 0.10
tracking threshold            = 0.05
```

The candidate threshold change is intended to improve recall. It does not mean
that every 0.05 candidate can start a mission lock.

The detector image size is also raised from 416 to 512 for the current
simulation profile.

## Why not simply increase the visual-servo gain

The current logs showed cases where a target was detected, the vehicle started
moving, and then there was a substantial detection gap. Increasing only the
servo gain can make the vehicle overshoot the last stale target.

Perception continuity should be improved first, then the visual servo should be
tuned with frequent bbox updates.

## Current fast-servo starting point

```text
visual_servo_gain          = 1.8
visual_target_max_update_m = 3.5
bbox_ema_alpha             = 1.0
visual_target_alpha        = 1.0
visual_target_lead_sec     = 0.0
```

A new bbox replaces the active steering reference immediately when its
confidence is better or equal. A weaker bbox is held back while the active
reference is fresh, then may replace it after the configured priority hold
(1.25 s in the validated simulation profile).

## End-to-end simulation result

The final monitored run completed the full intended sequence:

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

The normal PX4 disarm command still did not confirm in SITL after `LANDED`.
The simulation-only, post-landing force-disarm fallback then executed and PX4
reported the vehicle disarmed; the FSM emitted `MISSION_COMPLETE` and entered
`COMPLETE`.

The independent annotated-camera viewer also opened successfully and received
its first `640x480` frame from `/yolo/image_annotated`.

This validates the current **simulation integration** on the HARPia workstation.
It does not qualify the detector, thresholds, control law, force-disarm policy,
or landing behavior for real flight.

Before real flight, rebuild the dataset with real top-down imagery and
revalidate model quality, thresholds, camera-axis signs, PX4 control limits,
landing/disarm behavior and failsafes in a controlled environment.
