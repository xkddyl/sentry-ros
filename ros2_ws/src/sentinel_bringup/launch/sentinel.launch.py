from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _node(executable: str, *, condition=None, parameters=None) -> Node:
    return Node(
        package="sentinel_core",
        executable=executable,
        namespace=LaunchConfiguration("namespace"),
        output="screen",
        condition=condition,
        remappings=[
            ("tf", "/tf"),
            ("tf_static", "/tf_static"),
        ],
        parameters=parameters or [{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )


def generate_launch_description() -> LaunchDescription:
    description_share = Path(get_package_share_directory("sentinel_description"))
    navigation_share = Path(get_package_share_directory("sentinel_navigation"))
    mode = LaunchConfiguration("mode")
    use_sim_time = LaunchConfiguration("use_sim_time")

    description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(description_share / "launch" / "description.launch.py")
        ),
        launch_arguments={
            "namespace": LaunchConfiguration("namespace"),
            "use_sim_time": use_sim_time,
        }.items(),
    )
    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(navigation_share / "launch" / "navigation.launch.py")
        ),
        condition=IfCondition(LaunchConfiguration("start_nav2")),
        launch_arguments={
            "namespace": LaunchConfiguration("namespace"),
            "use_sim_time": use_sim_time,
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("namespace", default_value="sentry"),
            DeclareLaunchArgument("mode", default_value="sim"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("initial_estop", default_value="true"),
            DeclareLaunchArgument("policy_backend", default_value="mock"),
            DeclareLaunchArgument("policy_dir", default_value=""),
            DeclareLaunchArgument("rmuc_rl_path", default_value=""),
            DeclareLaunchArgument("policy_device", default_value="cpu"),
            DeclareLaunchArgument("camp", default_value="红"),
            DeclareLaunchArgument("start_nav2", default_value="false"),
            DeclareLaunchArgument("send_nav2_goal", default_value="false"),
            DeclareLaunchArgument("start_hardware", default_value="false"),
            DeclareLaunchArgument("hardware_transport", default_value="serial"),
            DeclareLaunchArgument("hardware_endpoint", default_value="/dev/ttyACM0"),
            DeclareLaunchArgument("hardware_baudrate", default_value="921600"),
            DeclareLaunchArgument("start_mock_hardware", default_value="false"),
            DeclareLaunchArgument("start_mock_lower_controller", default_value="false"),
            DeclareLaunchArgument("mock_lower_bind_host", default_value="127.0.0.1"),
            DeclareLaunchArgument("mock_lower_bind_port", default_value="20000"),
            DeclareLaunchArgument("start_mock_battle", default_value="false"),
            DeclareLaunchArgument("start_mock_nav", default_value="false"),
            description,
            _node(
                "mode_manager",
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "initial_mode": mode,
                        "initial_estop": LaunchConfiguration("initial_estop"),
                    }
                ],
            ),
            _node(
                "safety_supervisor",
                parameters=[{"use_sim_time": use_sim_time, "initial_mode": mode}],
            ),
            _node("battle_observation"),
            _node(
                "policy",
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "backend": LaunchConfiguration("policy_backend"),
                        "policy_dir": LaunchConfiguration("policy_dir"),
                        "rmuc_rl_path": LaunchConfiguration("rmuc_rl_path"),
                        "device": LaunchConfiguration("policy_device"),
                        "camp": LaunchConfiguration("camp"),
                    }
                ],
            ),
            _node(
                "tactical_executor",
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "send_nav2_goal": LaunchConfiguration("send_nav2_goal"),
                    }
                ],
            ),
            _node(
                "hardware_bridge",
                condition=IfCondition(LaunchConfiguration("start_hardware")),
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "transport": LaunchConfiguration("hardware_transport"),
                        "endpoint": LaunchConfiguration("hardware_endpoint"),
                        "baudrate": LaunchConfiguration("hardware_baudrate"),
                    }
                ],
            ),
            _node(
                "mock_lower_controller",
                condition=IfCondition(LaunchConfiguration("start_mock_lower_controller")),
                parameters=[
                    {
                        "use_sim_time": False,
                        "bind_host": LaunchConfiguration("mock_lower_bind_host"),
                        "bind_port": LaunchConfiguration("mock_lower_bind_port"),
                    }
                ],
            ),
            _node(
                "mock_hardware",
                condition=IfCondition(LaunchConfiguration("start_mock_hardware")),
            ),
            _node(
                "mock_battle_state",
                condition=IfCondition(LaunchConfiguration("start_mock_battle")),
            ),
            _node(
                "mock_nav_controller",
                condition=IfCondition(LaunchConfiguration("start_mock_nav")),
            ),
            navigation,
        ]
    )
