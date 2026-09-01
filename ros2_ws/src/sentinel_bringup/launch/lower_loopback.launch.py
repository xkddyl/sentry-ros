from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description() -> LaunchDescription:
    share = Path(get_package_share_directory("sentinel_bringup"))
    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    str(share / "launch" / "sentinel.launch.py")
                ),
                launch_arguments={
                    "mode": "hil",
                    "use_sim_time": "false",
                    "initial_estop": "true",
                    "policy_backend": "mock",
                    "start_nav2": "false",
                    "send_nav2_goal": "false",
                    "start_hardware": "true",
                    "hardware_transport": "udp",
                    "hardware_endpoint": "127.0.0.1:20000",
                    "start_mock_lower_controller": "true",
                    "mock_lower_bind_host": "127.0.0.1",
                    "mock_lower_bind_port": "20000",
                    "start_mock_hardware": "false",
                    "start_mock_battle": "false",
                    "start_mock_nav": "false",
                }.items(),
            )
        ]
    )
