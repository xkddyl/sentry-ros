"Little-endian, CRC-protected protocol shared by ROS 2 and STM32."

from __future__ import annotations

from dataclasses import dataclass
import struct


MAGIC = 0x534E
VERSION = 2
TYPE_COMMAND = 1
TYPE_TELEMETRY = 2
MAX_PAYLOAD = 256

CHASSIS_STOP = 0
CHASSIS_DIRECT = 1
CHASSIS_FOLLOW = 2
CHASSIS_SPIN = 3

FRAME_BODY = 0
FRAME_GIMBAL = 1
FRAME_WORLD = 2

COMMAND_FLAG_WEAPONS_FREE = 1 << 0
COMMAND_FLAG_ESTOP = 1 << 1
COMMAND_FLAG_ENABLE = 1 << 2

STATUS_FLAG_ESTOP = 1 << 0
STATUS_FLAG_ENABLED = 1 << 1
STATUS_FLAG_IMU_VALID = 1 << 2
STATUS_FLAG_GIMBAL_VALID = 1 << 3
STATUS_FLAG_SWERVE_VALID = 1 << 4
STATUS_FLAG_COMMAND_FRESH = 1 << 5

HEADER = struct.Struct("<HBBHHI")
COMMAND = struct.Struct("<hhhhhhhhbBBB")
TELEMETRY = struct.Struct(
    "<iii"
    "hhh"
    "hhh"
    "hhh"
    "hhhh"
    "hhhh"
    "HHHH"
    "IHBB"
)
CRC = struct.Struct("<H")
MAGIC_BYTES = struct.pack("<H", MAGIC)


@dataclass(slots=True)
class Frame:
    message_type: int
    sequence: int
    timestamp_ms: int
    payload: bytes


@dataclass(slots=True)
class Command:
    vx_m_s: float
    vy_m_s: float
    wz_rad_s: float

    spin_wz_rad_s: float
    follow_yaw_offset_rad: float

    yaw_big_target_rad: float
    yaw_small_target_rad: float
    pitch_target_rad: float

    target_slot: int
    chassis_mode: int
    command_frame: int

    weapons_free: bool
    estop: bool
    enable: bool


@dataclass(slots=True)
class Telemetry:
    x_m: float
    y_m: float
    yaw_rad: float

    vx_m_s: float
    vy_m_s: float
    wz_rad_s: float

    attitude_roll_rad: float
    attitude_pitch_rad: float
    attitude_yaw_rad: float

    yaw_big_rad: float
    yaw_small_rad: float
    pitch_rad: float

    steer_angle_rad: tuple[float, float, float, float]
    drive_speed_rad_s: tuple[float, float, float, float]

    heat_17: float
    heat_17_limit: float
    ammo_remaining: float
    battery_voltage: float
    fault_flags: int

    status_flags: int
    chassis_mode: int
    command_frame: int

    @property
    def estop(self) -> bool:
        return bool(self.status_flags & STATUS_FLAG_ESTOP)

    @property
    def enabled(self) -> bool:
        return bool(self.status_flags & STATUS_FLAG_ENABLED)

    @property
    def imu_valid(self) -> bool:
        return bool(self.status_flags & STATUS_FLAG_IMU_VALID)

    @property
    def gimbal_valid(self) -> bool:
        return bool(self.status_flags & STATUS_FLAG_GIMBAL_VALID)

    @property
    def swerve_valid(self) -> bool:
        return bool(self.status_flags & STATUS_FLAG_SWERVE_VALID)

    @property
    def command_fresh(self) -> bool:
        return bool(self.status_flags & STATUS_FLAG_COMMAND_FRESH)


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    crc = initial & 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = (
                ((crc << 1) ^ 0x1021) & 0xFFFF
                if crc & 0x8000
                else (crc << 1) & 0xFFFF
            )
    return crc


def _clamp_int(value: float, low: int, high: int) -> int:
    return min(max(int(round(value)), low), high)


def _four(values) -> tuple[float, float, float, float]:
    result = tuple(float(v) for v in values)
    if len(result) != 4:
        raise ValueError("expected exactly four swerve-module values")
    return result  # type: ignore[return-value]


def encode_frame(
    message_type: int, sequence: int, timestamp_ms: int, payload: bytes
) -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload is too large")
    header = HEADER.pack(
        MAGIC,
        VERSION,
        int(message_type) & 0xFF,
        len(payload),
        int(sequence) & 0xFFFF,
        int(timestamp_ms) & 0xFFFFFFFF,
    )
    body = header + payload
    return body + CRC.pack(crc16_ccitt(body))


def encode_command(
    *,
    sequence: int,
    timestamp_ms: int,
    vx_m_s: float,
    vy_m_s: float,
    wz_rad_s: float,
    target_slot: int,
    weapons_free: bool,
    estop: bool,
    chassis_mode: int = CHASSIS_DIRECT,
    command_frame: int = FRAME_BODY,
    spin_wz_rad_s: float = 0.0,
    follow_yaw_offset_rad: float = 0.0,
    yaw_big_target_rad: float = 0.0,
    yaw_small_target_rad: float = 0.0,
    pitch_target_rad: float = 0.0,
    enable: bool = True,
) -> bytes:
    if chassis_mode not in (
        CHASSIS_STOP,
        CHASSIS_DIRECT,
        CHASSIS_FOLLOW,
        CHASSIS_SPIN,
    ):
        raise ValueError("invalid chassis_mode")
    if command_frame not in (FRAME_BODY, FRAME_GIMBAL, FRAME_WORLD):
        raise ValueError("invalid command_frame")

    flags = 0
    if weapons_free:
        flags |= COMMAND_FLAG_WEAPONS_FREE
    if estop:
        flags |= COMMAND_FLAG_ESTOP
    if enable:
        flags |= COMMAND_FLAG_ENABLE

    payload = COMMAND.pack(
        _clamp_int(vx_m_s * 1000.0, -32768, 32767),
        _clamp_int(vy_m_s * 1000.0, -32768, 32767),
        _clamp_int(wz_rad_s * 1000.0, -32768, 32767),
        _clamp_int(spin_wz_rad_s * 1000.0, -32768, 32767),
        _clamp_int(follow_yaw_offset_rad * 1000.0, -32768, 32767),
        _clamp_int(yaw_big_target_rad * 1000.0, -32768, 32767),
        _clamp_int(yaw_small_target_rad * 1000.0, -32768, 32767),
        _clamp_int(pitch_target_rad * 1000.0, -32768, 32767),
        _clamp_int(target_slot, -1, 127),
        int(chassis_mode),
        int(command_frame),
        flags,
    )
    return encode_frame(TYPE_COMMAND, sequence, timestamp_ms, payload)


def decode_command(frame: Frame) -> Command:
    if frame.message_type != TYPE_COMMAND or len(frame.payload) != COMMAND.size:
        raise ValueError("not a command frame")

    (
        vx_mm_s,
        vy_mm_s,
        wz_mrad_s,
        spin_wz_mrad_s,
        follow_yaw_offset_mrad,
        yaw_big_target_mrad,
        yaw_small_target_mrad,
        pitch_target_mrad,
        target_slot,
        chassis_mode,
        command_frame,
        flags,
    ) = COMMAND.unpack(frame.payload)

    if chassis_mode not in (
        CHASSIS_STOP,
        CHASSIS_DIRECT,
        CHASSIS_FOLLOW,
        CHASSIS_SPIN,
    ):
        raise ValueError("invalid chassis_mode in command")
    if command_frame not in (FRAME_BODY, FRAME_GIMBAL, FRAME_WORLD):
        raise ValueError("invalid command_frame in command")

    return Command(
        vx_m_s=vx_mm_s / 1000.0,
        vy_m_s=vy_mm_s / 1000.0,
        wz_rad_s=wz_mrad_s / 1000.0,
        spin_wz_rad_s=spin_wz_mrad_s / 1000.0,
        follow_yaw_offset_rad=follow_yaw_offset_mrad / 1000.0,
        yaw_big_target_rad=yaw_big_target_mrad / 1000.0,
        yaw_small_target_rad=yaw_small_target_mrad / 1000.0,
        pitch_target_rad=pitch_target_mrad / 1000.0,
        target_slot=int(target_slot),
        chassis_mode=int(chassis_mode),
        command_frame=int(command_frame),
        weapons_free=bool(flags & COMMAND_FLAG_WEAPONS_FREE),
        estop=bool(flags & COMMAND_FLAG_ESTOP),
        enable=bool(flags & COMMAND_FLAG_ENABLE),
    )


def encode_telemetry(
    *,
    sequence: int,
    timestamp_ms: int,
    x_m: float,
    y_m: float,
    yaw_rad: float,
    vx_m_s: float,
    vy_m_s: float,
    wz_rad_s: float,
    heat_17: float,
    heat_17_limit: float,
    ammo_remaining: float,
    battery_voltage: float,
    fault_flags: int,
    attitude_roll_rad: float = 0.0,
    attitude_pitch_rad: float = 0.0,
    attitude_yaw_rad: float = 0.0,
    yaw_big_rad: float = 0.0,
    yaw_small_rad: float = 0.0,
    pitch_rad: float = 0.0,
    steer_angle_rad=(0.0, 0.0, 0.0, 0.0),
    drive_speed_rad_s=(0.0, 0.0, 0.0, 0.0),
    status_flags: int = 0,
    chassis_mode: int = CHASSIS_STOP,
    command_frame: int = FRAME_BODY,
) -> bytes:
    steer = _four(steer_angle_rad)
    drive = _four(drive_speed_rad_s)

    payload = TELEMETRY.pack(
        _clamp_int(x_m * 1000.0, -(2**31), 2**31 - 1),
        _clamp_int(y_m * 1000.0, -(2**31), 2**31 - 1),
        _clamp_int(yaw_rad * 1000.0, -(2**31), 2**31 - 1),
        _clamp_int(vx_m_s * 1000.0, -32768, 32767),
        _clamp_int(vy_m_s * 1000.0, -32768, 32767),
        _clamp_int(wz_rad_s * 1000.0, -32768, 32767),
        _clamp_int(attitude_roll_rad * 1000.0, -32768, 32767),
        _clamp_int(attitude_pitch_rad * 1000.0, -32768, 32767),
        _clamp_int(attitude_yaw_rad * 1000.0, -32768, 32767),
        _clamp_int(yaw_big_rad * 1000.0, -32768, 32767),
        _clamp_int(yaw_small_rad * 1000.0, -32768, 32767),
        _clamp_int(pitch_rad * 1000.0, -32768, 32767),
        *[_clamp_int(v * 1000.0, -32768, 32767) for v in steer],
        *[_clamp_int(v * 100.0, -32768, 32767) for v in drive],
        _clamp_int(heat_17, 0, 65535),
        _clamp_int(heat_17_limit, 0, 65535),
        _clamp_int(ammo_remaining, 0, 65535),
        _clamp_int(battery_voltage * 1000.0, 0, 65535),
        int(fault_flags) & 0xFFFFFFFF,
        int(status_flags) & 0xFFFF,
        int(chassis_mode) & 0xFF,
        int(command_frame) & 0xFF,
    )
    return encode_frame(TYPE_TELEMETRY, sequence, timestamp_ms, payload)


def decode_telemetry(frame: Frame) -> Telemetry:
    if frame.message_type != TYPE_TELEMETRY or len(frame.payload) != TELEMETRY.size:
        raise ValueError("not a telemetry frame")

    values = TELEMETRY.unpack(frame.payload)
    x_mm, y_mm, yaw_mrad = values[0:3]
    vx_mm_s, vy_mm_s, wz_mrad_s = values[3:6]
    roll_mrad, att_pitch_mrad, att_yaw_mrad = values[6:9]
    yaw_big_mrad, yaw_small_mrad, gimbal_pitch_mrad = values[9:12]
    steer = values[12:16]
    drive = values[16:20]
    heat, heat_limit, ammo, battery_mv = values[20:24]
    faults, status_flags, chassis_mode, command_frame = values[24:28]

    return Telemetry(
        x_m=x_mm / 1000.0,
        y_m=y_mm / 1000.0,
        yaw_rad=yaw_mrad / 1000.0,
        vx_m_s=vx_mm_s / 1000.0,
        vy_m_s=vy_mm_s / 1000.0,
        wz_rad_s=wz_mrad_s / 1000.0,
        attitude_roll_rad=roll_mrad / 1000.0,
        attitude_pitch_rad=att_pitch_mrad / 1000.0,
        attitude_yaw_rad=att_yaw_mrad / 1000.0,
        yaw_big_rad=yaw_big_mrad / 1000.0,
        yaw_small_rad=yaw_small_mrad / 1000.0,
        pitch_rad=gimbal_pitch_mrad / 1000.0,
        steer_angle_rad=tuple(v / 1000.0 for v in steer),
        drive_speed_rad_s=tuple(v / 100.0 for v in drive),
        heat_17=float(heat),
        heat_17_limit=float(heat_limit),
        ammo_remaining=float(ammo),
        battery_voltage=battery_mv / 1000.0,
        fault_flags=int(faults),
        status_flags=int(status_flags),
        chassis_mode=int(chassis_mode),
        command_frame=int(command_frame),
    )


class FrameParser:
    def __init__(self) -> None:
        self._buffer = bytearray()
        self.frames_ok = 0
        self.crc_errors = 0
        self.protocol_errors = 0
        self.framing_bytes_discarded = 0

    def _discard(self, count: int) -> None:
        count = min(max(int(count), 0), len(self._buffer))
        if count:
            del self._buffer[:count]
            self.framing_bytes_discarded += count

    def feed(self, data: bytes) -> list[Frame]:
        self._buffer.extend(data)
        frames: list[Frame] = []
        while True:
            index = self._buffer.find(MAGIC_BYTES)
            if index < 0:
                if self._buffer[-1:] == MAGIC_BYTES[:1]:
                    self._discard(max(len(self._buffer) - 1, 0))
                else:
                    self._discard(len(self._buffer))
                break
            if index:
                self._discard(index)
            if len(self._buffer) < HEADER.size:
                break
            magic, version, kind, size, sequence, timestamp = HEADER.unpack_from(
                self._buffer
            )
            if magic != MAGIC or version != VERSION or size > MAX_PAYLOAD:
                self.protocol_errors += 1
                self._discard(1)
                continue
            total = HEADER.size + size + CRC.size
            if len(self._buffer) < total:
                break
            body = bytes(self._buffer[: HEADER.size + size])
            expected_crc = CRC.unpack_from(self._buffer, HEADER.size + size)[0]
            if crc16_ccitt(body) != expected_crc:
                self.crc_errors += 1
                self._discard(1)
                continue
            frames.append(
                Frame(
                    message_type=kind,
                    sequence=sequence,
                    timestamp_ms=timestamp,
                    payload=body[HEADER.size:],
                )
            )
            self.frames_ok += 1
            del self._buffer[:total]
        return frames
