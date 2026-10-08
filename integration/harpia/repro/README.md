# Validated stack freeze

This directory stores the machine-readable freeze for the HARPia YOLO
simulation that reached `MISSION_COMPLETE` on 2026-10-07.

The generated `validated_stack.env` is created by:

```bash
bash integration/harpia/runtime/package_validated_stack.sh
```

It records the model SHA256 and the relevant local source revisions when they
are available.

The purpose is operational reproducibility: another team member should not need
to guess which model, world, mission package or runtime profile produced the
validated run.
