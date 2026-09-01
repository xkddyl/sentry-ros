from __future__ import annotations

import math
import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Int8, UInt8

from sentinel_interfaces.msg import ChassisControl, HardwareState, SystemStatus


class SafetySupervisor(Node):
    def __init__(self) -> None:
        super().__init__("safety_supervisor")
        self.declare_parameter("initial_mode", "sim")
        self.declare_parameter("publish_rate_hz", 100.0)
        self.declare_parameter("command_timeout_s", 0.50)
        self.declare_parameter("control_timeout_s", 0.50)
        self.declare_parameter("policy_timeout_s", 1.50)
        self.declare_parameter("hardware_timeout_s", 0.25)
        self.declare_parameter("max_linear_speed", 0.20)
        self.declare_parameter("max_linear_x", 0.20)
        self.declare_parameter("max_linear_y", 0.20)
        self.declare_parameter("max_angular_speed", 0.60)
        self.declare_parameter("max_linear_accel", 3.0)
        self.declare_parameter("heat_safety_margin", 10.0)

        mode_name = str(self.get_parameter("initial_mode").value).lower()
        self._mode = {"sim": 0, "hil": 1, "real": 2}.get(mode_name, 0)
        self._estop = True
        self._nav = Twist()
        self._teleop = Twist()
        self._control = self._default_control()
        self._control_seen = False
        self._last_nav = 0.0
        self._last_teleop = 0.0
        self._last_control = 0.0
        self._last_weapons_request = 0.0
        self._last_target_request = 0.0
        self._last_hardware = 0.0
        self._hardware = HardwareState()
        self._hardware.ammo_remaining = -1.0
        self._weapons_requested = False
        self._target_requested = -1
        self._last_output = Twist()
        self._last_tick = time.monotonic()

        # Absolute names are deliberate. Raw inputs are global/canonical;
        # safe outputs have exactly one owner: this node.
        self.create_subscription(Twist, "/cmd_vel", self._on_nav, 20)
        self.create_subscription(Twist, "/cmd_vel_teleop", self._on_teleop, 20)
        self.create_subscription(
            ChassisControl,
            "/sentry/chassis_control",
            self._on_control,
            20,
        )
        self.create_subscription(
            Bool, "/sentry/weapons_free_request", self._on_weapons, 10
        )
        self.create_subscription(Int8, "/sentry/target_request", self._on_target, 10)
        self.create_subscription(HardwareState, "/sentry/hardware_state", self._on_hw, 10)
        self.create_subscription(UInt8, "/sentry/system_mode", self._on_mode, 10)
        self.create_subscription(Bool, "/sentry/estop", self._on_estop, 10)

        self._cmd_pub = self.create_publisher(Twist, "/sentry/cmd_vel_safe", 20)
        self._control_pub = self.create_publisher(
            ChassisControl, "/sentry/chassis_control_safe", 20
        )
        self._weapons_pub = self.create_publisher(Bool, "/sentry/weapons_free_safe", 10)
        self._target_pub = self.create_publisher(Int8, "/sentry/target_safe", 10)
        self._status_pub = self.create_publisher(SystemStatus, "/sentry/system_status", 10)
        rate = max(float(self.get_parameter("publish_rate_hz").value), 1.0)
        self.create_timer(1.0 / rate, self._tick)

    @staticmethod
    def _default_control() -> ChassisControl:
        control = ChassisControl()
        control.mode = ChassisControl.MODE_DIRECT
        control.frame = ChassisControl.FRAME_BODY
        control.spin_wz_rad_s = 0.0
        control.follow_yaw_offset_rad = 0.0
        control.yaw_big_target_rad = 0.0
        control.yaw_small_target_rad = 0.0
        control.pitch_target_rad = 0.0
        control.enable = True
        return control

    @staticmethod
    def _stop_control() -> ChassisControl:
        control = ChassisControl()
        control.mode = ChassisControl.MODE_STOP
        control.frame = ChassisControl.FRAME_BODY
        control.enable = False
        return control

    @staticmethod
    def _copy_control(source: ChassisControl) -> ChassisControl:
        output = ChassisControl()
        output.mode = int(source.mode)
        output.frame = int(source.frame)
        output.spin_wz_rad_s = float(source.spin_wz_rad_s)
        output.follow_yaw_offset_rad = float(source.follow_yaw_offset_rad)
        output.yaw_big_target_rad = float(source.yaw_big_target_rad)
        output.yaw_small_target_rad = float(source.yaw_small_target_rad)
        output.pitch_target_rad = float(source.pitch_target_rad)
        output.enable = bool(source.enable)
        return output

    def _on_nav(self, message: Twist) -> None:
        if not self._finite_planar_twist(message):
            self.get_logger().error("rejecting non-finite /cmd_vel")
            return
        self._nav = message
        self._last_nav = time.monotonic()

    def _on_teleop(self, message: Twist) -> None:
        if not self._finite_planar_twist(message):
            self.get_logger().error("rejecting non-finite teleop command")
            return
        self._teleop = message
        self._last_teleop = time.monotonic()

    def _on_control(self, message: ChassisControl) -> None:
        values = (
            message.spin_wz_rad_s,
            message.follow_yaw_offset_rad,
            message.yaw_big_target_rad,
            message.yaw_small_target_rad,
            message.pitch_target_rad,
        )
        if not all(math.isfinite(float(value)) for value in values):
            self.get_logger().error("rejecting non-finite chassis control")
            return
        if int(message.mode) not in (
            ChassisControl.MODE_STOP,
            ChassisControl.MODE_DIRECT,
            ChassisControl.MODE_FOLLOW,
            ChassisControl.MODE_SPIN,
        ):
            self.get_logger().warning("rejecting unknown chassis mode")
            return
        if int(message.frame) not in (
            ChassisControl.FRAME_BODY,
            ChassisControl.FRAME_GIMBAL,
            ChassisControl.FRAME_WORLD,
        ):
            self.get_logger().warning("rejecting unknown command frame")
            return
        self._control = self._copy_control(message)
        self._control_seen = True
        self._last_control = time.monotonic()

    def _on_weapons(self, message: Bool) -> None:
        self._weapons_requested = bool(message.data)
        self._last_weapons_request = time.monotonic()

    def _on_target(self, message: Int8) -> None:
        requested = int(message.data)
        if requested < -1 or requested > 5:
            self.get_logger().warning("rejecting target slot outside [-1, 5]")
            requested = -1
        self._target_requested = requested
        self._last_target_request = time.monotonic()

    def _on_hw(self, message: HardwareState) -> None:
        self._hardware = message
        self._last_hardware = time.monotonic()

    def _on_mode(self, message: UInt8) -> None:
        mode = int(message.data)
        if mode in (SystemStatus.MODE_SIM, SystemStatus.MODE_HIL, SystemStatus.MODE_REAL):
            self._mode = mode
        else:
            self.get_logger().warning("rejecting unknown system mode")

    def _on_estop(self, message: Bool) -> None:
        self._estop = bool(message.data)

    @staticmethod
    def _finite_planar_twist(message: Twist) -> bool:
        return all(
            math.isfinite(float(value))
            for value in (
                message.linear.x,
                message.linear.y,
                message.linear.z,
                message.angular.x,
                message.angular.y,
                message.angular.z,
            )
        )

    @staticmethod
    def _copy_twist(source: Twist) -> Twist:
        output = Twist()
        output.linear.x = float(source.linear.x)
        output.linear.y = float(source.linear.y)
        output.linear.z = float(source.linear.z)
        output.angular.x = float(source.angular.x)
        output.angular.y = float(source.angular.y)
        output.angular.z = float(source.angular.z)
        return output

    def _limit(self, desired: Twist, dt: float) -> Twist:
        output = self._copy_twist(desired)
        output.linear.z = 0.0
        output.angular.x = 0.0
        output.angular.y = 0.0
        max_x = max(float(self.get_parameter("max_linear_x").value), 0.0)
        max_y = max(float(self.get_parameter("max_linear_y").value), 0.0)
        output.linear.x = min(max(output.linear.x, -max_x), max_x)
        output.linear.y = min(max(output.linear.y, -max_y), max_y)
        max_linear = max(float(self.get_parameter("max_linear_speed").value), 0.0)
        speed = math.hypot(output.linear.x, output.linear.y)
        if speed > max_linear > 0.0:
            scale = max_linear / speed
            output.linear.x *= scale
            output.linear.y *= scale
        max_angular = max(float(self.get_parameter("max_angular_speed").value), 0.0)
        output.angular.z = min(max(output.angular.z, -max_angular), max_angular)

        max_delta = max(
            float(self.get_parameter("max_linear_accel").value), 0.0
        ) * max(dt, 0.0)
        dx = output.linear.x - self._last_output.linear.x
        dy = output.linear.y - self._last_output.linear.y
        delta = math.hypot(dx, dy)
        if delta > max_delta > 0.0:
            scale = max_delta / delta
            output.linear.x = self._last_output.linear.x + dx * scale
            output.linear.y = self._last_output.linear.y + dy * scale
        return output

    def _safe_control(self, motion_allowed: bool, control_fresh: bool) -> ChassisControl:
        if not motion_allowed or not control_fresh:
            return self._stop_control()
        if not self._control_seen:
            return self._default_control()
        return self._copy_control(self._control)

    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(max(now - self._last_tick, 0.0), 0.1)
        self._last_tick = now
        timeout = float(self.get_parameter("command_timeout_s").value)

        source = "none"
        desired = Twist()
        if now - self._last_teleop <= timeout:
            desired = self._copy_twist(self._teleop)
            source = "teleop"
        elif now - self._last_nav <= timeout:
            desired = self._copy_twist(self._nav)
            source = "nav2"

        hardware_timeout = float(self.get_parameter("hardware_timeout_s").value)
        hardware_online = (
            now - self._last_hardware <= hardware_timeout
            and bool(self._hardware.online)
        )
        requires_hardware = self._mode in (
            SystemStatus.MODE_HIL,
            SystemStatus.MODE_REAL,
        )

        control_timeout = float(self.get_parameter("control_timeout_s").value)
        control_fresh = (
            not self._control_seen
            or now - self._last_control <= control_timeout
        )
        requested_control = self._control if self._control_seen else self._default_control()
        control_requests_motion = (
            control_fresh
            and bool(requested_control.enable)
            and int(requested_control.mode) != ChassisControl.MODE_STOP
        )

        motion_allowed = (
            not self._estop
            and (hardware_online or not requires_hardware)
            and control_fresh
        )
        if not motion_allowed:
            desired = Twist()
            source = "blocked"
        elif not control_requests_motion:
            desired = Twist()
            source = "chassis_stop"

        output = self._limit(desired, dt) if motion_allowed else Twist()
        self._last_output = output
        self._cmd_pub.publish(output)

        safe_control = self._safe_control(motion_allowed, control_fresh)
        if motion_allowed and control_fresh and not control_requests_motion:
            safe_control = self._copy_control(requested_control)
            safe_control.mode = ChassisControl.MODE_STOP
        safe_control.header.stamp = self.get_clock().now().to_msg()
        self._control_pub.publish(safe_control)

        policy_timeout = float(self.get_parameter("policy_timeout_s").value)
        policy_fresh = (
            now - self._last_weapons_request <= policy_timeout
            and now - self._last_target_request <= policy_timeout
        )
        heat_margin = float(self.get_parameter("heat_safety_margin").value)
        heat_ok = (
            self._hardware.heat_17_limit <= 0.0
            or self._hardware.heat_17 + heat_margin < self._hardware.heat_17_limit
        )
        ammo_ok = (
            self._hardware.ammo_remaining < 0.0
            or self._hardware.ammo_remaining > 0.0
        )
        weapons_allowed = (
            motion_allowed
            and control_requests_motion
            and policy_fresh
            and self._weapons_requested
            and self._target_requested >= 0
            and heat_ok
            and ammo_ok
        )
        weapons = Bool()
        weapons.data = weapons_allowed
        self._weapons_pub.publish(weapons)
        target = Int8()
        target.data = self._target_requested if weapons_allowed else -1
        self._target_pub.publish(target)

        status = SystemStatus()
        status.header.stamp = self.get_clock().now().to_msg()
        status.mode = self._mode
        status.estop = self._estop
        status.hardware_online = hardware_online
        status.policy_online = policy_fresh
        status.command_fresh = source in ("teleop", "nav2")
        status.active_motion_source = source
        if not control_fresh:
            status.detail = "motion blocked by stale chassis_control"
        elif motion_allowed:
            status.detail = "ready"
        else:
            status.detail = "motion blocked by e-stop or hardware watchdog"
        self._status_pub.publish(status)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SafetySupervisor()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
