from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, List, Tuple

import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from ultralytics import YOLO

from yolo_person_interfaces.msg import PersonDetection, PersonDetectionArray


class YoloPersonDetector(Node):
    """Portable YOLO person detector.

    The node depends only on a ROS 2 image topic. It intentionally has no
    Gazebo or PX4 dependency, so the same package can be reused on simulation,
    rosbag playback, a USB/CSI camera bridge, or an onboard computer.

    Two thresholds should be kept conceptually separate:
      * confidence_threshold: low candidate threshold used by YOLO.
      * mission lock/tracking thresholds: applied by the consumer.

    Keeping the detector threshold lower improves recall and lets the mission
    use hysteresis (for example: detect at 0.05, lock at 0.10, track at 0.05).
    """

    def __init__(self) -> None:
        super().__init__("yolo_person_detector")

        self.declare_parameter("model_path", "yolo11n.pt")
        self.declare_parameter("input_topic", "/camera/image_raw")
        self.declare_parameter("annotated_topic", "/yolo/image_annotated")
        self.declare_parameter("detection_topic", "/yolo/person_detection")
        self.declare_parameter("detections_topic", "/yolo/person_detections")
        self.declare_parameter("detected_topic", "/yolo/person_detected")
        self.declare_parameter("confidence_threshold", 0.05)
        self.declare_parameter("imgsz", 512)
        self.declare_parameter("iou_threshold", 0.45)
        self.declare_parameter("max_det", 10)
        self.declare_parameter("device", "cpu")
        self.declare_parameter("class_name", "person")
        self.declare_parameter("publish_annotated", True)
        self.declare_parameter("log_every_n_frames", 30)

        self.model_path = str(self.get_parameter("model_path").value)
        self.input_topic = str(self.get_parameter("input_topic").value)
        self.annotated_topic = str(self.get_parameter("annotated_topic").value)
        self.detection_topic = str(self.get_parameter("detection_topic").value)
        self.detections_topic = str(self.get_parameter("detections_topic").value)
        self.detected_topic = str(self.get_parameter("detected_topic").value)
        self.confidence_threshold = float(
            self.get_parameter("confidence_threshold").value
        )
        self.imgsz = int(self.get_parameter("imgsz").value)
        self.iou_threshold = float(self.get_parameter("iou_threshold").value)
        self.max_det = int(self.get_parameter("max_det").value)
        self.device = str(self.get_parameter("device").value)
        self.class_name = str(self.get_parameter("class_name").value).strip()
        self.publish_annotated = bool(
            self.get_parameter("publish_annotated").value
        )
        self.log_every_n_frames = max(
            1, int(self.get_parameter("log_every_n_frames").value)
        )

        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be in [0, 1]")
        if self.imgsz < 32:
            raise ValueError("imgsz must be >= 32")
        if not 0.0 <= self.iou_threshold <= 1.0:
            raise ValueError("iou_threshold must be in [0, 1]")

        model_ref = self.model_path
        if (
            "/" in model_ref
            and not Path(model_ref).expanduser().exists()
        ):
            raise FileNotFoundError(
                f"YOLO model not found: {Path(model_ref).expanduser()}"
            )

        self.bridge = CvBridge()
        self.model = YOLO(model_ref)
        self.person_class_id = self._resolve_class_id(
            self.model.names, self.class_name
        )

        self.annotated_pub = self.create_publisher(
            Image, self.annotated_topic, 1
        )
        self.detection_pub = self.create_publisher(
            PersonDetection, self.detection_topic, 10
        )
        self.detections_pub = self.create_publisher(
            PersonDetectionArray, self.detections_topic, 10
        )
        self.detected_pub = self.create_publisher(
            Bool, self.detected_topic, 10
        )

        self.image_sub = self.create_subscription(
            Image,
            self.input_topic,
            self._image_callback,
            qos_profile_sensor_data,
        )

        self.frames = 0
        self.frames_with_person = 0
        self.inference_ms_sum = 0.0

        self.get_logger().info(
            "YOLO person detector ready | "
            f"model={self.model_path} | input={self.input_topic} | "
            f"candidate_conf={self.confidence_threshold:.3f} | "
            f"imgsz={self.imgsz} | iou={self.iou_threshold:.2f} | "
            f"device={self.device} | class_id={self.person_class_id}"
        )

    @staticmethod
    def _resolve_class_id(names: object, class_name: str) -> int:
        target = class_name.casefold()

        if isinstance(names, dict):
            items: Iterable[Tuple[int, str]] = (
                (int(key), str(value)) for key, value in names.items()
            )
        elif isinstance(names, (list, tuple)):
            items = ((idx, str(value)) for idx, value in enumerate(names))
        else:
            raise TypeError(f"unsupported YOLO names type: {type(names)!r}")

        for class_id, name in items:
            if name.casefold() == target:
                return class_id

        raise RuntimeError(
            f"class {class_name!r} not present in model.names={names!r}"
        )

    @staticmethod
    def _detection_from_box(
        header,
        box,
        image_width: int,
        image_height: int,
        class_name: str,
    ) -> PersonDetection:
        x1, y1, x2, y2 = [
            float(value) for value in box.xyxy[0].detach().cpu().tolist()
        ]
        confidence = float(box.conf[0].detach().cpu().item())

        msg = PersonDetection()
        msg.header = header
        msg.class_name = class_name
        msg.confidence = confidence
        msg.x1 = x1
        msg.y1 = y1
        msg.x2 = x2
        msg.y2 = y2
        msg.center_x = (x1 + x2) / 2.0
        msg.center_y = (y1 + y2) / 2.0
        msg.image_width = int(image_width)
        msg.image_height = int(image_height)
        return msg

    def _image_callback(self, image_msg: Image) -> None:
        started = time.perf_counter()

        try:
            frame = self.bridge.imgmsg_to_cv2(
                image_msg, desired_encoding="bgr8"
            )

            results = self.model.predict(
                source=frame,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                imgsz=self.imgsz,
                device=self.device,
                classes=[self.person_class_id],
                max_det=self.max_det,
                verbose=False,
            )

            result = results[0]
            image_height, image_width = frame.shape[:2]

            detections: List[PersonDetection] = []
            for box in result.boxes:
                detections.append(
                    self._detection_from_box(
                        image_msg.header,
                        box,
                        image_width,
                        image_height,
                        self.class_name,
                    )
                )

            detections.sort(
                key=lambda detection: float(detection.confidence),
                reverse=True,
            )

            array_msg = PersonDetectionArray()
            array_msg.header = image_msg.header
            array_msg.detections = detections
            self.detections_pub.publish(array_msg)

            detected_msg = Bool()
            detected_msg.data = bool(detections)
            self.detected_pub.publish(detected_msg)

            if detections:
                self.frames_with_person += 1
                self.detection_pub.publish(detections[0])

            if self.publish_annotated:
                annotated = result.plot()
                annotated_msg = self.bridge.cv2_to_imgmsg(
                    annotated, encoding="bgr8"
                )
                annotated_msg.header = image_msg.header
                self.annotated_pub.publish(annotated_msg)

            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self.frames += 1
            self.inference_ms_sum += elapsed_ms

            if self.frames % self.log_every_n_frames == 0:
                mean_ms = self.inference_ms_sum / self.frames
                best = (
                    f"{detections[0].confidence:.3f}"
                    if detections
                    else "-"
                )
                self.get_logger().info(
                    f"frames={self.frames} | "
                    f"person_frames={self.frames_with_person} | "
                    f"persons_now={len(detections)} | best_conf={best} | "
                    f"callback={elapsed_ms:.1f} ms | mean={mean_ms:.1f} ms"
                )

        except Exception as exc:
            self.get_logger().error(
                f"YOLO image callback failed: {exc!r}"
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = YoloPersonDetector()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
