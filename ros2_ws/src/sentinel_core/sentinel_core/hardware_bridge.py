from __future__ import annotations

import math
import socket
import time

from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Int8
from tf2_ros import TransformBroadcaster

from sentinel_interfaces.msg import ChassisControl, HardwareState

from .wire_protocol import (
    CHASSIS_DIRECT,
    CHASSIS_STOP,
    FRAME_BODY,
    FrameParser,
    TYPE_TELEMETRY,
    decode_telemetry,
    encode_command,
)


class HardwareBridge(Node):
    def __init__(self) -> None:
        super().__init__("hardware_bridge")
        self.declare_parameter("transport", "serial")
        self.declare_parameter("endpoint", "/dev/ttyACM0")
        self.declare_parameter("baudrate", 921600)
        self.declare_parameter("udp_local_port", 20001)
        self.declare_parameter("command_rate_hz", 100.0)
        self.declare_parameter("command_timeout_s", 0.20)
        self.declare_parameter("control_timeout_s", 0.50)
        self.declare_parameter("publish_odometry", True)
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("odom_frame", "odom")

        self._transport_name = str(self.get_parameter("transport").value)
        self._transport = self._open_transport()
        self._parser = FrameParser()
        self._sequence = 0
        self._last_cmd_time = 0.0
        self._last_control_time = 0.0
        self._last_rx_time = 0.0
        self._last_rx_sequence = 0

        self._cmd = Twist()
        self._control = self._default_control()
        self._target = -1
        self._weapons_free = False
        self._estop = True
        self._last_telemetry = None

        self.create_subscription(Twist, "/sentry/cmd_vel_safe", self._on_cmd, 20)
        self.create_subscription(
            ChassisControl,
            "/sentry/chassis_control_safe",
            self._on_control,
            20,
        )
        self.create_subscription(
            Bool, "/sentry/weapons_free_safe", self._on_weapons, 10
        )
        self.create_subscription(Int8, "/sentry/target_safe", self._on_target, 10)
        self.create_subscription(Bool, "/sentry/estop", self._on_estop, 10)

        self._state_pub = self.create_publisher(
            HardwareState, "/sentry/hardware_state", 10
        )
        self._odom_pub = self.create_publisher(Odometry, "/sentry/odom", 20)
        self._tf = TransformBroadcaster(self)

        rate = max(float(self.get_parameter("command_rate_hz").value), 1.0)
        self.create_timer(1.0 / rate, self._tick)
        self.create_timer(0.1, self._publish_state)

    @staticmethod
    def _default_control() -> ChassisControl:
        control = ChassisControl()
        control.mode = CHASSIS_DIRECT
        control.frame = FRAME_BODY
        control.spin_wz_rad_s = 0.0
        control.follow_yaw_offset_rad = 0.0
        control.yaw_big_target_rad = 0.0
        control.yaw_small_target_rad = 0.0
        control.pitch_target_rad = 0.0
        control.enable = True
        return control

    def _open_transport(self):
        endpoint = str(self.get_parameter("endpoint").value)
        if self._transport_name == "udp":
            if ":" not in endpoint:
                raise ValueError("UDP endpoint must be host:port")
            host, port_text = endpoint.rsplit(":", 1)
            transport = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            transport.bind(
                ("0.0.0.0", int(self.get_parameter("udp_local_port").value))
            )
            transport.connect((host, int(port_text)))
            transport.setblocking(False)
            return transport
        if self._transport_name == "serial":
            try:
                import serial
            except ImportError as exc:
                raise RuntimeError(
                    "install python3-serial for serial transport"
                ) from exc
            return serial.Serial(
                endpoint,
                baudrate=int(self.get_parameter("baudrate").value),
                timeout=0,
                write_timeout=0.02,
            )
        raise ValueError(f"unsupported hardware transport: {self._transport_name}")

    def _on_cmd(self, message: Twist) -> None:
        values = (message.linear.x, message.linear.y, message.angular.z)
        if not all(math.isfinite(float(value)) for value in values):
            self.get_logger().warning("dropping non-finite safe command")
            return
        self._cmd = message
        self._last_cmd_time = time.monotonic()

    def _on_control(self, message: ChassisControl) -> None:
        values = (
            message.spin_wz_rad_s,
            message.follow_yaw_offset_rad,
            message.yaw_big_target_rad,
            message.yaw_small_target_rad,
            message.pitch_target_rad,
        )
        if not all(math.isfinite(float(value)) for value in values):
            self.get_logger().warning("dropping non-finite chassis control")
            return
        if int(message.mode) not in (
            ChassisControl.MODE_STOP,
            ChassisControl.MODE_DIRECT,
            ChassisControl.MODE_FOLLOW,
            ChassisControl.MODE_SPIN,
        ):
            self.get_logger().warning("dropping invalid chassis mode")
            return
        if int(message.frame) not in (
            ChassisControl.FRAME_BODY,
            ChassisControl.FRAME_GIMBAL,
            ChassisControl.FRAME_WORLD,
        ):
            self.get_logger().warning("dropping invalid command frame")
            return
        self._control = message
        self._last_control_time = time.monotonic()

    def _on_weapons(self, message: Bool) -> None:
        self._weapons_free = bool(message.data)

    def _on_target(self, message: Int8) -> None:
        self._target = int(message.data)

    def _on_estop(self, message: Bool) -> None:
        self._estop = bool(message.data)

    def _send(self, data: bytes) -> None:
        if self._transport_name == "udp":
            self._transport.send(data)
        else:
            self._transport.write(data)

    def _receive(self) -> bytes:
        try:
            if self._transport_name == "udp":
                return self._transport.recv(4096)
            return self._transport.read(4096)
        except (BlockingIOError, TimeoutError):
            return b""

    def _tick(self) -> None:
        now = time.monotonic()
        cmd_fresh = (
            now - self._last_cmd_time
            <= float(self.get_parameter("command_timeout_s").value)
        )
        control_fresh = (
            self._last_control_time <= 0.0
            or now - self._last_control_time
            <= float(self.get_parameter("control_timeout_s").value)
        )

        command = self._cmd if cmd_fresh and not self._estop else Twist()
        control = self._control if control_fresh else self._default_control()

        enabled = (
            cmd_fresh
            and control_fresh
            and bool(control.enable)
            and not self._estop
        )
        mode = int(control.mode) if enabled else CHASSIS_STOP
        frame_id = int(control.frame) if enabled else FRAME_BODY

        frame = encode_command(
            sequence=self._sequence,
            timestamp_ms=int(now * 1000.0),
            vx_m_s=command.linear.x if enabled else 0.0,
            vy_m_s=command.linear.y if enabled else 0.0,
            wz_rad_s=command.angular.z if enabled else 0.0,
            spin_wz_rad_s=float(control.spin_wz_rad_s) if enabled else 0.0,
            follow_yaw_offset_rad=(
                float(control.follow_yaw_offset_rad) if enabled else 0.0
            ),
            yaw_big_target_rad=(
                float(control.yaw_big_target_rad) if enabled else 0.0
            ),
            yaw_small_target_rad=(
                float(control.yaw_small_target_rad) if enabled else 0.0
            ),
            pitch_target_rad=(
                float(control.pitch_target_rad) if enabled else 0.0
            ),
            chassis_mode=mode,
            command_frame=frame_id,
            target_slot=self._target if enabled else -1,
            weapons_free=self._weapons_free and enabled,
            estop=self._estop,
            enable=enabled,
        )
        self._sequence = (self._sequence + 1) & 0xFFFF

        try:
            self._send(frame)
            data = self._receive()
        except (OSError, ValueError) as exc:
            self.get_logger().error(
                f"hardware transport error: {exc}",
                throttle_duration_sec=2.0,
            )
            return

        for received in self._parser.feed(data):
            if received.message_type == TYPE_TELEMETRY:
                self._last_telemetry = decode_telemetry(received)
                self._last_rx_time = now
                self._last_rx_sequence = received.sequence
                if bool(self.get_parameter("publish_odometry").value):
                    self._publish_odometry()

    def _publish_odometry(self) -> None:
        telemetry = self._last_telemetry
        if telemetry is None:
            return

        stamp = self.get_clock().now().to_msg()
        half = telemetry.yaw_rad * 0.5
        qz, qw = math.sin(half), math.cos(half)

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = str(self.get_parameter("odom_frame").value)
        odom.child_frame_id = str(self.get_parameter("base_frame").value)
        odom.pose.pose.position.x = telemetry.x_m
        odom.pose.pose.position.y = telemetry.y_m
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = telemetry.vx_m_s
        odom.twist.twist.linear.y = telemetry.vy_m_s
        odom.twist.twist.angular.z = telemetry.wz_rad_s
        self._odom_pub.publish(odom)

        transform = TransformStamped()
        transform.header = odom.header
        transform.child_frame_id = odom.child_frame_id
        transform.transform.translation.x = telemetry.x_m
        transform.translation.y = telemetry.y_m
        transform.transform.rotation.z = qz
        transform.transform.rotation.w = qw
        self._tf.sendTransform(transform)

    def _publish_state(self) -> None:
        now = time.monotonic()
        telemetry = self._last_telemetry

        state = HardwareState()
        state.header.stamp = self.get_clock().now().to_msg()
        state.online = telemetry is not None and now - self._last_rx_time < 0.25
        state.estop = self._estop

        if telemetry is not None:
            state.estop = telemetry.estop
            state.enabled = telemetry.enabled
            state.command_fresh = telemetry.command_fresh
            state.imu_valid = telemetry.imu_valid
            state.gimbal_valid = telemetry.gimbal_valid
            state.swerve_valid = telemetry.swerve_valid
            state.chassis_mode = telemetry.chassis_mode
            state.command_frame = telemetry.command_frame

            state.attitude_roll_rad = telemetry.attitude_roll_rad
            state.attitude_pitch_rad = telemetry.attitude_pitch_rad
            state.attitude_yaw_rad = telemetry.attitude_yaw_rad

            state.yaw_big_rad = telemetry.yaw_big_rad
            state.yaw_small_rad = telemetry.yaw_small_rad
            state.pitch_rad = telemetry.pitch_rad

            state.steer_angle_rad = list(telemetry.steer_angle_rad)
            state.drive_speed_rad_s = list(telemetry.drive_speed_rad_s)

            state.heat_17 = telemetry.heat_17
            state.heat_17_limit = telemetry.heat_17_limit
            state.ammo_remaining = telemetry.ammo_remaining
            state.battery_voltage = telemetry.battery_voltage
            state.fault_flags = telemetry.fault_flags
        else:
            state.ammo_remaining = -1.0

        state.last_rx_sequence = self._last_rx_sequence
        self._state_pub.publish(state)

    def destroy_node(self):
        try:
            self._transport.close()
        finally:
            return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = HardwareBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
