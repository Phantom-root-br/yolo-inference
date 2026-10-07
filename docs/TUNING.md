# Detector and visual-servo tuning

## Current simulation objective

The mission is:

```text
TAKEOFF 4 m
-> SEARCH
-> first detection above lock threshold
-> TARGET_LOCKED
-> center bounding box in camera
-> track centered for 30 s at 4 m
-> descend while tracking to 1 m
-> track centered for 30 s at 1 m
-> ascend while tracking to 4 m
-> return HOME
-> LAND
-> DISARM
```

## Detection parameters

### Candidate threshold

`confidence_threshold` belongs to the detector.

Current simulation recommendation:

```text
0.05
```

It intentionally sits below the mission lock threshold so weak frames can
still update a target that has already been acquired.

### Lock threshold

Current simulation:

```text
confirmation_confidence = 0.10
confirmation_frames = 1
```

The first qualifying detection interrupts the square-spiral search.

### Tracking threshold

Current simulation:

```text
tracking_min_confidence = 0.05
```

This is a hysteresis policy. Acquiring a target and maintaining a target do not
need the same confidence.

### Image size

Suggested starting points:

| Platform | imgsz |
|---|---:|
| old CPU / simulation | 512 |
| modern CPU | 512 or 640 |
| GPU | 640 |

A larger image can improve small-person recall but increases latency.

Measure end-to-end behavior; a detector with slightly better per-frame recall
can still track worse if inference becomes too slow.

## Miss handling

A missed inference frame must not erase the last visual waypoint.

Current simulation policy:

```text
detection_max_age_sec = 4.0
```

New bbox:
- replaces the previous visual target immediately.

Empty frame:
- vehicle continues toward the last target.

Long target loss:
- mission should hold/reacquire according to state policy;
- it must not resume the original spiral after TARGET_LOCKED.

## Visual servo

The control objective is the **bounding-box center**, not the actor world
coordinate:

```text
error_x = bbox_center_x - image_width/2
error_y = bbox_center_y - image_height/2
```

Both axes must be corrected simultaneously.

Current simulation camera mapping:

```text
image Y -> local X : -1
image X -> local Y : +1
```

In HARPia parameter names:

```text
local_x_from_image_y_sign = -1.0
local_y_from_image_x_sign = +1.0
```

These signs are camera-mount specific and must be revalidated on real hardware.

Do **not** automatically flip signs during normal tracking. A moving person can
make a naive sign-learning rule interpret target motion as controller failure.

## Fast current starting profile

```text
visual_servo_gain             = 1.8
visual_target_max_update_m    = 3.5
bbox_ema_alpha                = 1.0
visual_target_alpha           = 1.0
visual_target_lead_sec        = 0.0
alignment_hold_sec            = 0.5
```

The latest bbox wins. No EMA delay is introduced while the target is moving.

At lower altitude, pixel-to-meter conversion must scale with current altitude
so the controller does not overcorrect at 1 m.

## How to diagnose axis sign

Watch:

```text
BBOX_CHASE ... err_px=(X,Y)
```

For a correct controller, the absolute error should generally converge after a
new target is commanded.

If only `|X|` grows consistently, inspect the image-X to local-Y sign.

If only `|Y|` grows consistently, inspect the image-Y to local-X sign.

Do not change gain until the signs are correct.

## How to diagnose insufficient speed

If signs are correct and detections are frequent but the target remains near
the edge:

1. increase `visual_servo_gain` gradually;
2. increase `visual_target_max_update_m`;
3. inspect PX4 position-controller velocity limits;
4. consider velocity feed-forward in the mission adapter.

If detections have multi-second gaps, first improve detector recall/latency.
Increasing servo gain alone can make the aircraft overshoot a stale target.
