from pathlib import Path
import math
import unittest

import yaml

from training.end_to_end.contract import (
    DEFAULT_BEV_CHANNELS,
    EndToEndObservationSpec,
    VelocityLimits,
    decode_normalized_action,
    validate_low_dim_state,
    validate_normalized_action,
)


ROOT = Path(__file__).resolve().parents[1]


class EndToEndContractTests(unittest.TestCase):
    def test_default_observation_shape(self):
        spec = EndToEndObservationSpec()
        spec.validate()
        self.assertEqual(spec.height, 128)
        self.assertEqual(spec.width, 128)
        self.assertEqual(len(DEFAULT_BEV_CHANNELS), 6)
        self.assertEqual(spec.bev_values, 6 * 128 * 128)

    def test_state_contract(self):
        state = validate_low_dim_state([0.2, -0.1, 0.3, 2.0, -1.0])
        self.assertEqual(len(state), 5)
        with self.assertRaises(ValueError):
            validate_low_dim_state([0.0] * 4)
        with self.assertRaises(ValueError):
            validate_low_dim_state([0.0, 0.0, math.nan, 0.0, 0.0])

    def test_action_is_clamped_before_scaling(self):
        limits = VelocityLimits(2.0, 1.5, 3.0)
        action = decode_normalized_action([2.0, -2.0, 0.5], limits)
        self.assertEqual(action.as_tuple(), (2.0, -1.5, 1.5))

    def test_limits_are_mandatory_and_validated(self):
        with self.assertRaises(ValueError):
            decode_normalized_action(
                [0.0, 0.0, 0.0],
                VelocityLimits(0.0, 1.0, 1.0),
            )
        with self.assertRaises(ValueError):
            validate_normalized_action([0.0, 0.0])
        with self.assertRaises(ValueError):
            validate_normalized_action([0.0, math.inf, 0.0])

    def test_ros_interface_is_registered(self):
        msg_path = (
            ROOT
            / "ros2_ws"
            / "src"
            / "sentinel_interfaces"
            / "msg"
            / "EndToEndObservation.msg"
        )
        self.assertTrue(msg_path.is_file())
        cmake = (
            ROOT
            / "ros2_ws"
            / "src"
            / "sentinel_interfaces"
            / "CMakeLists.txt"
        ).read_text(encoding="utf-8")
        self.assertIn('"msg/EndToEndObservation.msg"', cmake)

    def test_topic_contract_keeps_learning_output_behind_safety(self):
        topics = yaml.safe_load(
            (ROOT / "config" / "interfaces" / "ros_topics.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            topics["learning"]["e2e_observation"]["topic"],
            "/sentry/e2e/observation",
        )
        self.assertEqual(
            topics["learning"]["e2e_command"]["topic"],
            "/sentry/e2e/cmd_vel_raw",
        )
        self.assertEqual(
            topics["commands"]["safe_chassis"]["owner"],
            "safety_supervisor_only",
        )
        self.assertNotEqual(
            topics["learning"]["e2e_command"]["topic"],
            topics["commands"]["safe_chassis"]["topic"],
        )


if __name__ == "__main__":
    unittest.main()
