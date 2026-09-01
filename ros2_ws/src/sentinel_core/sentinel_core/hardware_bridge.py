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

from sentinel_interfaces.msg import (
    ChassisControl,
    HardwareDiagnostics,
    HardwareState,
)

from .wire_protocol import (
    CHASSIS_DIRECT,
    CHASSIS_STOP,
    FRAME_BODY,
    VERSION,
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
        self.declare_parameter("telemetry_timeout_s", 0.25)
        self.declare_parameter("hard_disconnect_timeout_s", 2.0)
        self.declare_parameter("reconnect_period_s", 1.0)
        self.declare_parameter("diagnostics_rate_hz", 2.0)
        self.declare_parameter("publish_odometry", True)
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("odom_frame", "odom")

        self._transport_name = str(self.get_parameter("transport").value)
        self._endpoint = str(self.get_parameter("endpoint").value)
        self._transport = None
        self._transport_state = HardwareDiagnostics.STATE_DISCONNECTED
        self._next_reconnect_time = 0.0
        self._opened_at = 0.0
        self._ever_connected = False
        self._last_transport_error = "not connected"

        self._parser = FrameParser()
        self._sequence = 0
        self._last_cmd_time = 0.0
        self._last_control_time = 0.0
        self._last_rx_time = 0.0
        self._last_rx_sequence = 0
        self._have_rx_sequence = False

        self._cmd = Twist()
        self._control = self._default_control()
        self._target = -1
        self._weapons_free = False
        self._estop = True
        self._last_telemetry = None

        self._tx_frames = 0
        self._rx_frames = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._decode_errors = 0
        self._sequence_gaps = 0
        self._duplicate_frames = 0
        self._out_of_order_frames = 0
        self._reconnect_count = 0
        self._last_diag_time = time.monotonic()
        self._last_diag_tx_frames = 0
        self._last_diag_rx_frames = 0

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
        self._diag_pub = self.create_publisher(
            HardwareDiagnostics, "/sentry/hardware_diagnostics", 10
        )
        self._odom_pub = self.create_publisher(Odometry, "/sentry/odom", 20)
        self._tf = TransformBroadcaster(self)

        rate = max(float(self.get_parameter("command_rate_hz").value), 1.0)
        self.create_timer(1.0 / rate, self._tick)
        self.create_timer(0.1, self._publish_state)
        diag_rate = max(float(self.get_parameter("diagnostics_rate_hz").value), 0.2)
        self.create_timer(1.0 / diag_rate, self._publish_diagnostics)

        self._ensure_transport(time.monotonic())

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
        if self._transport_name == "udp":
            if ":" not in self._endpoint:
                raise ValueError("UDP endpoint must be host:port")
            host, port_text = self._endpoint.rsplit(":", 1)
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
                self._endpoint,
                baudrate=int(self.get_parameter("baudrate").value),
                timeout=0,
                write_timeout=0.02,
            )
        raise ValueError(f"unsupported hardware transport: {self._transport_name}")

    def _ensure_transport(self, now: float) -> bool:
        if self._transport is not None:
            return True
        if now < self._next_reconnect_time:
            return False

        self._transport_state = HardwareDiagnostics.STATE_CONNECTING
        try:
            transport = self._open_transport()
        except (OSError, RuntimeError, ValueError) as exc:
            self._transport_state = HardwareDiagnostics.STATE_DISCONNECTED
            self._last_transport_error = str(exc)
            self._next_reconnect_time = now + max(
                float(self.get_parameter("reconnect_period_s").value), 0.1
            )
            self.get_logger().warning(f"hardware connect failed: {exc}")
            return False

        self._transport = transport
        self._transport_state = HardwareDiagnostics.STATE_CONNECTED
        self._opened_at = now
        self._last_transport_error = ""
        if self._ever_connected:
            self._reconnect_count += 1
        else:
            self._ever_connected = True
        self.get_logger().info(
            f"hardware transport connected: {self._transport_name} {self._endpoint}"
        )
        return True

    def _close_transport(self) -> None:
        transport = self._transport
        self._transport = None
        if transport is None:
            return
        try:
            transport.close()
        except OSError:
            pass

    def _mark_transport_fault(self, now: float, reason: str) -> None:
        self._close_transport()
        self._transport_state = HardwareDiagnostics.STATE_DISCONNECTED
        self._last_transport_error = reason
        self._next_reconnect_time = now + max(
            float(self.get_parameter("reconnect_period_s").value), 0.1
        )
        self.get_logger().warning(f"hardware transport fault: {reason}")

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
        if self._transport is None:
            raise OSError("transport is not connected")
        if self._transport_name == "udp":
            sent = self._transport.send(data)
            if sent != len(data):
                raise OSError(f"short UDP send: {sent}/{len(data)}")
        else:
            sent = self._transport.write(data)
            if sent != len(data):
                raise OSError(f"short serial write: {sent}/{len(data)}")

    def _receive_chunks(self) -> list[bytes]:
        if self._transport is None:
            return []
        chunks: list[bytes] = []
        if self._transport_name == "udp":
            while True:
                try:
                    data = self._transport.recv(4096)
                except (BlockingIOError, TimeoutError):
                    break
                if not data:
                    break
                chunks.append(data)
            return chunks

        data = self._transport.read(4096)
        if data:
            chunks.append(data)
        return chunks

    def _classify_sequence(self, sequence: int) -> None:
        sequence = int(sequence) & 0xFFFF
        if not self._have_rx_sequence:
            self._last_rx_sequence = sequence
            self._have_rx_sequence = True
            return

        delta = (sequence - self._last_rx_sequence) & 0xFFFF
        if delta == 0:
            self._duplicate_frames += 1
            return
        if delta == 1:
            self._last_rx_sequence = sequence
            return
        if delta < 0x8000:
            self._sequence_gaps += delta - 1
            self._last_rx_sequence = sequence
            return
        self._out_of_order_frames += 1

    def _build_command_frame(self, now: float) -> bytes:
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
        return frame

    def _tick(self) -> None:
        now = time.monotonic()
        frame = self._build_command_frame(now)

        if not self._ensure_transport(now):
            return

        try:
            self._send(frame)
            self._tx_frames += 1
            self._tx_bytes += len(frame)
            chunks = self._receive_chunks()
        except (OSError, ValueError) as exc:
            self._mark_transport_fault(now, str(exc))
            return

        for chunk in chunks:
            self._rx_bytes += len(chunk)
            for received in self._parser.feed(chunk):
                if received.message_type != TYPE_TELEMETRY:
                    self._decode_errors += 1
                    continue
                try:
                    telemetry = decode_telemetry(received)
                except ValueError:
                    self._decode_errors += 1
                    continue

                self._classify_sequence(received.sequence)
                self._last_telemetry = telemetry
                self._last_rx_time = now
                self._rx_frames += 1
                if bool(self.get_parameter("publish_odometry").value):
                    self._publish_odometry()

        telemetry_timeout = max(
            float(self.get_parameter("telemetry_timeout_s").value), 0.01
        )
        telemetry_age = (
            now - self._last_rx_time if self._last_rx_time > 0.0 else now - self._opened_at
        )
        if telemetry_age <= telemetry_timeout:
            self._transport_state = HardwareDiagnostics.STATE_CONNECTED
        else:
            self._transport_state = HardwareDiagnostics.STATE_DEGRADED

        hard_timeout = max(
            float(self.get_parameter("hard_disconnect_timeout_s").value),
            telemetry_timeout,
        )
        if self._transport_name == "serial" and telemetry_age > hard_timeout:
            self._mark_transport_fault(now, "telemetry timeout")

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
        transform.transform.translation.y = telemetry.y_m
        transform.transform.rotation.z = qz
        transform.transform.rotation.w = qw
        self._tf.sendTransform(transform)

    def _telemetry_fresh(self, now: float) -> bool:
        timeout = max(float(self.get_parameter("telemetry_timeout_s").value), 0.01)
        return self._last_rx_time > 0.0 and now - self._last_rx_time <= timeout

    def _publish_state(self) -> None:
        now = time.monotonic()
        telemetry = self._last_telemetry

        state = HardwareState()
        state.header.stamp = self.get_clock().now().to_msg()
        state.online = self._telemetry_fresh(now)
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

    def _publish_diagnostics(self) -> None:
        now = time.monotonic()
        dt = max(now - self._last_diag_time, 1e-6)
        tx_rate = (self._tx_frames - self._last_diag_tx_frames) / dt
        rx_rate = (self._rx_frames - self._last_diag_rx_frames) / dt
        self._last_diag_time = now
        self._last_diag_tx_frames = self._tx_frames
        self._last_diag_rx_frames = self._rx_frames

        fresh = self._telemetry_fresh(now)
        if self._last_rx_time > 0.0:
            rx_age_ms = (now - self._last_rx_time) * 1000.0
        else:
            rx_age_ms = -1.0

        message = HardwareDiagnostics()
        message.header.stamp = self.get_clock().now().to_msg()
        message.transport_state = int(self._transport_state)
        message.transport = self._transport_name
        message.endpoint = self._endpoint
        message.protocol_version = VERSION
        message.telemetry_fresh = fresh
        message.last_valid_rx_age_ms = float(rx_age_ms)
        message.tx_rate_hz = float(tx_rate)
        message.rx_rate_hz = float(rx_rate)
        message.tx_frames = self._tx_frames
        message.rx_frames = self._rx_frames
        message.tx_bytes = self._tx_bytes
        message.rx_bytes = self._rx_bytes
        message.crc_errors = self._parser.crc_errors
        message.protocol_errors = self._parser.protocol_errors + self._decode_errors
        message.framing_bytes_discarded = self._parser.framing_bytes_discarded
        message.sequence_gaps = self._sequence_gaps
        message.duplicate_frames = self._duplicate_frames
        message.out_of_order_frames = self._out_of_order_frames
        message.reconnect_count = self._reconnect_count
        message.last_rx_sequence = self._last_rx_sequence

        if self._transport_state == HardwareDiagnostics.STATE_CONNECTED:
            message.detail = "connected; telemetry valid"
        elif self._transport_state == HardwareDiagnostics.STATE_DEGRADED:
            message.detail = "transport open; telemetry stale or missing"
        elif self._transport_state == HardwareDiagnostics.STATE_CONNECTING:
            message.detail = "connecting"
        else:
            message.detail = self._last_transport_error or "disconnected"
        self._diag_pub.publish(message)

    def destroy_node(self):
        self._close_transport()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = HardwareBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
