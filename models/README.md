# Models

The validated simulation model is tracked with the reproducible HARPia stack:

```text
models/harpia_person_topdown_pilot_v2.pt
```

Its exact size and SHA256 are frozen in:

```text
integration/harpia/repro/validated_stack.env
```

`bootstrap_workspace.sh` verifies the checksum before starting the mission.

The current custom weight is a **top-down simulation pilot model**. It is not a
real-flight model and its simulation confidence thresholds must not be treated
as validated thresholds for a physical aircraft.

For future model versions, do not silently overwrite the validated baseline.
Follow `docs/MODEL_UPGRADE_POLICY.md`: train a candidate, compare it against
the baseline, run continuous-video and ROS regressions, then run the complete
mission before promotion.

Large future weights may move to Git LFS, a GitHub Release asset, or an internal
artifact store, but every promoted model must keep a version and checksum.
