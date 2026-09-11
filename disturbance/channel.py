"""
ASTRATRACK — Disturbance Channel Configuration

Standardized channel descriptor for all 10 disturbance types:
- enable/disable toggle
- intensity
- frequency (Hz or recurrence rate)
- random seed (with independent PRNG stream)
- duration (active lifetime)
- start delay (activation offset)
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class DisturbanceChannelConfig:
    """
    Configuration for an individual disturbance channel.

    Note: These models are configurable engineering approximations
    for algorithm robustness testing, not physically exact atmospheric models.
    """
    name: str
    enabled: bool = False
    intensity: float = 0.0
    frequency: float = 1.0           # Hz or event rate
    seed: Optional[int] = None       # Specific seed or None (uses engine master seed)
    duration: float = float("inf")   # Active duration (seconds)
    start_delay: float = 0.0         # Activation delay (seconds)

    def is_active(self, current_time: float) -> bool:
        """Return True if this disturbance channel is currently active."""
        if not self.enabled or self.intensity <= 0.0:
            return False
        if current_time < self.start_delay:
            return False
        if current_time > (self.start_delay + self.duration):
            return False
        return True

    def get_rng(self, master_seed: Optional[int] = None) -> np.random.RandomState:
        """Get an isolated, deterministic RandomState for this channel."""
        effective_seed = self.seed if self.seed is not None else master_seed
        if effective_seed is not None:
            # Deterministically hash channel name + seed to prevent cross-channel correlation
            channel_hash = abs(hash(self.name)) % 100000
            return np.random.RandomState((effective_seed + channel_hash) % (2**31 - 1))
        return np.random.RandomState()
