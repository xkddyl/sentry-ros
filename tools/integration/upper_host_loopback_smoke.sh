#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/sentinel_env.sh"

LOG_DIR="$WORKSPACE_ROOT/logs"
mkdir -p "$LOG_DIR"
LAUNCH_LOG="$LOG_DIR/upper_host_loopback.log"

LAUNCH_PID=""
CONTROL_PID=""
CMD_PID=""
cleanup() {
  [[ -z "$CONTROL_PID" ]] || kill "$CONTROL_PID" 2>/dev/null || true
  [[ -z "$CMD_PID" ]] || kill "$CMD_PID" 2>/dev/null || true
  [[ -z "$LAUNCH_PID" ]] || kill "$LAUNCH_PID" 2>/dev/null || true
  [[ -z "$CONTROL_PID" ]] || wait "$CONTROL_PID" 2>/dev/null || true
  [[ -z "$CMD_PID" ]] || wait "$CMD_PID" 2>/dev/null || true
  [[ -z "$LAUNCH_PID" ]] || wait "$LAUNCH_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

fail() {
  echo "RESULT: FAIL"
  echo "ROOT_CAUSE=$1"
  echo "LOG=$LAUNCH_LOG"
  exit 1
}

[[ "$ROS_DISTRO" == "jazzy" ]] || fail "ROS_DISTRO is not jazzy"
command -v ros2 >/dev/null || fail "ros2 CLI not found"
[[ -r "$SENTINEL_ROS2_WS/install/setup.bash" ]] || fail "ROS workspace is not built"

ros2 launch sentinel_bringup lower_loopback.launch.py >"$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

wait_for_topic() {
  local topic="$1" deadline=$((SECONDS + 30))
  while (( SECONDS < deadline )); do
    kill -0 "$LAUNCH_PID" 2>/dev/null || fail "loopback launch exited early"
    if ros2 topic list 2>/dev/null | grep -qx "$topic"; then
      return 0
    fi
    sleep 0.5
  done
  fail "timeout waiting for $topic"
}

wait_for_topic /sentry/hardware_state
wait_for_topic /sentry/hardware_diagnostics
wait_for_topic /sentry/chassis_control_safe

# The mock lower controller is allowed to answer while e-stop is active. That
# proves transport health without enabling motion.
deadline=$((SECONDS + 15))
while (( SECONDS < deadline )); do
  if timeout 3 ros2 topic echo /sentry/hardware_state --once 2>/dev/null \
      | grep -q "online: true"; then
    break
  fi
  sleep 0.5
done
(( SECONDS < deadline )) || fail "mock lower never became online"

# Explicitly release only the software e-stop in this all-UDP mock launch.
ros2 topic pub --once /sentry/estop std_msgs/msg/Bool '{data: false}' >/dev/null
sleep 0.5

control_msg='{mode: 1, frame: 0, spin_wz_rad_s: 0.0, follow_yaw_offset_rad: 0.0, yaw_big_target_rad: 0.0, yaw_small_target_rad: 0.0, pitch_target_rad: 0.0, enable: true}'
cmd_msg='{linear: {x: 0.10, y: 0.04, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.10}}'

set +e
timeout 3 ros2 topic pub -r 20 /sentry/chassis_control \
  sentinel_interfaces/msg/ChassisControl "$control_msg" >/dev/null 2>&1 &
CONTROL_PID=$!
timeout 3 ros2 topic pub -r 20 /cmd_vel geometry_msgs/msg/Twist \
  "$cmd_msg" >/dev/null 2>&1 &
CMD_PID=$!
set -e

sleep 1
SAFE_CONTROL="$(timeout 5 ros2 topic echo /sentry/chassis_control_safe --once)" 
echo "$SAFE_CONTROL" | grep -q "mode: 1" || fail "DIRECT mode did not reach safe bus"
echo "$SAFE_CONTROL" | grep -q "enable: true" || fail "safe chassis control was not enabled"

DIAG="$(timeout 5 ros2 topic echo /sentry/hardware_diagnostics --once)"
echo "$DIAG" | grep -q "transport_state: 2" || fail "transport is not CONNECTED"
echo "$DIAG" | grep -q "telemetry_fresh: true" || fail "telemetry is not fresh"

echo "[OK] safe mode and UDP telemetry are live"

wait "$CONTROL_PID" 2>/dev/null || true
CONTROL_PID=""
wait "$CMD_PID" 2>/dev/null || true
CMD_PID=""
sleep 1

STALE_CONTROL="$(timeout 5 ros2 topic echo /sentry/chassis_control_safe --once)"
echo "$STALE_CONTROL" | grep -q "mode: 0" || fail "stale chassis control did not fall back to STOP"

echo "RESULT: PASS"
echo "[OK] Mock Lower binary loopback"
echo "[OK] chassis_control raw -> safety -> safe"
echo "[OK] telemetry -> hardware_state/diagnostics"
echo "[OK] stale explicit chassis control -> STOP"
