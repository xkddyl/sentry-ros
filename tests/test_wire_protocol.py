from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "sentinel_core"))

from sentinel_core.wire_protocol import (  # noqa: E402
    CHASSIS_SPIN,
    FRAME_WORLD,
    FrameParser,
    STATUS_FLAG_COMMAND_FRESH,
    STATUS_FLAG_ENABLED,
    STATUS_FLAG_IMU_VALID,
    TYPE_COMMAND,
    TYPE_TELEMETRY,
    decode_telemetry,
    encode_command,
    encode_telemetry,
)


class WireProtocolTest(unittest.TestCase):
    def test_chunking_noise_crc_and_v2_telemetry(self) -> None:
        flags = (
            STATUS_FLAG_ENABLED
            | STATUS_FLAG_IMU_VALID
            | STATUS_FLAG_COMMAND_FRESH
        )
        valid = encode_telemetry(
            sequence=9,
            timestamp_ms=7654321,
            x_m=1.25,
            y_m=-0.5,
            yaw_rad=0.75,
            vx_m_s=0.2,
            vy_m_s=-0.3,
            wz_rad_s=0.1,
            attitude_roll_rad=0.01,
            attitude_pitch_rad=-0.02,
            attitude_yaw_rad=0.74,
            yaw_big_rad=0.1,
            yaw_small_rad=-0.05,
            pitch_rad=0.025,
            steer_angle_rad=(0.1, -0.2, 0.3, -0.4),
            drive_speed_rad_s=(10.0, -11.0, 12.0, -13.0),
            heat_17=33,
            heat_17_limit=260,
            ammo_remaining=123,
            battery_voltage=24.5,
            fault_flags=0xA5,
            status_flags=flags,
            chassis_mode=CHASSIS_SPIN,
            command_frame=FRAME_WORLD,
        )
        corrupted = bytearray(valid)
        corrupted[-1] ^= 0x01

        parser = FrameParser()
        output = []
        stream = b"noise" + bytes(corrupted) + valid
        for index in range(0, len(stream), 3):
            output.extend(parser.feed(stream[index : index + 3]))

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0].message_type, TYPE_TELEMETRY)

        decoded = decode_telemetry(output[0])
        self.assertAlmostEqual(decoded.x_m, 1.25)
        self.assertAlmostEqual(decoded.y_m, -0.5)
        self.assertAlmostEqual(decoded.attitude_pitch_rad, -0.02)
        self.assertAlmostEqual(decoded.drive_speed_rad_s[3], -13.0)
        self.assertTrue(decoded.enabled)
        self.assertTrue(decoded.imu_valid)
        self.assertTrue(decoded.command_fresh)
        self.assertEqual(decoded.chassis_mode, CHASSIS_SPIN)
        self.assertEqual(decoded.command_frame, FRAME_WORLD)
        self.assertEqual(decoded.fault_flags, 0xA5)

    def test_python_and_c_command_encoding_match(self) -> None:
        expected = encode_command(
            sequence=513,
            timestamp_ms=123456789,
            vx_m_s=1.25,
            vy_m_s=-0.5,
            wz_rad_s=0.0,
            spin_wz_rad_s=0.35,
            follow_yaw_offset_rad=0.0,
            yaw_big_target_rad=0.1,
            yaw_small_target_rad=-0.05,
            pitch_target_rad=0.025,
            chassis_mode=CHASSIS_SPIN,
            command_frame=FRAME_WORLD,
            target_slot=5,
            weapons_free=True,
            estop=False,
            enable=True,
        ).hex()

        protocol = ROOT / "firmware" / "protocol"
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "protocol_demo"
            subprocess.run(
                [
                    "gcc",
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(protocol / "sentinel_wire_protocol.c"),
                    str(protocol / "protocol_demo.c"),
                    "-I",
                    str(protocol),
                    "-o",
                    str(executable),
                ],
                check=True,
            )
            actual = subprocess.check_output(
                [str(executable)], text=True
            ).strip()

        self.assertEqual(actual, expected)
        frames = FrameParser().feed(bytes.fromhex(actual))
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].message_type, TYPE_COMMAND)


if __name__ == "__main__":
    unittest.main()
