#!/usr/bin/env python3
"""Reliable OpenCV viewer for /yolo/image_annotated.

This viewer deliberately does not use `ros2 topic echo` as a readiness gate.
It subscribes with sensor-data/best-effort QoS and waits for the first frame
inside the GUI process.
"""

from __future__ import annotations

import argparse
import time

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Image


class AnnotatedCameraViewer(Node):
    def __init__(self, topic: str, window: str, width: int) -> None:
        super().__init__("harpia_yolo_annotated_viewer")

        self.topic = topic
        self.window = window
        self.width = max(320, int(width))
        self.bridge = CvBridge()
        self.first_frame = True
        self.last_frame_monotonic = 0.0
        self.frames = 0

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.create_subscription(
            Image,
            self.topic,
            self._on_image,
            qos,
        )

        cv2.namedWindow(
            self.window,
            cv2.WINDOW_NORMAL,
        )

        self.get_logger().info(
            f"waiting for annotated frames on {self.topic}"
        )

    def _on_image(self, msg: Image) -> None:
        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8",
        )

        height, width = frame.shape[:2]

        if width > 0 and width != self.width:
            scale = self.width / float(width)
            frame = cv2.resize(
                frame,
                (
                    self.width,
                    max(1, int(height * scale)),
                ),
                interpolation=cv2.INTER_LINEAR,
            )

        self.frames += 1
        self.last_frame_monotonic = time.monotonic()

        if self.first_frame:
            self.first_frame = False
            self.get_logger().info(
                f"first annotated frame received: "
                f"{msg.width}x{msg.height}"
            )

        cv2.imshow(
            self.window,
            frame,
        )

        key = cv2.waitKey(1) & 0xFF

        if key in (27, ord("q")):
            rclpy.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--topic",
        default="/yolo/image_annotated",
    )
    parser.add_argument(
        "--window",
        default="HARPia YOLO - Camera do drone",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=960,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    rclpy.init()

    node = AnnotatedCameraViewer(
        topic=args.topic,
        window=args.window,
        width=args.width,
    )

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()

        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
