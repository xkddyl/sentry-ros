#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$script_dir/sentinel_env.sh"

dependency_error=0
if [[ ! -r /opt/ros/humble/setup.bash ]]; then
    echo "ERROR: ROS2 Humble setup is missing: /opt/ros/humble/setup.bash" >&2
    dependency_error=1
fi
if ! command -v colcon >/dev/null 2>&1; then
    echo "ERROR: colcon is not available in PATH" >&2
    dependency_error=1
fi
if [[ ! -d "$SENTINEL_ROS2_WS/src" ]]; then
    echo "ERROR: ROS2 workspace is invalid: $SENTINEL_ROS2_WS" >&2
    dependency_error=1
fi

if (( dependency_error )); then
    echo "Run dependency/bootstrap step first" >&2
    exit 2
fi

cd "$SENTINEL_ROS2_WS"
colcon build --symlink-install
