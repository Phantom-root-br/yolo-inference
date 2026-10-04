from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SearchDirection(str, Enum):
    EAST = "EAST"
    NORTH = "NORTH"
    WEST = "WEST"
    SOUTH = "SOUTH"


_DIRECTION_VECTORS: dict[SearchDirection, tuple[int, int]] = {
    SearchDirection.EAST: (1, 0),
    SearchDirection.NORTH: (0, 1),
    SearchDirection.WEST: (-1, 0),
    SearchDirection.SOUTH: (0, -1),
}


@dataclass(frozen=True)
class SearchStep:
    leg_index: int
    direction: SearchDirection
    distance_m: float
    dx_m: float
    dy_m: float
    turn_after_deg: float = 90.0


class SquareSpiralPlanner:
    """Generate an expanding square spiral around the search origin.

    Leg lengths follow d, d, 2d, 2d, 3d, 3d, ... while direction rotates
    +90 degrees after every completed leg.
    """

    def __init__(self, *, step_m: float = 2.0, max_leg_m: float = 20.0) -> None:
        if step_m <= 0.0:
            raise ValueError("step_m must be positive")
        if max_leg_m < step_m:
            raise ValueError("max_leg_m must be >= step_m")
        self.step_m = step_m
        self.max_leg_m = max_leg_m
        self._leg_index = 0

    @property
    def leg_index(self) -> int:
        return self._leg_index

    def reset(self) -> None:
        self._leg_index = 0

    def current_step(self) -> SearchStep | None:
        distance = (self._leg_index // 2 + 1) * self.step_m
        if distance > self.max_leg_m:
            return None

        directions = list(SearchDirection)
        direction = directions[self._leg_index % len(directions)]
        vx, vy = _DIRECTION_VECTORS[direction]
        return SearchStep(
            leg_index=self._leg_index,
            direction=direction,
            distance_m=distance,
            dx_m=vx * distance,
            dy_m=vy * distance,
        )

    def advance(self) -> SearchStep | None:
        self._leg_index += 1
        return self.current_step()
