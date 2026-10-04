from __future__ import annotations

from dataclasses import dataclass

from .geometry import center_proximity, iou, normalized_error
from .models import Detection, TargetObservation


@dataclass(frozen=True)
class SelectorWeights:
    iou: float = 0.50
    center: float = 0.30
    confidence: float = 0.20


class TargetSelector:
    """Lightweight single-human continuity selector.

    The selector is intentionally not an identity tracker. It assumes the
    mission normally has one relevant person and scores new boxes by spatial
    continuity plus detector confidence.
    """

    def __init__(
        self,
        *,
        confirm_hits: int = 3,
        max_misses: int = 5,
        min_continuity_score: float = 0.25,
        weights: SelectorWeights | None = None,
    ) -> None:
        if confirm_hits < 1:
            raise ValueError("confirm_hits must be >= 1")
        if max_misses < 0:
            raise ValueError("max_misses must be >= 0")
        self.confirm_hits = confirm_hits
        self.max_misses = max_misses
        self.min_continuity_score = min_continuity_score
        self.weights = weights or SelectorWeights()
        self._last: Detection | None = None
        self._hits = 0
        self._misses = 0
        self._age = 0

    def reset(self) -> None:
        self._last = None
        self._hits = 0
        self._misses = 0
        self._age = 0

    def update(
        self,
        detections: list[Detection],
        *,
        frame_width: int,
        frame_height: int,
    ) -> TargetObservation | None:
        people = [d for d in detections if d.class_name == "person"]
        if not people:
            self._misses += 1
            if self._misses > self.max_misses:
                self.reset()
            return None

        selected, score, continued = self._select_candidate(
            people,
            frame_width=frame_width,
            frame_height=frame_height,
        )

        if continued:
            self._hits += 1
            self._age += 1
        else:
            self._hits = 1
            self._age = 1

        self._last = selected
        self._misses = 0
        ex_norm, ey_norm = normalized_error(selected, frame_width, frame_height)
        return TargetObservation(
            detection=selected,
            ex_norm=ex_norm,
            ey_norm=ey_norm,
            continuity_score=score,
            age_frames=self._age,
            confirmed=self._hits >= self.confirm_hits,
        )

    def _select_candidate(
        self,
        people: list[Detection],
        *,
        frame_width: int,
        frame_height: int,
    ) -> tuple[Detection, float, bool]:
        if self._last is None:
            selected = max(people, key=lambda d: d.confidence)
            return selected, selected.confidence, False

        ranked = [
            (
                self._continuity_score(
                    self._last,
                    candidate,
                    frame_width=frame_width,
                    frame_height=frame_height,
                ),
                candidate,
            )
            for candidate in people
        ]
        score, selected = max(ranked, key=lambda item: item[0])
        return selected, score, score >= self.min_continuity_score

    def _continuity_score(
        self,
        previous: Detection,
        current: Detection,
        *,
        frame_width: int,
        frame_height: int,
    ) -> float:
        return (
            self.weights.iou * iou(previous, current)
            + self.weights.center
            * center_proximity(previous, current, frame_width, frame_height)
            + self.weights.confidence * current.confidence
        )
