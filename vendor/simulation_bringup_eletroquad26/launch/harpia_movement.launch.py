from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch.launch_description_sources import PythonLaunchDescriptionSource
import os

def generate_launch_description():

    ld = LaunchDescription()

    # --- PX4 COMMANDER ---

    px4_commander_dir = get_package_share_directory('px4_commander')

    px4_commander_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(px4_commander_dir, 'launch', 'px4_commander.launch.py')
        )
    )

    # --- MOVEMENT CONTROLLER ---

    movement_controller_dir = get_package_share_directory('movement_controller')

    movement_controller_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(movement_controller_dir, 'launch', 'movement_controller.launch.py')
        )
    )

    ld.add_action(px4_commander_launch)
    ld.add_action(movement_controller_launch)

    return ld