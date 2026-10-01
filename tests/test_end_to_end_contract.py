import math
import unittest

from training.end_to_end.contract import (
    DEFAULT_BEV_CHANNELS,
    EndToEndObservationSpec,
    VelocityLimits,
    decode_normalized_action,
    validate_low_dim_state,
    validate_normalized_action,
)


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


if __name__ == "__main__":
    unittest.main()
