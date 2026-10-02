#!/usr/bin/env bash

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_root="$(cd -- "${script_dir}/../.." && pwd)"

if [[ ! -r /opt/ros/humble/setup.bash ]]; then
  echo "ROS 2 Humble is not installed. Run tools/ubuntu/bootstrap_humble.sh." >&2
  return 2
fi
if [[ ! -r "${workspace_root}/ros2_ws/install/setup.bash" ]]; then
  echo "Workspace is not built. Run tools/ubuntu/build.sh." >&2
  return 3
fi

set -a
source "${workspace_root}/config/network.env"
set +a
source /opt/ros/humble/setup.bash
source "${workspace_root}/ros2_ws/install/setup.bash"
export SENTINEL_WORKSPACE="${workspace_root}"
export FASTRTPS_DEFAULT_PROFILES_FILE="${workspace_root}/config/fastdds.xml"
