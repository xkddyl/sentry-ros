from __future__ import annotations

from collections import deque
import math
import random
import socket
import time

import rclpy
from rclpy.node import Node

from .wire_protocol import (
    CHASSIS_SPIN,
    CHASSIS_STOP,
    CRC,
    FRAME_WORLD,
    STATUS_FLAG_COMMAND_FRESH,
    STATUS_FLAG_ENABLED,
    STATUS_FLAG_ESTOP,
    STATUS_FLAG_GIMBAL_VALID,
    STATUS_FLAG_IMU_VALID,
    STATUS_FLAG_SWERVE_VALID,
    TYPE_COMMAND,
    VERSION,
    FrameParser,
    crc16_ccitt,
    decode_command,
    encode_telemetry,
)


class MockLowerController(Node):
    """UDP binary-protocol peer that behaves like an unpowered STM32 bench target.

    It deliberately does not publish HardwareState or Odometry itself. All data
    must travel through the same wire protocol and HardwareBridge used by real
    hardware, which makes it suitable for transport/safety regression tests.
    """

    def __init__(self) -> None:
        super().__init__("mock_lower_controller")
        self.declare_parameter("bind_host", "127.0.0.1")
        self.declare_parameter("bind_port", 20000)
        self.declare_parameter("poll_rate_hz", 500.0)
        self.declare_parameter("drop_rate", 0.0)
        self.declare_parameter("crc_error_rate", 0.0)
        self.declare_parameter("wrong_version_rate", 0.0)
        self.declare_parameter("delay_ms", 0.0)
        self.declare_parameter("freeze", False)
        self.declare_parameter("sequence_jump_every", 0)
        self.declare_parameter("random_seed", 7)
        self.declare_parameter("battery_voltage", 24.0)
        self.declare_parameter("imu_valid", True)
        self.declare_parameter("gimbal_valid", True)
        self.declare_parameter("swerve_valid", False)

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(
            (
                str(self.get_parameter("bind_host").value),
                int(self.get_parameter("bind_port").value),
            )
        )
        self._socket.setblocking(False)
        self._parser = FrameParser()
        self._rng = random.Random(int(self.get_parameter("random_seed").value))
        self._pending: deque[tuple[float, tuple[str, int], bytes]] = deque()

        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0
        self._last_command_time = 0.0
        self._telemetry_sequence = 0
        self._sent_count = 0
        self._last_command = None

        rate = max(float(self.get_parameter("poll_rate_hz").value), 20.0)
        self.create_timer(1.0 / rate, self._tick)
        self.get_logger().info(
            "mock lower controller listening on "
            f"{self.get_parameter('bind_host').value}:"
            f"{self.get_parameter('bind_port').value}"
        )

    @staticmethod
    def _clamp_probability(value: float) -> float:
        return min(max(float(value), 0.0), 1.0)

    def _integrate(self, command, now: float) -> tuple[float, float, float]:
        if self._last_command_time <= 0.0:
            dt = 0.0
        else:
            dt = min(max(now - self._last_command_time, 0.0), 0.05)
        self._last_command_time = now

        enabled = bool(command.enable) and not bool(command.estop)
        moving = enabled and int(command.chassis_mode) != CHASSIS_STOP
        if not moving:
            vx = 0.0
            vy = 0.0
            wz = 0.0
        else:
            vx = float(command.vx_m_s)
            vy = float(command.vy_m_s)
            wz = (
                float(command.spin_wz_rad_s)
                if int(command.chassis_mode) == CHASSIS_SPIN
                else float(command.wz_rad_s)
            )

        if int(command.command_frame) == FRAME_WORLD:
            world_vx = vx
            world_vy = vy
        else:
            # BODY is exact. GIMBAL intentionally falls back to BODY here;
            # the transport mock does not implement gimbal/chassis kinematics.
            c = math.cos(self._yaw)
            s = math.sin(self._yaw)
            world_vx = c * vx - s * vy
            world_vy = s * vx + c * vy

        self._x += world_vx * dt
        self._y += world_vy * dt
        self._yaw += wz * dt
        self._yaw = math.atan2(math.sin(self._yaw), math.cos(self._yaw))
        return vx, vy, wz

    def _status_flags(self, command) -> int:
        flags = STATUS_FLAG_COMMAND_FRESH
        if command.estop:
            flags |= STATUS_FLAG_ESTOP
        if command.enable and not command.estop:
            flags |= STATUS_FLAG_ENABLED
        if bool(self.get_parameter("imu_valid").value):
            flags |= STATUS_FLAG_IMU_VALID
        if bool(self.get_parameter("gimbal_valid").value):
            flags |= STATUS_FLAG_GIMBAL_VALID
        if bool(self.get_parameter("swerve_valid").value):
            flags |= STATUS_FLAG_SWERVE_VALID
        return flags

    def _make_telemetry(self, command, now: float) -> bytes:
        vx, vy, wz = self._integrate(command, now)
        sequence = self._telemetry_sequence
        self._telemetry_sequence = (self._telemetry_sequence + 1) & 0xFFFF
        self._sent_count += 1

        jump_every = max(int(self.get_parameter("sequence_jump_every").value), 0)
        if jump_every and self._sent_count % jump_every == 0:
            self._telemetry_sequence = (self._telemetry_sequence + 1) & 0xFFFF

        raw = bytearray(
            encode_telemetry(
                sequence=sequence,
                timestamp_ms=int(now * 1000.0),
                x_m=self._x,
                y_m=self._y,
                yaw_rad=self._yaw,
                vx_m_s=vx,
                vy_m_s=vy,
                wz_rad_s=wz,
                attitude_roll_rad=0.0,
                attitude_pitch_rad=0.0,
                attitude_yaw_rad=self._yaw,
                yaw_big_rad=0.0,
                yaw_small_rad=0.0,
                pitch_rad=0.0,
                steer_angle_rad=(0.0, 0.0, 0.0, 0.0),
                drive_speed_rad_s=(0.0, 0.0, 0.0, 0.0),
                heat_17=0.0,
                heat_17_limit=260.0,
                ammo_remaining=0.0,
                battery_voltage=float(self.get_parameter("battery_voltage").value),
                fault_flags=0,
                status_flags=self._status_flags(command),
                chassis_mode=int(command.chassis_mode),
                command_frame=int(command.command_frame),
            )
        )

        wrong_version_rate = self._clamp_probability(
            self.get_parameter("wrong_version_rate").value
        )
        if self._rng.random() < wrong_version_rate:
            raw[2] = (VERSION + 1) & 0xFF
            body = bytes(raw[:-CRC.size])
            raw[-CRC.size :] = CRC.pack(crc16_ccitt(body))

        crc_error_rate = self._clamp_probability(
            self.get_parameter("crc_error_rate").value
        )
        if self._rng.random() < crc_error_rate:
            raw[-1] ^= 0x01

        return bytes(raw)

    def _handle_datagram(self, data: bytes, address: tuple[str, int], now: float) -> None:
        for frame in self._parser.feed(data):
            if frame.message_type != TYPE_COMMAND:
                continue
            try:
                command = decode_command(frame)
            except ValueError as exc:
                self.get_logger().warning(f"mock rejected command frame: {exc}")
                continue

            self._last_command = command
            if bool(self.get_parameter("freeze").value):
                continue

            drop_rate = self._clamp_probability(self.get_parameter("drop_rate").value)
            if self._rng.random() < drop_rate:
                continue

            response = self._make_telemetry(command, now)
            delay_s = max(float(self.get_parameter("delay_ms").value), 0.0) / 1000.0
            self._pending.append((now + delay_s, address, response))

    def _flush_pending(self, now: float) -> None:
        while self._pending and self._pending[0][0] <= now:
            _, address, data = self._pending.popleft()
            try:
                self._socket.sendto(data, address)
            except OSError as exc:
                self.get_logger().warning(f"mock UDP send failed: {exc}")

    def _tick(self) -> None:
        now = time.monotonic()
        while True:
            try:
                data, address = self._socket.recvfrom(4096)
            except BlockingIOError:
                break
            except OSError as exc:
                self.get_logger().warning(f"mock UDP receive failed: {exc}")
                break
            if data:
                self._handle_datagram(data, address, now)
        self._flush_pending(now)

    def destroy_node(self):
        self._socket.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MockLowerController()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
