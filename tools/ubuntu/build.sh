#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_root="$(cd -- "${script_dir}/../.." && pwd)"

if [[ ! -r /opt/ros/humble/setup.bash ]]; then
  echo "ROS 2 Humble is not installed or is not readable at /opt/ros/humble/setup.bash." >&2
  echo "Run tools/ubuntu/bootstrap_humble.sh before building this workspace." >&2
  exit 2
fi

source /opt/ros/humble/setup.bash
cd "${workspace_root}/ros2_ws"
rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
colcon build --symlink-install --event-handlers console_direct+

echo "Build complete. Source ros2_ws/install/setup.bash before running."
