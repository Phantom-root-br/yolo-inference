from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = LaunchConfiguration("config")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config",
                default_value="",
                description="Optional ROS 2 YAML parameter file.",
            ),
            Node(
                package="yolo_person_detector",
                executable="person_detector",
                name="yolo_person_detector",
                output="screen",
                parameters=[config],
            ),
        ]
    )
