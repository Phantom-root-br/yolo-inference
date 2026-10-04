from __future__ import annotations

import importlib.util
import random
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gazebo_spawn_random_human.py"
SPEC = importlib.util.spec_from_file_location("gazebo_spawn_random_human", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sample_pose_is_reproducible_for_same_seed():
    kwargs = {
        "xmin": -12.0,
        "xmax": 12.0,
        "ymin": -12.0,
        "ymax": 12.0,
        "min_origin_distance": 4.0,
    }
    pose_a = MODULE.sample_pose(random.Random(12345), **kwargs)
    pose_b = MODULE.sample_pose(random.Random(12345), **kwargs)
    assert pose_a == pytest.approx(pose_b)


def test_sample_pose_respects_bounds_and_exclusion_radius():
    x, y, yaw = MODULE.sample_pose(
        random.Random(7),
        xmin=-5.0,
        xmax=8.0,
        ymin=-6.0,
        ymax=9.0,
        min_origin_distance=3.0,
    )
    assert -5.0 <= x <= 8.0
    assert -6.0 <= y <= 9.0
    assert (x * x + y * y) ** 0.5 >= 3.0
    assert -3.141592653589793 <= yaw <= 3.141592653589793


def test_sample_pose_rejects_impossible_exclusion_radius():
    with pytest.raises(ValueError, match="raio de exclusao"):
        MODULE.sample_pose(
            random.Random(1),
            xmin=-1.0,
            xmax=1.0,
            ymin=-1.0,
            ymax=1.0,
            min_origin_distance=10.0,
        )
