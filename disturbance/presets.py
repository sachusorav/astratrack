"""
ASTRATRACK — Disturbance Presets

Defines standard engineering presets for algorithm robustness evaluation:
- NORMAL
- LIGHT DISTURBANCE
- MODERATE DISTURBANCE
- SEVERE DISTURBANCE
- EXTREME STRESS TEST
"""

from typing import Dict
from disturbance.channel import DisturbanceChannelConfig


def get_preset_channels(preset_name: str) -> Dict[str, DisturbanceChannelConfig]:
    """
    Return dictionary of 10 configured disturbance channels for a named preset.

    Channel keys:
    'image_noise', 'camera_vibration', 'platform_jitter', 'target_acceleration',
    'target_angular_motion', 'turbulence', 'temporary_blur', 'brightness_variation',
    'target_occlusion', 'random_target_loss'
    """
    p = preset_name.upper().replace("-", "_").replace(" ", "_")

    if p in ("NORMAL", "EASY", "OFF"):
        return {
            "image_noise": DisturbanceChannelConfig("image_noise", enabled=True, intensity=3.0),
            "camera_vibration": DisturbanceChannelConfig("camera_vibration", enabled=False, intensity=0.0),
            "platform_jitter": DisturbanceChannelConfig("platform_jitter", enabled=False, intensity=0.0),
            "target_acceleration": DisturbanceChannelConfig("target_acceleration", enabled=False, intensity=0.0),
            "target_angular_motion": DisturbanceChannelConfig("target_angular_motion", enabled=False, intensity=0.0),
            "turbulence": DisturbanceChannelConfig("turbulence", enabled=False, intensity=0.0),
            "temporary_blur": DisturbanceChannelConfig("temporary_blur", enabled=False, intensity=0.0),
            "brightness_variation": DisturbanceChannelConfig("brightness_variation", enabled=False, intensity=0.0),
            "target_occlusion": DisturbanceChannelConfig("target_occlusion", enabled=False, intensity=0.0),
            "random_target_loss": DisturbanceChannelConfig("random_target_loss", enabled=False, intensity=0.0),
        }

    elif p in ("LIGHT", "LIGHT_DISTURBANCE"):
        return {
            "image_noise": DisturbanceChannelConfig("image_noise", enabled=True, intensity=8.0),
            "camera_vibration": DisturbanceChannelConfig("camera_vibration", enabled=True, intensity=0.2, frequency=4.0),
            "platform_jitter": DisturbanceChannelConfig("platform_jitter", enabled=True, intensity=0.4, frequency=8.0),
            "target_acceleration": DisturbanceChannelConfig("target_acceleration", enabled=False, intensity=0.0),
            "target_angular_motion": DisturbanceChannelConfig("target_angular_motion", enabled=True, intensity=0.1, frequency=0.5),
            "turbulence": DisturbanceChannelConfig("turbulence", enabled=True, intensity=1.5, frequency=1.0),
            "temporary_blur": DisturbanceChannelConfig("temporary_blur", enabled=False, intensity=0.0),
            "brightness_variation": DisturbanceChannelConfig("brightness_variation", enabled=True, intensity=0.15, frequency=1.5),
            "target_occlusion": DisturbanceChannelConfig("target_occlusion", enabled=False, intensity=0.0),
            "random_target_loss": DisturbanceChannelConfig("random_target_loss", enabled=False, intensity=0.0),
        }

    elif p in ("MODERATE", "MODERATE_DISTURBANCE"):
        return {
            "image_noise": DisturbanceChannelConfig("image_noise", enabled=True, intensity=18.0),
            "camera_vibration": DisturbanceChannelConfig("camera_vibration", enabled=True, intensity=0.6, frequency=6.0),
            "platform_jitter": DisturbanceChannelConfig("platform_jitter", enabled=True, intensity=1.0, frequency=10.0),
            "target_acceleration": DisturbanceChannelConfig("target_acceleration", enabled=True, intensity=40.0, frequency=0.3),
            "target_angular_motion": DisturbanceChannelConfig("target_angular_motion", enabled=True, intensity=0.3, frequency=0.8),
            "turbulence": DisturbanceChannelConfig("turbulence", enabled=True, intensity=3.5, frequency=2.0),
            "temporary_blur": DisturbanceChannelConfig("temporary_blur", enabled=True, intensity=3.0, frequency=0.2),
            "brightness_variation": DisturbanceChannelConfig("brightness_variation", enabled=True, intensity=0.30, frequency=2.0),
            "target_occlusion": DisturbanceChannelConfig("target_occlusion", enabled=False, intensity=0.0),
            "random_target_loss": DisturbanceChannelConfig("random_target_loss", enabled=False, intensity=0.0),
        }

    elif p in ("SEVERE", "SEVERE_DISTURBANCE", "HARD"):
        return {
            "image_noise": DisturbanceChannelConfig("image_noise", enabled=True, intensity=28.0),
            "camera_vibration": DisturbanceChannelConfig("camera_vibration", enabled=True, intensity=1.2, frequency=8.0),
            "platform_jitter": DisturbanceChannelConfig("platform_jitter", enabled=True, intensity=2.0, frequency=12.0),
            "target_acceleration": DisturbanceChannelConfig("target_acceleration", enabled=True, intensity=100.0, frequency=0.4),
            "target_angular_motion": DisturbanceChannelConfig("target_angular_motion", enabled=True, intensity=0.6, frequency=1.0),
            "turbulence": DisturbanceChannelConfig("turbulence", enabled=True, intensity=6.0, frequency=3.0),
            "temporary_blur": DisturbanceChannelConfig("temporary_blur", enabled=True, intensity=6.0, frequency=0.3),
            "brightness_variation": DisturbanceChannelConfig("brightness_variation", enabled=True, intensity=0.50, frequency=3.0),
            "target_occlusion": DisturbanceChannelConfig("target_occlusion", enabled=True, intensity=0.7, duration=2.0, start_delay=5.0),
            "random_target_loss": DisturbanceChannelConfig("random_target_loss", enabled=False, intensity=0.0),
        }

    else:  # EXTREME_STRESS_TEST / EXTREME
        return {
            "image_noise": DisturbanceChannelConfig("image_noise", enabled=True, intensity=45.0),
            "camera_vibration": DisturbanceChannelConfig("camera_vibration", enabled=True, intensity=2.5, frequency=10.0),
            "platform_jitter": DisturbanceChannelConfig("platform_jitter", enabled=True, intensity=3.5, frequency=15.0),
            "target_acceleration": DisturbanceChannelConfig("target_acceleration", enabled=True, intensity=250.0, frequency=0.5),
            "target_angular_motion": DisturbanceChannelConfig("target_angular_motion", enabled=True, intensity=1.2, frequency=1.5),
            "turbulence": DisturbanceChannelConfig("turbulence", enabled=True, intensity=10.0, frequency=4.0),
            "temporary_blur": DisturbanceChannelConfig("temporary_blur", enabled=True, intensity=12.0, frequency=0.4),
            "brightness_variation": DisturbanceChannelConfig("brightness_variation", enabled=True, intensity=0.75, frequency=4.0),
            "target_occlusion": DisturbanceChannelConfig("target_occlusion", enabled=True, intensity=0.95, duration=3.0, start_delay=4.0),
            "random_target_loss": DisturbanceChannelConfig("random_target_loss", enabled=True, intensity=0.4, frequency=0.2),
        }


PRESET_NAMES = [
    "NORMAL",
    "LIGHT DISTURBANCE",
    "MODERATE DISTURBANCE",
    "SEVERE DISTURBANCE",
    "EXTREME STRESS TEST",
]
