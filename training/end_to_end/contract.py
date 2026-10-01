"""Dependency-light contract for end-to-end sentry training."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


SCHEMA_VERSION = 1
DEFAULT_BEV_HEIGHT = 128
DEFAULT_BEV_WIDTH = 128
DEFAULT_BEV_CHANNELS = (
    "obstacle",
    "free",
    "unknown",
    "enemy",
    "self",
    "goal",
)
LOW_DIM_STATE_FIELDS = (
    "vx_mps",
    "vy_mps",
    "wz_radps",
    "goal_dx_m",
    "goal_dy_m",
)
ACTION_FIELDS = ("vx_mps", "vy_mps", "wz_radps")


@dataclass(frozen=True, slots=True)
class EndToEndObservationSpec:
    height: int = DEFAULT_BEV_HEIGHT
    width: int = DEFAULT_BEV_WIDTH
    channels: tuple[str, ...] = DEFAULT_BEV_CHANNELS
    state_fields: tuple[str, ...] = LOW_DIM_STATE_FIELDS
    schema_version: int = SCHEMA_VERSION

    @property
    def bev_values(self) -> int:
        return self.height * self.width * len(self.channels)

    def validate(self) -> None:
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")
        if self.height <= 0 or self.width <= 0:
            raise ValueError("BEV dimensions must be positive")
        if not self.channels or len(set(self.channels)) != len(self.channels):
            raise ValueError("BEV channel names must be unique and non-empty")
        if not self.state_fields or len(set(self.state_fields)) != len(self.state_fields):
            raise ValueError("state field names must be unique and non-empty")


@dataclass(frozen=True, slots=True)
class VelocityLimits:
    """Physical action limits supplied by the validated chassis integration."""

    vx_abs_mps: float
    vy_abs_mps: float
    wz_abs_radps: float

    def validate(self) -> None:
        values = (self.vx_abs_mps, self.vy_abs_mps, self.wz_abs_radps)
        if not all(math.isfinite(value) and value > 0.0 for value in values):
            raise ValueError("all velocity limits must be finite and positive")


@dataclass(frozen=True, slots=True)
class EndToEndAction:
    vx_mps: float
    vy_mps: float
    wz_radps: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.vx_mps, self.vy_mps, self.wz_radps)


def _finite_tuple(values: Sequence[float], expected: int, name: str) -> tuple[float, ...]:
    if len(values) != expected:
        raise ValueError(f"{name} has {len(values)} values; expected {expected}")
    output = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in output):
        raise ValueError(f"{name} contains NaN or infinity")
    return output


def validate_low_dim_state(
    values: Sequence[float],
    *,
    spec: EndToEndObservationSpec = EndToEndObservationSpec(),
) -> tuple[float, ...]:
    spec.validate()
    return _finite_tuple(values, len(spec.state_fields), "state")


def validate_flat_bev(
    values: Sequence[float],
    *,
    spec: EndToEndObservationSpec = EndToEndObservationSpec(),
) -> tuple[float, ...]:
    spec.validate()
    return _finite_tuple(values, spec.bev_values, "bev")


def validate_normalized_action(values: Sequence[float]) -> tuple[float, float, float]:
    action = _finite_tuple(values, len(ACTION_FIELDS), "action")
    clamped = tuple(min(max(value, -1.0), 1.0) for value in action)
    return (clamped[0], clamped[1], clamped[2])


def decode_normalized_action(
    values: Sequence[float],
    limits: VelocityLimits,
) -> EndToEndAction:
    """Map normalized policy output [-1, 1] to SI chassis velocity.

    Limits are mandatory: the learning stack must not invent real robot limits.
    """

    limits.validate()
    vx, vy, wz = validate_normalized_action(values)
    return EndToEndAction(
        vx_mps=vx * limits.vx_abs_mps,
        vy_mps=vy * limits.vy_abs_mps,
        wz_radps=wz * limits.wz_abs_radps,
    )
