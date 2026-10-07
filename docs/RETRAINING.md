# Retraining the top-down person detector

## Why retraining is required

The current custom model is a simulation pilot. It demonstrates that a
top-down human can be learned, but it is not sufficient evidence for real
flight.

Simulation-to-real changes include:

- human appearance and clothing;
- camera optics and distortion;
- exposure and white balance;
- motion blur and vibration;
- shadows and outdoor illumination;
- background texture;
- person scale at different altitudes;
- partial occlusion;
- compression and transport artifacts.

Real deployment therefore requires a new dataset and a new validation cycle.

## Dataset collection plan

Collect complete sessions, not isolated cherry-picked positives.

Recommended diversity:

- 1 m, 2 m, 3 m, 4 m and higher operational altitudes;
- center, edges and corners of the image;
- stationary and walking humans;
- different walking directions;
- different people, clothing and body shapes;
- sun, shade, cloudy light and indoor light when relevant;
- grass, concrete, asphalt, dirt and visually cluttered backgrounds;
- partial person visibility;
- motion blur;
- frames with no person;
- hard negatives that resemble a top-down human.

Store metadata for each capture session:

```text
session_id
date
camera
resolution
altitude
site
person_id_anonymized
lighting
notes
```

## Critical split rule

**Never split adjacent video frames randomly between train and validation.**

Near-identical frames leak scene/person information and can make validation
look much better than real generalization.

Split by whole session, flight, site and preferably person:

```text
train:
  session_A
  session_B
  session_C

val:
  session_D

test:
  session_E
```

A final real-flight-style test set should stay untouched until model selection
is complete.

## Labels

YOLO detection label per object:

```text
class_id center_x center_y width height
```

Coordinates are normalized to image width/height.

For a one-class dataset:

```text
0 = person
```

Negative frames are valid and should have an empty label file.

## Dataset YAML

Example:

```yaml
path: /data/harpia_person
train: images/train
val: images/val
test: images/test

names:
  0: person
```

## Train

The repository contains `scripts/train_topdown_person.py`.

Example:

```bash
python scripts/train_topdown_person.py   --data /data/harpia_person/data.yaml   --base-model yolo11n.pt   --imgsz 640   --epochs 100   --batch 16   --device 0   --name harpia_person_real_v1
```

For CPU-only experiments, reduce `batch` and expect much slower training.

## What to measure

Do not select a model only by mAP.

For this mission, also measure:

- recall at operational object size;
- missed-frame rate while the person is visible;
- longest consecutive detection gap;
- false locks per minute on negative scenes;
- confidence distribution for positives and negatives;
- end-to-end inference latency;
- centralization success rate when coupled to the controller.

Useful operational thresholds are selected from those distributions.

## Two-threshold operational policy

A practical deployment may use:

```text
candidate threshold < lock threshold
```

Example starting point only:

```text
candidate: 0.05
lock:      0.10
tracking:  0.05
```

These numbers are currently simulation-oriented. They **must not** be copied
to a real aircraft without validation.

## Hard-negative loop

After each field test:

1. save false-positive frames;
2. save visible-human frames that were missed;
3. label them;
4. add them to the dataset using session-aware splits;
5. retrain;
6. rerun the untouched validation/test sets;
7. compare missed-frame gap and false-lock metrics.

This loop is more valuable than continuously lowering the confidence threshold.

## Model versioning

Recommended naming:

```text
harpia_person_sim_v2.pt
harpia_person_real_v1.pt
harpia_person_real_v2.pt
```

For every released weight keep:

- training command;
- dataset revision;
- Ultralytics version;
- base model;
- image size;
- metrics;
- threshold recommendation;
- checksum.

Do not silently replace a weight file while keeping the same version name.
