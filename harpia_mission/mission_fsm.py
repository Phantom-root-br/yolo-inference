from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import TargetObservation
from .search_pattern import SearchStep, SquareSpiralPlanner


class MissionState(str, Enum):
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    SEARCH = "SEARCH"
    ACQUIRE = "ACQUIRE"
    TRACK = "TRACK"
    APPROACH = "APPROACH"
    STABILIZE = "STABILIZE"
    LAND_ZONE_SELECT = "LAND_ZONE_SELECT"
    LAND = "LAND"
    COMPLETE = "COMPLETE"
    ABORT = "ABORT"


@dataclass(frozen=True)
class MissionConfig:
    takeoff_height_m: float = 5.0
    approach_deadband: float = 0.10
    stable_cycles_required: int = 3
    search_step_m: float = 2.0
    search_max_leg_m: float = 20.0


@dataclass(frozen=True)
class MissionInput:
    preflight_ok: bool = False
    takeoff_reached: bool = False
    search_step_complete: bool = False
    target: TargetObservation | None = None
    safe_landing_zone_ready: bool = False
    landed: bool = False
    abort: bool = False
    abort_reason: str | None = None


@dataclass(frozen=True)
class ActionDecision:
    state: MissionState
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


class MissionFSM:
    """Perception-driven mission state machine with no PX4 dependency."""

    def __init__(self, config: MissionConfig | None = None) -> None:
        self.config = config or MissionConfig()
        if self.config.stable_cycles_required < 1:
            raise ValueError("stable_cycles_required must be >= 1")
        self.state = MissionState.PREFLIGHT
        self._stable_cycles = 0
        self.search = SquareSpiralPlanner(
            step_m=self.config.search_step_m,
            max_leg_m=self.config.search_max_leg_m,
        )

    def tick(self, event: MissionInput) -> ActionDecision:
        if event.abort:
            self.state = MissionState.ABORT
            return self._decision("ABORT", reason=event.abort_reason or "abort_requested")

        if self.state == MissionState.PREFLIGHT:
            if event.preflight_ok:
                self.state = MissionState.TAKEOFF
                return self._decision(
                    "TAKEOFF",
                    height_m=self.config.takeoff_height_m,
                )
            return self._decision("WAIT_PREFLIGHT")

        if self.state == MissionState.TAKEOFF:
            if event.takeoff_reached:
                self.state = MissionState.SEARCH
                self.search.reset()
                return self._search_decision()
            return self._decision("TAKEOFF", height_m=self.config.takeoff_height_m)

        if self.state == MissionState.SEARCH:
            if event.target is not None:
                self.state = MissionState.ACQUIRE
                return self._decision(
                    "HOLD",
                    target_confirmed=event.target.confirmed,
                    target_confidence=event.target.detection.confidence,
                )
            if event.search_step_complete:
                self.search.advance()
            return self._search_decision()

        if self.state == MissionState.ACQUIRE:
            if event.target is None:
                self.state = MissionState.SEARCH
                return self._search_decision()
            if event.target.confirmed:
                self.state = MissionState.TRACK
                return self._target_decision("HOLD", event.target)
            return self._target_decision("HOLD", event.target)

        if self.state == MissionState.TRACK:
            if event.target is None:
                self.state = MissionState.ACQUIRE
                return self._decision("HOLD", reason="target_lost")
            if not event.target.confirmed:
                self.state = MissionState.ACQUIRE
                return self._target_decision("HOLD", event.target)
            self.state = MissionState.APPROACH
            return self._approach_or_stabilize(event.target)

        if self.state == MissionState.APPROACH:
            if event.target is None or not event.target.confirmed:
                self.state = MissionState.ACQUIRE
                return self._decision("HOLD", reason="target_lost")
            return self._approach_or_stabilize(event.target)

        if self.state == MissionState.STABILIZE:
            if event.target is None or not event.target.confirmed:
                self._stable_cycles = 0
                self.state = MissionState.ACQUIRE
                return self._decision("HOLD", reason="target_lost")
            if not self._inside_deadband(event.target):
                self._stable_cycles = 0
                self.state = MissionState.APPROACH
                return self._target_decision("ALIGN_TARGET", event.target)

            self._stable_cycles += 1
            if self._stable_cycles >= self.config.stable_cycles_required:
                self.state = MissionState.LAND_ZONE_SELECT
                return self._decision(
                    "REQUEST_SAFE_LANDING_ZONE",
                    stable_cycles=self._stable_cycles,
                )
            return self._target_decision(
                "HOLD",
                event.target,
                stable_cycles=self._stable_cycles,
            )

        if self.state == MissionState.LAND_ZONE_SELECT:
            if event.safe_landing_zone_ready:
                self.state = MissionState.LAND
                return self._decision("LAND_SAFE_ZONE")
            return self._decision("HOLD", reason="waiting_safe_landing_zone")

        if self.state == MissionState.LAND:
            if event.landed:
                self.state = MissionState.COMPLETE
                return self._decision("MISSION_COMPLETE")
            return self._decision("LAND_SAFE_ZONE")

        if self.state == MissionState.COMPLETE:
            return self._decision("MISSION_COMPLETE")

        return self._decision("ABORT", reason="mission_aborted")

    def _approach_or_stabilize(self, target: TargetObservation) -> ActionDecision:
        if self._inside_deadband(target):
            self.state = MissionState.STABILIZE
            self._stable_cycles = 1
            return self._target_decision(
                "HOLD",
                target,
                stable_cycles=self._stable_cycles,
            )
        self.state = MissionState.APPROACH
        self._stable_cycles = 0
        return self._target_decision("ALIGN_TARGET", target)

    def _inside_deadband(self, target: TargetObservation) -> bool:
        d = self.config.approach_deadband
        return abs(target.ex_norm) <= d and abs(target.ey_norm) <= d

    def _search_decision(self) -> ActionDecision:
        step = self.search.current_step()
        if step is None:
            self.state = MissionState.ABORT
            return self._decision("HOLD", reason="search_limit_reached")
        return self._decision("SEARCH_STEP", **self._search_payload(step))

    def _target_decision(
        self,
        action: str,
        target: TargetObservation,
        **extra: Any,
    ) -> ActionDecision:
        return self._decision(
            action,
            ex_norm=target.ex_norm,
            ey_norm=target.ey_norm,
            target_confidence=target.detection.confidence,
            continuity_score=target.continuity_score,
            target_age_frames=target.age_frames,
            target_confirmed=target.confirmed,
            **extra,
        )

    @staticmethod
    def _search_payload(step: SearchStep) -> dict[str, Any]:
        return {
            "leg_index": step.leg_index,
            "direction": step.direction.value,
            "distance_m": step.distance_m,
            "dx_m": step.dx_m,
            "dy_m": step.dy_m,
            "turn_after_deg": step.turn_after_deg,
        }

    def _decision(self, action: str, reason: str | None = None, **payload: Any) -> ActionDecision:
        return ActionDecision(
            state=self.state,
            action=action,
            payload=payload,
            reason=reason,
        )
