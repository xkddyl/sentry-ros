from setuptools import find_packages, setup

package_name = "sentinel_core"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=("test",)),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Sentinel Maintainer",
    maintainer_email="maintainer@example.com",
    description="Sentinel policy, safety and hardware integration nodes.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "battle_observation = sentinel_core.observation_node:main",
            "hardware_bridge = sentinel_core.hardware_bridge:main",
            "mock_battle_state = sentinel_core.mock_battle_state:main",
            "mock_hardware = sentinel_core.mock_hardware:main",
            "mock_lower_controller = sentinel_core.mock_lower_controller:main",
            "mock_nav_controller = sentinel_core.mock_nav_controller:main",
            "mode_manager = sentinel_core.mode_manager:main",
            "policy = sentinel_core.policy_node:main",
            "safety_supervisor = sentinel_core.safety_supervisor:main",
            "tactical_executor = sentinel_core.tactical_executor:main",
            "training_manager = sentinel_core.training_manager:main",
        ]
    },
)
