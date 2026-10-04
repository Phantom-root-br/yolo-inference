"""Mission logic for HARPia perception-driven behaviors.

This package intentionally does not talk to PX4. It produces semantic actions
that a separate flight adapter can translate into the vehicle-control stack.
"""

from .geometry import center_proximity, iou, normalized_error
from .mission_fsm import ActionDecision, MissionConfig, MissionFSM, MissionInput, MissionState
from .models import Detection, TargetObservation
from .search_pattern import SearchDirection, SearchStep, SquareSpiralPlanner
from .target_selector import TargetSelector

__all__ = [
    "ActionDecision",
    "Detection",
    "MissionConfig",
    "MissionFSM",
    "MissionInput",
    "MissionState",
    "SearchDirection",
    "SearchStep",
    "SquareSpiralPlanner",
    "TargetObservation",
    "TargetSelector",
    "center_proximity",
    "iou",
    "normalized_error",
]
