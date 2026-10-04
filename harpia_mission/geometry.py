from __future__ import annotations

from math import hypot

from .models import Detection


def normalized_error(
    detection: Detection,
    frame_width: int,
    frame_height: int,
) -> tuple[float, float]:
    """Return target-center error normalized to approximately [-1, 1]."""
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame dimensions must be positive")

    cx, cy = detection.center
    ex = (cx - frame_width / 2.0) / (frame_width / 2.0)
    ey = (cy - frame_height / 2.0) / (frame_height / 2.0)
    return (_clamp(ex, -1.0, 1.0), _clamp(ey, -1.0, 1.0))


def iou(a: Detection, b: Detection) -> float:
    """Intersection-over-union between two bounding boxes."""
    ax1, ay1, ax2, ay2 = a.bbox
    bx1, by1, bx2, by2 = b.bbox

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return 0.0 if union <= 0.0 else intersection / union


def center_proximity(
    a: Detection,
    b: Detection,
    frame_width: int,
    frame_height: int,
) -> float:
    """Similarity in [0, 1] based on distance between box centers."""
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame dimensions must be positive")

    ax, ay = a.center
    bx, by = b.center
    distance = hypot(ax - bx, ay - by)
    diagonal = hypot(frame_width, frame_height)
    if diagonal == 0.0:
        return 0.0
    return _clamp(1.0 - distance / diagonal, 0.0, 1.0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
