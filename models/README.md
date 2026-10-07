# Models

Binary YOLO weights are not committed to normal Git history.

Current simulation model name:

```text
harpia_person_topdown_pilot_v2.pt
```

Place the file here for the default simulation config:

```text
models/harpia_person_topdown_pilot_v2.pt
```

or point the ROS parameter `model_path` to an absolute path.

The current custom weight is a **simulation pilot model**, not a real-flight
release. See `docs/RETRAINING.md` before using the system with real imagery.

For a team release, prefer one of:

1. GitHub Release asset with checksum;
2. Git LFS;
3. an internal artifact store.

Whichever mechanism is chosen, keep model version and dataset version explicit.
