#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    """ This function starts the system in a custom configuration """

    # Generate the object that must be returned by this function
    ld = LaunchDescription()


    ##################################################
    #  Initalize simulation      
    ##################################################

    ################ SITL + GZ + MICRO-XRCE + QGC + ROS_GZ_BRIDGE ################
    processes_path = os.path.join(
        get_package_share_directory('simulation_bringup'),
        'config',
        'simulation',
        'run_eletroquad26_m2.sh'
    )

    simulation_processes = ExecuteProcess(cmd=['bash', processes_path], output='screen')


    ##################################################
    #  Add the action to LaunchDescription object 
    ##################################################

    ld.add_action(simulation_processes)

    return ld