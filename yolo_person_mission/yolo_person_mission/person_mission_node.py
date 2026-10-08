#!/usr/bin/env python3

"""
HARPia / Nautilus - YOLO Person Mission

Mission:

WAIT_POSITION
    -> WARMUP_OFFBOARD
    -> ENGAGE_OFFBOARD
    -> ARM
    -> TAKEOFF
    -> SEARCH_SQUARE_SPIRAL
    -> CENTER_TARGET
    -> TRACK_CENTER_30S
    -> RETURN_HOME
    -> PAUSED

Important architectural boundary:

    yolo_person_detector
             |
             | ROS messages only
             v
    yolo_person_mission
             |
             | px4_msgs
             v
            PX4

This file contains no Gazebo dependency.

The mission can therefore be reused with a real camera as long as
the perception layer keeps publishing the same ROS interfaces.
"""

import math
import time
from enum import Enum, auto
from typing import List, Optional, Tuple

import rclpy

from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)

from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from std_msgs.msg import String

from yolo_person_interfaces.msg import (
    PersonDetection,
    PersonDetectionArray,
)


class State(Enum):
    WAIT_POSITION = auto()
    WARMUP_OFFBOARD = auto()
    ENGAGE_OFFBOARD = auto()
    ARM = auto()
    TAKEOFF = auto()
    SEARCH_SQUARE_SPIRAL = auto()
    CENTER_TARGET = auto()
    TRACK_CENTER_30S = auto()
    DESCEND_TRACK_1M = auto()
    TRACK_LOW_30S = auto()
    ASCEND_TRACK_4M = auto()
    RETURN_HOME = auto()
    LAND_HOME = auto()
    DISARM = auto()
    COMPLETE = auto()
    PAUSED = auto()
    ERROR_HOLD = auto()


def generate_square_spiral(
    step_m: float,
    max_radius_m: float,
) -> List[Tuple[float, float]]:
    """
    Generate square-spiral offsets around (0, 0).

    With step=1:

        (1,0)
        (1,1)
        (0,1)
        (-1,1)
        (-1,0)
        (-1,-1)
        (0,-1)
        (1,-1)
        (2,-1)
        (2,0)
        (2,1)
        (2,2)
        ...

    Coordinates are LOCAL PX4 offsets relative to home.
    """

    if step_m <= 0.0:
        raise ValueError('spiral_step_m must be > 0')

    if max_radius_m < step_m:
        raise ValueError(
            'spiral_max_radius_m must be >= spiral_step_m'
        )

    x = 0.0
    y = 0.0

    directions = [
        (1.0, 0.0),
        (0.0, 1.0),
        (-1.0, 0.0),
        (0.0, -1.0),
    ]

    direction_index = 0
    segment_length = 1

    points: List[Tuple[float, float]] = []

    while True:

        for _ in range(2):

            dx, dy = directions[
                direction_index % 4
            ]

            for _ in range(segment_length):

                x += dx * step_m
                y += dy * step_m

                if (
                    abs(x) > max_radius_m + 1e-6
                    or abs(y) > max_radius_m + 1e-6
                ):
                    return points

                points.append(
                    (round(x, 6), round(y, 6))
                )

            direction_index += 1

        segment_length += 1


class YoloPersonMission(Node):

    def __init__(self) -> None:
        super().__init__('yolo_person_mission')

        # HARPia visual-servo / mission phase parameters.
        # Persistent visual-target controller.
        # Visual target arbitration.
        #
        # A better/equal-confidence bbox replaces the
        # currently steering bbox immediately.
        #
        # A weaker bbox only replaces it after the current
        # reference has aged, avoiding both jitter and a
        # permanently frozen high-confidence bbox.
        # Simulation-only post-landing DISARM fallback.
        #
        # Keep FALSE by default for portability/real-aircraft safety.
        self.declare_parameter(
            'allow_force_disarm_after_landed',
            False,
        )
        self.declare_parameter(
            'force_disarm_after_sec',
            5.0,
        )
        self.declare_parameter(
            'disarm_timeout_sec',
            20.0,
        )

        self.declare_parameter(
            'bbox_priority_hold_sec',
            1.25,
        )

        self.declare_parameter(
            'bbox_confidence_epsilon',
            0.0,
        )

        self.declare_parameter(
            'visual_servo_gain',
            1.80,
        )

        self.declare_parameter(
            'visual_target_alpha',
            0.85,
        )

        self.declare_parameter(
            'visual_target_max_update_m',
            1.50,
        )

        self.declare_parameter(
            'visual_target_lead_sec',
            0.60,
        )

        self.declare_parameter(
            'visual_target_max_speed_mps',
            0.80,
        )

        self.declare_parameter('bbox_ema_alpha', 0.80)
        self.declare_parameter('low_altitude_m', 1.0)
        self.declare_parameter('low_track_duration_sec', 30.0)
        self.declare_parameter('vertical_tolerance_m', 0.25)

        self.bbox_ema_alpha = float(
            self.get_parameter('bbox_ema_alpha').value
        )
        self.low_altitude = float(
            self.get_parameter('low_altitude_m').value
        )
        self.low_track_duration = float(
            self.get_parameter('low_track_duration_sec').value
        )
        self.vertical_tolerance = float(
            self.get_parameter('vertical_tolerance_m').value
        )

        self.smoothed_center_x = None
        self.smoothed_center_y = None
        self.high_track_accum = 0.0
        self.low_track_accum = 0.0
        self.phase_last_tick = time.monotonic()


        # =====================================================
        # Parameters
        # =====================================================

        self.declare_parameter(
            'flight_altitude_m',
            4.0,
        )

        self.declare_parameter(
            'takeoff_tolerance_m',
            0.30,
        )

        self.declare_parameter(
            'waypoint_tolerance_m',
            0.30,
        )

        self.declare_parameter(
            'return_tolerance_m',
            0.30,
        )

        self.declare_parameter(
            'spiral_step_m',
            1.0,
        )

        self.declare_parameter(
            'spiral_max_radius_m',
            4.0,
        )

        self.declare_parameter(
            'confirmation_confidence',
            0.85,
        )

        self.declare_parameter(
            'confirmation_frames',
            5,
        )

        self.declare_parameter(
            'detection_max_age_sec',
            0.50,
        )

        self.declare_parameter(
            'tracking_min_confidence',
            0.50,
        )

        self.declare_parameter(
            'target_loss_timeout_sec',
            1.0,
        )

        self.declare_parameter(
            'alignment_margin_px',
            20.0,
        )

        self.declare_parameter(
            'alignment_hold_sec',
            1.0,
        )

        self.declare_parameter(
            'meters_per_pixel',
            0.0045,
        )

        self.declare_parameter(
            'max_alignment_step_m',
            0.25,
        )

        self.declare_parameter(
            'local_x_from_image_y_sign',
            1.0,
        )

        self.declare_parameter(
            'local_y_from_image_x_sign',
            1.0,
        )

        self.declare_parameter(
            'track_duration_sec',
            30.0,
        )

        # =====================================================
        # Read parameters
        # =====================================================

        self.flight_altitude = float(
            self.get_parameter(
                'flight_altitude_m'
            ).value
        )

        self.takeoff_tolerance = float(
            self.get_parameter(
                'takeoff_tolerance_m'
            ).value
        )

        self.waypoint_tolerance = float(
            self.get_parameter(
                'waypoint_tolerance_m'
            ).value
        )

        self.return_tolerance = float(
            self.get_parameter(
                'return_tolerance_m'
            ).value
        )

        self.spiral_step = float(
            self.get_parameter(
                'spiral_step_m'
            ).value
        )

        self.spiral_max_radius = float(
            self.get_parameter(
                'spiral_max_radius_m'
            ).value
        )

        self.confirmation_confidence = float(
            self.get_parameter(
                'confirmation_confidence'
            ).value
        )

        self.confirmation_frames = int(
            self.get_parameter(
                'confirmation_frames'
            ).value
        )

        self.detection_max_age = float(
            self.get_parameter(
                'detection_max_age_sec'
            ).value
        )

        self.tracking_min_confidence = float(
            self.get_parameter(
                'tracking_min_confidence'
            ).value
        )

        self.target_loss_timeout = float(
            self.get_parameter(
                'target_loss_timeout_sec'
            ).value
        )

        self.alignment_margin = float(
            self.get_parameter(
                'alignment_margin_px'
            ).value
        )

        self.alignment_hold_sec = float(
            self.get_parameter(
                'alignment_hold_sec'
            ).value
        )

        self.meters_per_pixel = float(
            self.get_parameter(
                'meters_per_pixel'
            ).value
        )

        self.max_alignment_step = float(
            self.get_parameter(
                'max_alignment_step_m'
            ).value
        )

        self.x_from_image_y_sign = float(
            self.get_parameter(
                'local_x_from_image_y_sign'
            ).value
        )

        self.y_from_image_x_sign = float(
            self.get_parameter(
                'local_y_from_image_x_sign'
            ).value
        )

        self.track_duration = float(
            self.get_parameter(
                'track_duration_sec'
            ).value
        )

        if self.confirmation_frames < 1:
            raise ValueError(
                'confirmation_frames must be >= 1'
            )

        # =====================================================
        # PX4 QoS
        # =====================================================

        qos_px4 = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # =====================================================
        # PX4 publishers
        # =====================================================

        self.offboard_pub = self.create_publisher(
            OffboardControlMode,
            '/fmu/in/offboard_control_mode',
            10,
        )

        self.trajectory_pub = self.create_publisher(
            TrajectorySetpoint,
            '/fmu/in/trajectory_setpoint',
            10,
        )

        self.command_pub = self.create_publisher(
            VehicleCommand,
            '/fmu/in/vehicle_command',
            10,
        )

        # =====================================================
        # PX4 subscriptions
        # =====================================================

        self.create_subscription(
            VehicleLocalPosition,
            '/fmu/out/vehicle_local_position',
            self.local_position_callback,
            qos_px4,
        )

        self.create_subscription(
            VehicleStatus,
            '/fmu/out/vehicle_status',
            self.vehicle_status_callback,
            qos_px4,
        )

        # =====================================================
        # YOLO subscription
        #
        # We use PersonDetectionArray because the detector
        # publishes it for every processed frame, including
        # frames with ZERO people.
        #
        # This makes "5 consecutive frames" measurable.
        # =====================================================

        self.create_subscription(
            PersonDetectionArray,
            '/yolo/person_detections',
            self.detections_callback,
            10,
        )

        # =====================================================
        # Mission observability
        # =====================================================

        self.event_pub = self.create_publisher(
            String,
            '/yolo/mission_event',
            10,
        )

        self.state_pub = self.create_publisher(
            String,
            '/yolo/mission_state',
            10,
        )

        # =====================================================
        # Vehicle state
        # =====================================================

        self.position: Optional[
            VehicleLocalPosition
        ] = None

        self.vehicle_status: Optional[
            VehicleStatus
        ] = None

        # Home / target use PX4 LOCAL NED coordinates.
        self.home_x = 0.0
        self.home_y = 0.0
        self.home_z = 0.0

        self.target_x = 0.0
        self.target_y = 0.0
        self.target_z = 0.0
        self.target_yaw = 0.0

        # =====================================================
        # Detection state
        # =====================================================

        self.latest_detection: Optional[
            PersonDetection
        ] = None

        self.latest_detection_monotonic = 0.0

        self.detection_seq = 0
        self.last_alignment_seq = -1

        self.strong_detection_streak = 0

        # =====================================================
        # Mission state
        # =====================================================

        self.state = State.WAIT_POSITION
        self.state_started = time.monotonic()

        self.last_command_time = 0.0

        self.aligned_since: Optional[
            float
        ] = None

        self.center_event_sent = False

        self.track_started: Optional[
            float
        ] = None

        # =====================================================
        # Search path
        # =====================================================

        self.spiral_offsets = (
            generate_square_spiral(
                self.spiral_step,
                self.spiral_max_radius,
            )
        )

        self.spiral_index = 0

        # 20 Hz keeps OFFBOARD heartbeat/setpoint alive.
        self.timer = self.create_timer(
            0.05,
            self.control_loop,
        )

        self.get_logger().info(
            'HARPia YOLO Person Mission pronta.'
        )

        self.get_logger().info(
            f'altitude={self.flight_altitude:.2f} m | '
            f'confirmação={self.confirmation_confidence:.2f} '
            f'x {self.confirmation_frames} frames | '
            f'espiral step={self.spiral_step:.2f} m | '
            f'raio={self.spiral_max_radius:.2f} m | '
            f'track={self.track_duration:.1f} s'
        )

        self.get_logger().info(
            f'espiral possui '
            f'{len(self.spiral_offsets)} waypoints'
        )

        self.publish_state()

    # =========================================================
    # Basic ROS / PX4 helpers
    # =========================================================

    def now_us(self) -> int:
        return int(
            self.get_clock().now().nanoseconds
            / 1000
        )

    def local_position_callback(
        self,
        msg: VehicleLocalPosition,
    ) -> None:
        self.position = msg

    def vehicle_status_callback(
        self,
        msg: VehicleStatus,
    ) -> None:
        self.vehicle_status = msg

    # =========================================================
    # YOLO detections
    # =========================================================

    def detections_callback(
        self,
        msg: PersonDetectionArray,
    ) -> None:

        # A miss does NOT cancel navigation.
        # Keep flying toward the last visual XY target.
        if not msg.detections:
            return

        best = max(
            msg.detections,
            key=lambda detection: float(
                detection.confidence
            ),
        )

        if (
            best.class_name.strip().lower()
            != 'person'
        ):
            return

        confidence = float(
            best.confidence
        )

        now = time.monotonic()

        # The newest bbox always replaces the previous bbox.
        self.latest_detection = best
        self.latest_detection_monotonic = now
        self.detection_seq += 1

        visual_states = (
            State.CENTER_TARGET,
            State.TRACK_CENTER_30S,
            State.DESCEND_TRACK_1M,
            State.TRACK_LOW_30S,
            State.ASCEND_TRACK_4M,
        )

        # First detection above threshold:
        # stop spiral NOW and generate the first visual waypoint NOW.
        if (
            self.state
            == State.SEARCH_SQUARE_SPIRAL
        ):

            if (
                confidence
                < self.confirmation_confidence
            ):
                return

            self.strong_detection_streak = 1

            self.publish_event(
                'PERSON_CONFIRMED'
            )

            self.publish_event(
                'TARGET_LOCKED'
            )

            self.get_logger().warning(
                'TARGET LOCKED: '
                f'confidence={confidence:.3f} '
                f'bbox_center=('
                f'{best.center_x:.1f},'
                f'{best.center_y:.1f})'
            )

            self.transition(
                State.CENTER_TARGET,
                'primeira bbox YOLO acima do limiar',
            )

            # Force this exact bbox to generate movement immediately.
            self.last_alignment_seq = -1

            self.apply_alignment_correction(
                best
            )

            return

        # During all visual phases, a new detection immediately
        # overwrites the old visual waypoint.
        if self.state in visual_states:

            if (
                confidence
                < self.tracking_min_confidence
            ):
                return

            self.apply_alignment_correction(
                best
            )

            return

    def fresh_detection(
        self,
    ) -> Optional[PersonDetection]:

        if self.latest_detection is None:
            return None

        age = (
            time.monotonic()
            - self.latest_detection_monotonic
        )

        if age > self.detection_max_age:
            return None

        if (
            self.latest_detection
            .class_name
            .strip()
            .lower()
            != 'person'
        ):
            return None

        if (
            float(
                self.latest_detection.confidence
            )
            < self.tracking_min_confidence
        ):
            return None

        return self.latest_detection

    def strong_target_confirmed(
        self,
    ) -> bool:

        detection = self.fresh_detection()

        if detection is None:
            return False

        if (
            float(detection.confidence)
            < self.confirmation_confidence
        ):
            return False

        return (
            self.strong_detection_streak
            >= self.confirmation_frames
        )

    # =========================================================
    # Mission reporting
    # =========================================================

    def publish_event(
        self,
        event: str,
    ) -> None:

        msg = String()
        msg.data = event

        self.event_pub.publish(msg)

        self.get_logger().warning(
            f'MISSION_EVENT: {event}'
        )

    def publish_state(
        self,
    ) -> None:

        msg = String()
        msg.data = self.state.name

        self.state_pub.publish(msg)

    def transition(
        self,
        new_state: State,
        reason: str = '',
    ) -> None:

        old_state = self.state

        self.state = new_state
        self.state_started = time.monotonic()

        self.publish_state()

        suffix = (
            f' | {reason}'
            if reason
            else ''
        )

        self.get_logger().warning(
            f'STATE: '
            f'{old_state.name} -> '
            f'{new_state.name}'
            f'{suffix}'
        )

        # State-specific entry behavior.

        if new_state == State.TAKEOFF:

            self.target_x = self.home_x
            self.target_y = self.home_y
            self.target_z = (
                self.home_z
                - self.flight_altitude
            )

            self.get_logger().warning(
                'TAKEOFF target '
                f'x={self.target_x:.2f} '
                f'y={self.target_y:.2f} '
                f'z={self.target_z:.2f}'
            )

        elif new_state == State.SEARCH_SQUARE_SPIRAL:

            self.strong_detection_streak = 0
            self.spiral_index = 0

            self.set_spiral_target()

        elif new_state == State.CENTER_TARGET:

            self.aligned_since = None
            self.last_alignment_seq = -1

            if self.position is not None:
                self.target_x = float(
                    self.position.x
                )
                self.target_y = float(
                    self.position.y
                )

            self.target_z = (
                self.home_z
                - self.flight_altitude
            )

        elif new_state == State.TRACK_CENTER_30S:

            self.track_started = (
                time.monotonic()
            )

            self.last_alignment_seq = -1

        elif new_state == State.RETURN_HOME:

            self.target_x = self.home_x
            self.target_y = self.home_y

            self.target_z = (
                self.home_z
                - self.flight_altitude
            )

        elif new_state == State.PAUSED:

            self.target_x = self.home_x
            self.target_y = self.home_y

            self.target_z = (
                self.home_z
                - self.flight_altitude
            )

        elif new_state == State.ERROR_HOLD:

            if self.position is not None:

                self.target_x = float(
                    self.position.x
                )

                self.target_y = float(
                    self.position.y
                )

                self.target_z = float(
                    self.position.z
                )

    def state_age(
        self,
    ) -> float:

        return (
            time.monotonic()
            - self.state_started
        )

    # =========================================================
    # PX4 publishing
    # =========================================================

    def publish_offboard_mode(
        self,
    ) -> None:

        msg = OffboardControlMode()

        msg.timestamp = self.now_us()

        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False

        self.offboard_pub.publish(msg)

    def publish_position_target(
        self,
    ) -> None:

        msg = TrajectorySetpoint()

        msg.timestamp = self.now_us()

        msg.position = [
            float(self.target_x),
            float(self.target_y),
            float(self.target_z),
        ]

        msg.yaw = float(
            self.target_yaw
        )

        self.trajectory_pub.publish(msg)

    def publish_control_cycle(
        self,
    ) -> None:

        self.publish_offboard_mode()
        self.publish_position_target()

    def send_vehicle_command(
        self,
        command: int,
        param1: float = 0.0,
        param2: float = 0.0,
    ) -> None:

        msg = VehicleCommand()

        msg.timestamp = self.now_us()

        msg.param1 = float(param1)
        msg.param2 = float(param2)
        msg.param3 = 0.0
        msg.param4 = 0.0
        msg.param5 = 0.0
        msg.param6 = 0.0
        msg.param7 = 0.0

        msg.command = int(command)

        msg.target_system = 1
        msg.target_component = 1

        msg.source_system = 1
        msg.source_component = 1

        msg.from_external = True

        self.command_pub.publish(msg)

    def send_forced_disarm_command(
        self,
    ) -> None:
        """Send MAV_CMD_COMPONENT_ARM_DISARM with force magic.

        This helper is only called after the FSM has already emitted LANDED
        and only when allow_force_disarm_after_landed is explicitly enabled.
        """

        msg = VehicleCommand()
        msg.param1 = 0.0
        msg.param2 = 21196.0
        msg.command = (
            VehicleCommand
            .VEHICLE_CMD_COMPONENT_ARM_DISARM
        )
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = int(
            self.get_clock().now().nanoseconds
            / 1000
        )

        self.command_pub.publish(msg)

    def maybe_repeat_command(
        self,
        command: int,
        param1: float = 0.0,
        param2: float = 0.0,
        period: float = 1.0,
    ) -> None:

        now = time.monotonic()

        if (
            now - self.last_command_time
            >= period
        ):

            self.send_vehicle_command(
                command,
                param1,
                param2,
            )

            self.last_command_time = now

    # =========================================================
    # PX4 state helpers
    # =========================================================

    def position_valid(
        self,
    ) -> bool:

        if self.position is None:
            return False

        return (
            bool(
                getattr(
                    self.position,
                    'xy_valid',
                    True,
                )
            )
            and
            bool(
                getattr(
                    self.position,
                    'z_valid',
                    True,
                )
            )
        )

    def is_offboard(
        self,
    ) -> bool:

        if self.vehicle_status is None:
            return False

        expected = getattr(
            VehicleStatus,
            'NAVIGATION_STATE_OFFBOARD',
            None,
        )

        if expected is None:
            return False

        return (
            int(self.vehicle_status.nav_state)
            == int(expected)
        )

    def is_armed(
        self,
    ) -> bool:

        if self.vehicle_status is None:
            return False

        expected = getattr(
            VehicleStatus,
            'ARMING_STATE_ARMED',
            None,
        )

        if expected is None:
            return False

        return (
            int(
                self.vehicle_status.arming_state
            )
            == int(expected)
        )

    def distance_to_target(
        self,
    ) -> float:

        if self.position is None:
            return float('inf')

        dx = (
            float(self.position.x)
            - self.target_x
        )

        dy = (
            float(self.position.y)
            - self.target_y
        )

        dz = (
            float(self.position.z)
            - self.target_z
        )

        return math.sqrt(
            dx * dx
            + dy * dy
            + dz * dz
        )

    def horizontal_distance_to_target(
        self,
    ) -> float:

        if self.position is None:
            return float('inf')

        dx = (
            float(self.position.x)
            - self.target_x
        )

        dy = (
            float(self.position.y)
            - self.target_y
        )

        return math.hypot(
            dx,
            dy,
        )

    # =========================================================
    # Square spiral
    # =========================================================

    def set_spiral_target(
        self,
    ) -> None:

        if (
            self.spiral_index
            >= len(self.spiral_offsets)
        ):
            return

        offset_x, offset_y = (
            self.spiral_offsets[
                self.spiral_index
            ]
        )

        self.target_x = (
            self.home_x
            + offset_x
        )

        self.target_y = (
            self.home_y
            + offset_y
        )

        self.target_z = (
            self.home_z
            - self.flight_altitude
        )

        self.get_logger().info(
            'SPIRAL '
            f'{self.spiral_index + 1}/'
            f'{len(self.spiral_offsets)} '
            f'offset=({offset_x:.2f},'
            f'{offset_y:.2f}) '
            f'target=({self.target_x:.2f},'
            f'{self.target_y:.2f},'
            f'{self.target_z:.2f})'
        )

    # =========================================================
    # Visual servoing
    # =========================================================

    def alignment_error_px(
        self,
        detection: PersonDetection,
    ) -> Tuple[float, float]:

        image_width = max(
            float(detection.image_width),
            1.0,
        )

        image_height = max(
            float(detection.image_height),
            1.0,
        )

        error_x_px = (
            float(detection.center_x)
            - image_width / 2.0
        )

        error_y_px = (
            float(detection.center_y)
            - image_height / 2.0
        )

        return (
            error_x_px,
            error_y_px,
        )

    def detection_centered(
        self,
        detection: PersonDetection,
    ) -> bool:

        (
            error_x_px,
            error_y_px,
        ) = self.alignment_error_px(
            detection
        )

        return (
            abs(error_x_px)
            <= self.alignment_margin
            and
            abs(error_y_px)
            <= self.alignment_margin
        )

    def apply_alignment_correction(
        self,
        detection: PersonDetection,
    ) -> None:
        """
        Latest-bbox persistent XY controller.

        - First valid bbox creates a local XY destination.
        - X and Y image errors are corrected simultaneously.
        - Every newer bbox replaces the previous destination.
        - Empty inference frames DO NOT cancel the destination.
        - No automatic sign inversion is allowed here.
        """

        if self.position is None:
            return

        # One command for each NEW YOLO inference only.
        if (
            self.last_alignment_seq
            == self.detection_seq
        ):
            return

        self.last_alignment_seq = (
            self.detection_seq
        )

        # BBOX_PRIORITY_GATE
        #
        # Better/equal candidate:
        #     replaces steering reference immediately.
        #
        # Weaker candidate:
        #     cannot disturb a recent stronger reference.
        #
        # Once the stronger bbox has aged beyond the
        # priority window, the freshest valid bbox wins.
        # This is necessary because the person is moving.

        now_visual = time.monotonic()

        new_confidence = float(
            detection.confidence
        )

        priority_hold = float(
            self.get_parameter(
                'bbox_priority_hold_sec'
            ).value
        )

        confidence_epsilon = float(
            self.get_parameter(
                'bbox_confidence_epsilon'
            ).value
        )

        active_confidence = getattr(
            self,
            'active_bbox_confidence',
            None,
        )

        active_time = getattr(
            self,
            'active_bbox_monotonic',
            None,
        )

        active_age = float('inf')

        if active_time is not None:
            active_age = max(
                0.0,
                now_visual
                - float(active_time),
            )

        accept_bbox = False
        accept_reason = 'FIRST'

        if active_confidence is None:

            accept_bbox = True

        elif (
            new_confidence
            + confidence_epsilon
            >= float(active_confidence)
        ):

            accept_bbox = True
            accept_reason = 'BETTER_OR_EQUAL'

        elif active_age >= priority_hold:

            accept_bbox = True
            accept_reason = 'CURRENT_AGED'

        if not accept_bbox:

            self.get_logger().info(
                'BBOX_KEEP '
                f'active_conf={float(active_confidence):.3f} '
                f'new_conf={new_confidence:.3f} '
                f'age={active_age:.2f}s '
                f'target=({self.target_x:.2f},'
                f'{self.target_y:.2f})'
            )

            # Do NOT modify target_x / target_y.
            # Vehicle keeps navigating to the current
            # accepted visual target.
            return

        previous_confidence = (
            float(active_confidence)
            if active_confidence is not None
            else -1.0
        )

        self.active_bbox_confidence = (
            new_confidence
        )

        self.active_bbox_monotonic = (
            now_visual
        )

        self.active_bbox_seq = (
            self.detection_seq
        )

        self.get_logger().info(
            'BBOX_ACCEPT '
            f'reason={accept_reason} '
            f'old_conf={previous_confidence:.3f} '
            f'new_conf={new_confidence:.3f} '
            f'seq={self.detection_seq}'
        )


        (
            error_x_px,
            error_y_px,
        ) = self.alignment_error_px(
            detection
        )

        current_x = float(
            self.position.x
        )

        current_y = float(
            self.position.y
        )

        # --------------------------------------------------
        # If BOTH image axes are centered, brake here.
        # Never stop because only one axis is centered.
        # --------------------------------------------------

        if (
            abs(error_x_px)
            <= self.alignment_margin
            and
            abs(error_y_px)
            <= self.alignment_margin
        ):

            self.target_x = current_x
            self.target_y = current_y

            self.get_logger().warning(
                "BBOX_CENTERED "
                f"err_px=("
                f"{error_x_px:.1f},"
                f"{error_y_px:.1f}) "
                f"hold_xy=("
                f"{current_x:.2f},"
                f"{current_y:.2f})"
            )

            return

        # --------------------------------------------------
        # Gain / maximum displacement.
        # --------------------------------------------------

        gain = 1.60

        if self.has_parameter(
            "visual_servo_gain"
        ):
            gain = float(
                self.get_parameter(
                    "visual_servo_gain"
                ).value
            )

        max_update = 3.00

        if self.has_parameter(
            "visual_target_max_update_m"
        ):
            max_update = float(
                self.get_parameter(
                    "visual_target_max_update_m"
                ).value
            )

        # --------------------------------------------------
        # Camera geometry.
        #
        # ROS optical camera:
        #
        # image horizontal X -> vehicle/local Y
        # image vertical   Y -> vehicle/local X
        #
        # Downward camera expected signs:
        #
        # image Y positive (bbox below center)
        #     -> move local X negative
        #
        # image X positive (bbox right of center)
        #     -> move local Y positive
        # --------------------------------------------------

        # Camera-axis signs come from the declared
        # portable parameters. Never auto-flip
        # signs while following a moving target.
        x_sign = float(
            self.x_from_image_y_sign
        )

        y_sign = float(
            self.y_from_image_x_sign
        )

        # --------------------------------------------------
        # Scale pixel displacement with actual altitude.
        # --------------------------------------------------

        altitude = abs(
            self.home_z
            - float(self.position.z)
        )

        altitude = max(
            0.20,
            altitude,
        )

        altitude_ratio = (
            altitude
            / max(
                0.20,
                self.flight_altitude,
            )
        )

        effective_mpp = (
            self.meters_per_pixel
            * altitude_ratio
        )

        # --------------------------------------------------
        # BOTH AXES AT ONCE.
        # --------------------------------------------------

        dx = (
            error_y_px
            * effective_mpp
            * x_sign
            * gain
        )

        dy = (
            error_x_px
            * effective_mpp
            * y_sign
            * gain
        )

        # Do not move an already centered individual axis.
        if (
            abs(error_y_px)
            <= self.alignment_margin
        ):
            dx = 0.0

        if (
            abs(error_x_px)
            <= self.alignment_margin
        ):
            dy = 0.0

        distance = (
            dx * dx
            + dy * dy
        ) ** 0.5

        if (
            distance > max_update
            and
            distance > 1e-6
        ):

            scale = (
                max_update
                / distance
            )

            dx *= scale
            dy *= scale

        # --------------------------------------------------
        # IMPORTANT:
        #
        # Destination is based on CURRENT aircraft position.
        #
        # It remains active indefinitely until another
        # detection replaces it.
        # --------------------------------------------------

        new_target_x = (
            current_x
            + dx
        )

        new_target_y = (
            current_y
            + dy
        )

        self.target_x = new_target_x
        self.target_y = new_target_y

        # Z is controlled exclusively by mission state.
        # Never alter target_z here.

        self.get_logger().warning(
            "BBOX_CHASE "
            f"seq={self.detection_seq} "
            f"conf={float(detection.confidence):.3f} "
            f"err_px=("
            f"{error_x_px:.1f},"
            f"{error_y_px:.1f}) "
            f"sign=("
            f"{x_sign:+.0f},"
            f"{y_sign:+.0f}) "
            f"dxy=("
            f"{dx:.2f},"
            f"{dy:.2f}) "
            f"pos=("
            f"{current_x:.2f},"
            f"{current_y:.2f}) "
            f"target=("
            f"{new_target_x:.2f},"
            f"{new_target_y:.2f})"
        )

    def control_loop(
        self,
    ) -> None:

        try:
            self._control_loop()

        except Exception as exc:

            self.get_logger().error(
                f'Erro na FSM YOLO: {exc!r}'
            )

            self.transition(
                State.ERROR_HOLD,
                'exceção interna',
            )

    def _control_loop(
        self,
    ) -> None:

        # -----------------------------------------------------
        # WAIT_POSITION
        # -----------------------------------------------------

        if self.state == State.WAIT_POSITION:

            if not self.position_valid():
                return

            self.home_x = float(
                self.position.x
            )

            self.home_y = float(
                self.position.y
            )

            self.home_z = float(
                self.position.z
            )

            self.target_x = self.home_x
            self.target_y = self.home_y

            # PX4 LOCAL NED:
            # climbing means decreasing local Z.
            self.target_z = (
                self.home_z
                - self.flight_altitude
            )

            self.target_yaw = 0.0

            self.get_logger().info(
                f'HOME '
                f'x={self.home_x:.2f} '
                f'y={self.home_y:.2f} '
                f'z={self.home_z:.2f} | '
                f'takeoff_z={self.target_z:.2f}'
            )

            self.publish_event(
                'HOME_CAPTURED'
            )

            self.transition(
                State.WARMUP_OFFBOARD
            )

            return

        # All states after WAIT_POSITION maintain an OFFBOARD
        # heartbeat / position target, including PAUSED.
        self.publish_control_cycle()

        # -----------------------------------------------------
        # WARMUP_OFFBOARD
        # -----------------------------------------------------

        if self.state == State.WARMUP_OFFBOARD:

            if self.state_age() >= 2.5:

                self.last_command_time = 0.0

                self.transition(
                    State.ENGAGE_OFFBOARD
                )

            return

        # -----------------------------------------------------
        # ENGAGE_OFFBOARD
        # -----------------------------------------------------

        if self.state == State.ENGAGE_OFFBOARD:

            self.maybe_repeat_command(
                VehicleCommand
                .VEHICLE_CMD_DO_SET_MODE,
                param1=1.0,
                param2=6.0,
            )

            if self.is_offboard():

                self.last_command_time = 0.0

                self.transition(
                    State.ARM
                )

            elif self.state_age() > 12.0:

                self.transition(
                    State.ERROR_HOLD,
                    'OFFBOARD não confirmou',
                )

            return

        # -----------------------------------------------------
        # ARM
        # -----------------------------------------------------

        if self.state == State.ARM:

            self.maybe_repeat_command(
                VehicleCommand
                .VEHICLE_CMD_COMPONENT_ARM_DISARM,
                param1=1.0,
            )

            if self.is_armed():

                self.publish_event(
                    'VEHICLE_ARMED'
                )

                self.transition(
                    State.TAKEOFF
                )

            elif self.state_age() > 12.0:

                self.transition(
                    State.ERROR_HOLD,
                    'ARM não confirmou',
                )

            return

        # -----------------------------------------------------
        # TAKEOFF
        # -----------------------------------------------------

        if self.state == State.TAKEOFF:

            distance = (
                self.distance_to_target()
            )

            if (
                distance
                <= self.takeoff_tolerance
            ):

                self.get_logger().info(
                    'Altitude de busca atingida '
                    f'erro={distance:.2f} m'
                )

                self.publish_event(
                    'TAKEOFF_COMPLETE'
                )

                self.transition(
                    State.SEARCH_SQUARE_SPIRAL
                )

            elif self.state_age() > 120.0:

                self.transition(
                    State.ERROR_HOLD,
                    'timeout de decolagem',
                )

            return

        # -----------------------------------------------------
        # SEARCH SQUARE SPIRAL
        # -----------------------------------------------------

        if (
            self.state
            == State.SEARCH_SQUARE_SPIRAL
        ):

            # Stale detection cannot remain part of a streak.
            if (
                self.latest_detection is None
                or
                (
                    time.monotonic()
                    - self.latest_detection_monotonic
                )
                > self.detection_max_age
            ):
                self.strong_detection_streak = 0

            if self.strong_target_confirmed():

                detection = self.fresh_detection()

                self.publish_event(
                    'PERSON_CONFIRMED'
                )

                self.publish_event(
                    'TARGET_LOCKED'
                )

                if detection is not None:
                    self.get_logger().warning(
                        'Pessoa confirmada: '
                        f'confidence='
                        f'{detection.confidence:.3f} '
                        f'center=('
                        f'{detection.center_x:.1f},'
                        f'{detection.center_y:.1f})'
                    )

                self.transition(
                    State.CENTER_TARGET,
                    'pessoa confirmada com '
                    f'{self.strong_detection_streak} '
                    'frames fortes',
                )

                return

            if (
                self.horizontal_distance_to_target()
                <= self.waypoint_tolerance
            ):

                self.spiral_index += 1

                if (
                    self.spiral_index
                    >= len(
                        self.spiral_offsets
                    )
                ):

                    self.spiral_index = 0

                    self.publish_event(
                        'SEARCH_LOOP_RESTART'
                    )

                    self.get_logger().warning(
                        'Espiral concluída; reiniciando busca.'
                    )

                    self.set_spiral_target()
                    return

                self.set_spiral_target()

            return

        # -----------------------------------------------------
        # CENTER TARGET
        # -----------------------------------------------------

        if self.state == State.CENTER_TARGET:

            detection = (
                self.fresh_detection()
            )

            if detection is None:

                self.aligned_since = None

                # Hold current position while waiting.
                if (
                    self.latest_detection_monotonic
                    > 0.0
                    and
                    (
                        time.monotonic()
                        - self.latest_detection_monotonic
                    )
                    > self.target_loss_timeout
                ):

                    self.get_logger().warning(
                        'Pessoa temporariamente perdida '
                        'durante centralização.'
                    )

                return

            self.apply_alignment_correction(
                detection
            )

            if self.detection_centered(
                detection
            ):

                if self.aligned_since is None:

                    self.aligned_since = (
                        time.monotonic()
                    )

                    self.get_logger().info(
                        'Pessoa entrou na margem '
                        'de centralização.'
                    )

                if (
                    time.monotonic()
                    - self.aligned_since
                    >= self.alignment_hold_sec
                ):

                    if not self.center_event_sent:

                        self.center_event_sent = True

                        self.publish_event(
                            'PERSON_CENTERED'
                        )

                        self.get_logger().warning(
                            'PESSOA CENTRALIZADA '
                            'NA CAMERA.'
                        )

                    else:

                        self.publish_event(
                            'PERSON_RECENTERED'
                        )

                    self.transition(
                        State.TRACK_CENTER_30S,
                        'centralização estabilizada',
                    )

            else:
                self.aligned_since = None

            return

        # -----------------------------------------------------
        # TRACK CENTER FOR 30 SECONDS AT SEARCH ALTITUDE
        # -----------------------------------------------------

        if (
            self.state
            == State.TRACK_CENTER_30S
        ):

            now = time.monotonic()
            dt = max(
                0.0,
                min(
                    0.25,
                    now - self.phase_last_tick,
                ),
            )
            self.phase_last_tick = now

            detection = self.fresh_detection()

            if detection is not None:
                self.apply_alignment_correction(detection)

            # 30 chronological seconds.
            # On a missed inference frame the aircraft
            # continues toward the last accepted visual
            # waypoint.
            self.high_track_accum += dt

            if self.high_track_accum >= self.track_duration:

                self.publish_event('TRACK_HIGH_30S_COMPLETE')

                self.target_z = self.home_z - self.low_altitude
                self.low_track_accum = 0.0
                self.phase_last_tick = time.monotonic()

                self.transition(
                    State.DESCEND_TRACK_1M,
                    '30 s de tracking a 4 m completos; descendo sobre o alvo',
                )

            return

        # -----------------------------------------------------
        # DESCEND TO 1 M WHILE VISUALLY TRACKING
        # -----------------------------------------------------

        if self.state == State.DESCEND_TRACK_1M:

            detection = self.fresh_detection()

            if detection is not None:
                self.apply_alignment_correction(detection)

            self.target_z = self.home_z - self.low_altitude

            if self.position is None:
                return

            altitude_error = abs(
                float(self.position.z) - self.target_z
            )

            if altitude_error <= self.vertical_tolerance:

                self.publish_event('TARGET_LOW_ALTITUDE_REACHED')
                self.low_track_accum = 0.0
                self.phase_last_tick = time.monotonic()

                self.transition(
                    State.TRACK_LOW_30S,
                    '1 m atingido sobre o alvo',
                )

            return

        # -----------------------------------------------------
        # TRACK CENTER FOR ANOTHER 30 SECONDS AT 1 M
        # -----------------------------------------------------

        if self.state == State.TRACK_LOW_30S:

            now = time.monotonic()
            dt = max(
                0.0,
                min(
                    0.25,
                    now - self.phase_last_tick,
                ),
            )
            self.phase_last_tick = now

            detection = self.fresh_detection()

            if detection is not None:
                self.apply_alignment_correction(detection)

            # 30 chronological seconds at 1 m.
            # Missing YOLO frames preserve the last
            # accepted XY target but do not freeze FSM.
            self.low_track_accum += dt

            self.target_z = self.home_z - self.low_altitude

            if self.low_track_accum >= self.low_track_duration:

                self.publish_event('TRACK_LOW_30S_COMPLETE')

                self.target_z = self.home_z - self.flight_altitude

                self.transition(
                    State.ASCEND_TRACK_4M,
                    '30 s de tracking a 1 m completos; subindo ainda sobre o alvo',
                )

            return

        # -----------------------------------------------------
        # ASCEND TO SEARCH ALTITUDE WHILE STILL TRACKING
        # -----------------------------------------------------

        if self.state == State.ASCEND_TRACK_4M:

            detection = self.fresh_detection()

            if detection is not None:
                self.apply_alignment_correction(detection)

            self.target_z = self.home_z - self.flight_altitude

            if self.position is None:
                return

            altitude_error = abs(
                float(self.position.z) - self.target_z
            )

            if altitude_error <= self.vertical_tolerance:

                self.publish_event('ASCEND_TRACK_COMPLETE')

                self.target_x = self.home_x
                self.target_y = self.home_y
                self.target_z = self.home_z - self.flight_altitude

                self.transition(
                    State.RETURN_HOME,
                    'altura segura atingida; retornando ao HOME',
                )

            return

        # -----------------------------------------------------
        # RETURN HOME AT SEARCH ALTITUDE
        # -----------------------------------------------------

        if self.state == State.RETURN_HOME:

            if self.distance_to_target() <= self.return_tolerance:

                self.publish_event('RETURN_HOME_COMPLETE')

                self.target_x = self.home_x
                self.target_y = self.home_y
                self.target_z = self.home_z

                self.transition(
                    State.LAND_HOME,
                    'HOME alcançado; iniciando pouso',
                )

            elif self.state_age() > 90.0:

                self.transition(
                    State.ERROR_HOLD,
                    'timeout de retorno ao home',
                )

            return

        # -----------------------------------------------------
        # LAND AT HOME
        # -----------------------------------------------------

        if self.state == State.LAND_HOME:

            # Use PX4 native landing mode for portability across machines
            # and airframes instead of forcing a ground position setpoint.
            self.maybe_repeat_command(
                VehicleCommand.VEHICLE_CMD_NAV_LAND
            )

            if self.position is None:
                return

            horizontal_error = (
                (
                    (float(self.position.x) - self.home_x) ** 2
                    + (float(self.position.y) - self.home_y) ** 2
                ) ** 0.5
            )

            vertical_error = abs(
                float(self.position.z) - self.home_z
            )

            vertical_speed = abs(
                float(getattr(self.position, 'vz', 0.0))
            )

            if (
                horizontal_error <= self.return_tolerance
                and vertical_error <= self.vertical_tolerance
                and vertical_speed <= 0.40
            ):

                self.publish_event('LANDED')
                self.last_command_time = 0.0

                self.transition(
                    State.DISARM,
                    'pouso confirmado',
                )

            elif self.state_age() > 90.0:

                self.transition(
                    State.ERROR_HOLD,
                    'timeout de pouso',
                )

            return

        # -----------------------------------------------------
        # DISARM
        # -----------------------------------------------------

        if self.state == State.DISARM:

            age = self.state_age()

            allow_force = bool(
                self.get_parameter(
                    'allow_force_disarm_after_landed'
                ).value
            )

            force_after = float(
                self.get_parameter(
                    'force_disarm_after_sec'
                ).value
            )

            disarm_timeout = float(
                self.get_parameter(
                    'disarm_timeout_sec'
                ).value
            )

            # Always try the normal landed disarm first.
            self.maybe_repeat_command(
                VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
                param1=0.0,
            )

            # In the simulation profile only, use MAVLink force-disarm
            # after a grace period. DISARM is reachable only after the
            # LAND_HOME state has already emitted LANDED.
            if (
                allow_force
                and age >= force_after
                and self.is_armed()
            ):

                now = time.monotonic()

                last_force = float(
                    getattr(
                        self,
                        '_last_force_disarm_monotonic',
                        0.0,
                    )
                )

                if (
                    now - last_force
                    >= 1.0
                ):

                    self._last_force_disarm_monotonic = now

                    if not bool(
                        getattr(
                            self,
                            '_force_disarm_announced',
                            False,
                        )
                    ):

                        self._force_disarm_announced = True

                        self.get_logger().warning(
                            'DISARM normal nao confirmou; '
                            'enviando force-disarm '
                            'POS-LANDED (simulacao).'
                        )

                    self.send_forced_disarm_command()

            if not self.is_armed():

                self.publish_event(
                    'VEHICLE_DISARMED'
                )

                self.publish_event(
                    'MISSION_COMPLETE'
                )

                self.transition(
                    State.COMPLETE,
                    'missao concluida',
                )

            elif age > disarm_timeout:

                self.transition(
                    State.ERROR_HOLD,
                    'DISARM nao confirmou',
                )

            return


        if self.state == State.COMPLETE:
            self.target_x = self.home_x
            self.target_y = self.home_y
            self.target_z = self.home_z
            return

        if self.state == State.PAUSED:
            return

        # ERROR HOLD
        # ERROR HOLD
        # -----------------------------------------------------

        if self.state == State.ERROR_HOLD:

            # No automatic landing is commanded here.
            #
            # This is deliberate for the simulation stage.
            # Real-aircraft failsafe policy must be validated
            # separately before hardware flight.
            return


def main(args=None) -> None:

    rclpy.init(args=args)

    node = YoloPersonMission()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:

        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
