from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    """One detector output in pixel coordinates."""

    bbox: tuple[float, float, float, float]
    confidence: float
    class_name: str = "person"

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


@dataclass(frozen=True)
class TargetObservation:
    """Detection enriched with continuity and normalized image error."""

    detection: Detection
    ex_norm: float
    ey_norm: float
    continuity_score: float
    age_frames: int
    confirmed: bool
