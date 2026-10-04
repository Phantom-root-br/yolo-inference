import pytest

from harpia_mission import (
    Detection,
    MissionConfig,
    MissionFSM,
    MissionInput,
    MissionState,
    SquareSpiralPlanner,
    TargetObservation,
    TargetSelector,
    iou,
    normalized_error,
)


def test_normalized_error_center_is_zero():
    detection = Detection((540, 260, 740, 460), 0.9)
    ex, ey = normalized_error(detection, 1280, 720)
    assert ex == pytest.approx(0.0)
    assert ey == pytest.approx(0.0)


def test_iou_identical_boxes_is_one():
    box = Detection((10, 20, 30, 40), 0.8)
    assert iou(box, box) == pytest.approx(1.0)


def test_square_spiral_grows_every_two_legs():
    planner = SquareSpiralPlanner(step_m=2.0, max_leg_m=6.0)
    seen = []
    for _ in range(6):
        step = planner.current_step()
        assert step is not None
        seen.append((step.direction.value, step.distance_m, step.dx_m, step.dy_m))
        planner.advance()

    assert seen == [
        ("EAST", 2.0, 2.0, 0.0),
        ("NORTH", 2.0, 0.0, 2.0),
        ("WEST", 4.0, -4.0, 0.0),
        ("SOUTH", 4.0, 0.0, -4.0),
        ("EAST", 6.0, 6.0, 0.0),
        ("NORTH", 6.0, 0.0, 6.0),
    ]


def test_square_spiral_stops_at_limit():
    planner = SquareSpiralPlanner(step_m=2.0, max_leg_m=2.0)
    assert planner.current_step() is not None
    planner.advance()
    assert planner.current_step() is not None
    planner.advance()
    assert planner.current_step() is None


def test_selector_confirms_consistent_target_after_three_hits():
    selector = TargetSelector(confirm_hits=3)
    observations = []
    for x in (100, 105, 110):
        observations.append(
            selector.update(
                [Detection((x, 100, x + 120, 360), 0.8)],
                frame_width=640,
                frame_height=480,
            )
        )

    assert observations[0] is not None and not observations[0].confirmed
    assert observations[1] is not None and not observations[1].confirmed
    assert observations[2] is not None and observations[2].confirmed


def test_selector_prefers_spatial_continuity_over_distant_box():
    selector = TargetSelector(confirm_hits=2)
    selector.update(
        [Detection((100, 100, 200, 350), 0.8)],
        frame_width=640,
        frame_height=480,
    )
    target = selector.update(
        [
            Detection((105, 100, 205, 350), 0.75),
            Detection((500, 100, 620, 350), 0.99),
        ],
        frame_width=640,
        frame_height=480,
    )
    assert target is not None
    assert target.detection.bbox[0] == 105
    assert target.confirmed


def test_selector_resets_after_misses():
    selector = TargetSelector(confirm_hits=2, max_misses=1)
    selector.update(
        [Detection((100, 100, 200, 350), 0.8)],
        frame_width=640,
        frame_height=480,
    )
    assert selector.update([], frame_width=640, frame_height=480) is None
    assert selector.update([], frame_width=640, frame_height=480) is None
    target = selector.update(
        [Detection((100, 100, 200, 350), 0.8)],
        frame_width=640,
        frame_height=480,
    )
    assert target is not None
    assert target.age_frames == 1
    assert not target.confirmed


def target(ex: float, ey: float, *, confirmed: bool = True) -> TargetObservation:
    return TargetObservation(
        detection=Detection((100, 100, 200, 300), 0.9),
        ex_norm=ex,
        ey_norm=ey,
        continuity_score=0.9,
        age_frames=5,
        confirmed=confirmed,
    )


def enter_search(fsm: MissionFSM):
    fsm.tick(MissionInput(preflight_ok=True))
    return fsm.tick(MissionInput(takeoff_reached=True))


def test_preflight_to_takeoff_to_search():
    fsm = MissionFSM()
    decision = fsm.tick(MissionInput(preflight_ok=True))
    assert decision.state == MissionState.TAKEOFF
    assert decision.action == "TAKEOFF"

    decision = fsm.tick(MissionInput(takeoff_reached=True))
    assert decision.state == MissionState.SEARCH
    assert decision.action == "SEARCH_STEP"
    assert decision.payload["direction"] == "EAST"


def test_search_acquire_approach_and_stabilize():
    fsm = MissionFSM(MissionConfig(stable_cycles_required=3))
    enter_search(fsm)

    decision = fsm.tick(MissionInput(target=target(-0.5, 0.1, confirmed=False)))
    assert decision.state == MissionState.ACQUIRE

    decision = fsm.tick(MissionInput(target=target(-0.4, 0.08)))
    assert decision.state == MissionState.TRACK

    decision = fsm.tick(MissionInput(target=target(-0.3, 0.05)))
    assert decision.state == MissionState.APPROACH
    assert decision.action == "ALIGN_TARGET"

    decision = fsm.tick(MissionInput(target=target(0.05, 0.04)))
    assert decision.state == MissionState.STABILIZE
    assert decision.action == "HOLD"

    fsm.tick(MissionInput(target=target(0.04, 0.03)))
    decision = fsm.tick(MissionInput(target=target(0.03, 0.02)))
    assert decision.state == MissionState.LAND_ZONE_SELECT
    assert decision.action == "REQUEST_SAFE_LANDING_ZONE"


def test_land_requires_explicit_safe_zone_then_landed_event():
    fsm = MissionFSM(MissionConfig(stable_cycles_required=1))
    enter_search(fsm)
    fsm.tick(MissionInput(target=target(0.0, 0.0, confirmed=False)))
    fsm.tick(MissionInput(target=target(0.0, 0.0)))
    fsm.tick(MissionInput(target=target(0.0, 0.0)))
    decision = fsm.tick(MissionInput(target=target(0.0, 0.0)))
    assert decision.state == MissionState.LAND_ZONE_SELECT

    decision = fsm.tick(MissionInput())
    assert decision.action == "HOLD"

    decision = fsm.tick(MissionInput(safe_landing_zone_ready=True))
    assert decision.state == MissionState.LAND
    assert decision.action == "LAND_SAFE_ZONE"

    decision = fsm.tick(MissionInput(landed=True))
    assert decision.state == MissionState.COMPLETE


def test_target_loss_during_approach_returns_to_acquire_with_hold():
    fsm = MissionFSM()
    enter_search(fsm)
    fsm.tick(MissionInput(target=target(-0.5, 0.0, confirmed=False)))
    fsm.tick(MissionInput(target=target(-0.4, 0.0)))
    fsm.tick(MissionInput(target=target(-0.3, 0.0)))
    decision = fsm.tick(MissionInput(target=None))
    assert decision.state == MissionState.ACQUIRE
    assert decision.action == "HOLD"
    assert decision.reason == "target_lost"


def test_abort_is_global():
    fsm = MissionFSM()
    decision = fsm.tick(MissionInput(abort=True, abort_reason="manual_test"))
    assert decision.state == MissionState.ABORT
    assert decision.action == "ABORT"
    assert decision.reason == "manual_test"


def test_search_limit_transitions_to_abort():
    fsm = MissionFSM(MissionConfig(search_step_m=2.0, search_max_leg_m=2.0))
    enter_search(fsm)
    fsm.tick(MissionInput(search_step_complete=True))
    decision = fsm.tick(MissionInput(search_step_complete=True))
    assert decision.state == MissionState.ABORT
    assert decision.action == "HOLD"
    assert decision.reason == "search_limit_reached"
