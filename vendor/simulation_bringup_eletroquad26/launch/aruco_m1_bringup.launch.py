from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


WORLD = "/root/PX4-Autopilot/Tools/simulation/gz/worlds/eletroquad26_m1.sdf"

GZ_RESOURCES = (
    "/root/PX4-Autopilot/Tools/simulation/gz/models:"
    "/root/PX4-Autopilot/Tools/simulation/gz/worlds:"
    "/opt/ros/humble/share/as2_gazebo_assets/worlds:"
    "/opt/ros/humble/share/as2_gazebo_assets/models"
)


def generate_launch_description():

    gui = LaunchConfiguration("gui")

    return LaunchDescription([

        DeclareLaunchArgument(
            "gui",
            default_value="true",
            description="Abrir interface gráfica do Gazebo"
        ),

        # ---------------------------------------------------------
        # Ambiente Gazebo Garden
        # ---------------------------------------------------------
        SetEnvironmentVariable("GZ_VERSION", "garden"),
        SetEnvironmentVariable("GZ_IP", "127.0.0.1"),
        SetEnvironmentVariable("IGN_IP", "127.0.0.1"),
        SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", GZ_RESOURCES),

        # ---------------------------------------------------------
        # Gazebo Server
        # ---------------------------------------------------------
        ExecuteProcess(
            cmd=[
                "gz", "sim",
                "-r",
                "-s",
                WORLD,
            ],
            output="screen",
        ),

        # ---------------------------------------------------------
        # Gazebo GUI
        # ---------------------------------------------------------
        TimerAction(
            period=2.0,
            actions=[
                ExecuteProcess(
                    cmd=[
                        "gz", "sim",
                        "-g",
                    ],
                    output="screen",
                    condition=IfCondition(gui),
                )
            ],
        ),

        # ---------------------------------------------------------
        # MicroXRCEAgent
        # ---------------------------------------------------------
        TimerAction(
            period=2.0,
            actions=[
                ExecuteProcess(
                    cmd=[
                        "MicroXRCEAgent",
                        "udp4",
                        "-p",
                        "8888",
                    ],
                    output="screen",
                )
            ],
        ),

        # ---------------------------------------------------------
        # PX4 SITL + harpia
        # ---------------------------------------------------------
        TimerAction(
            period=4.0,
            actions=[
                ExecuteProcess(
                    cmd=[
                        "bash",
                        "-lc",
                        """
                        cd /root/PX4-Autopilot

                        export GZ_VERSION=garden
                        export GZ_IP=127.0.0.1
                        export IGN_IP=127.0.0.1

                        unset GZ_PARTITION
                        unset IGN_PARTITION

                        export GZ_SIM_RESOURCE_PATH="/root/PX4-Autopilot/Tools/simulation/gz/models:/root/PX4-Autopilot/Tools/simulation/gz/worlds:/opt/ros/humble/share/as2_gazebo_assets/worlds:/opt/ros/humble/share/as2_gazebo_assets/models"

                        export PX4_GZ_STANDALONE=1
                        export PX4_GZ_WORLD=eletroquad26_m1
                        export HEADLESS=1

                        make px4_sitl gz_harpia
                        """
                    ],
                    output="screen",
                )
            ],
        ),

        # ---------------------------------------------------------
        # Clock Gazebo -> ROS
        # Usa o ros_gz Garden do overlay
        # ---------------------------------------------------------
        TimerAction(
            period=6.0,
            actions=[
                Node(
                    package="ros_gz_bridge",
                    executable="parameter_bridge",
                    name="clock_bridge_garden",
                    arguments=[
                        "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"
                    ],
                    output="screen",
                )
            ],
        ),

        # ---------------------------------------------------------
        # Câmera Gazebo -> ROS
        # ---------------------------------------------------------
        TimerAction(
            period=6.0,
            actions=[
                Node(
                    package="ros_gz_image",
                    executable="image_bridge",
                    name="camera_bridge_garden",
                    arguments=[
                        "/color_cam_downward",
                    ],
                    remappings=[
                        (
                            "/color_cam_downward",
                            "/camera/image_raw",
                        ),
                    ],
                    output="screen",
                )
            ],
        ),

        # ---------------------------------------------------------
        # Detector ArUco
        # ---------------------------------------------------------
        TimerAction(
            period=8.0,
            actions=[
                Node(
                    package="aruco_det",
                    executable="detector_node",
                    name="aruco_detector_node",
                    remappings=[
                        (
                            "/image_raw",
                            "/camera/image_raw",
                        ),
                    ],
                    output="screen",
                )
            ],
        ),

        # ---------------------------------------------------------
        # Aligner
        # ---------------------------------------------------------
        TimerAction(
            period=9.0,
            actions=[
                Node(
                    package="aligner",
                    executable="aligner_node",
                    output="screen",
                )
            ],
        ),
    ])
