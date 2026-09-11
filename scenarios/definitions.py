"""
ASTRATRACK — Scenario Lab Definitions

Provides the 10 standard aerospace scenarios:
01 — BASELINE
02 — HIGH SPEED TARGET
03 — TARGET ACCELERATION
04 — CAMERA VIBRATION
05 — IMAGE NOISE
06 — TURBULENCE
07 — TEMPORARY OCCLUSION
08 — TARGET LOSS
09 — COMBINED DISTURBANCE
10 — EXTREME STRESS TEST

Each scenario defines:
- target trajectory
- camera behavior
- disturbance parameters
- expected challenge
- evaluation metrics
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ScenarioDefinition:
    """Complete specification for an ASTRATRACK simulation scenario."""
    id: str                       # e.g. "01", "02", ...
    name: str                     # e.g. "BASELINE"
    difficulty: str               # "NOMINAL", "MEDIUM", "HARD", "SEVERE", "EXTREME"
    description: str              # Operational description
    expected_challenge: str       # Physical / optical challenge being evaluated

    # Configuration dictionaries
    target_config: Dict[str, Any]
    camera_config: Dict[str, Any]
    disturbance_config: Dict[str, Any]
    evaluation_criteria: Dict[str, Any] = field(default_factory=dict)


def get_standard_scenarios() -> Dict[str, ScenarioDefinition]:
    """Return dictionary of the 10 standard aerospace scenarios keyed by ID."""
    return {
        "01": ScenarioDefinition(
            id="01",
            name="BASELINE",
            difficulty="NOMINAL",
            description="Smooth sinusoidal trajectory under nominal sensor conditions. Establishes baseline calibration.",
            expected_challenge="Establish boresight alignment within 0.5s and maintain steady tracking with RMS error < 2.0 px.",
            target_config={
                "motion_model": "sinusoidal",
                "speed": 100.0,
                "radius": 12,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 8.0,
                "inertia": 0.85,
            },
            disturbance_config={"preset": "NORMAL"},
            evaluation_criteria={
                "min_lock_retention_pct": 98.0,
                "max_rms_error_px": 2.0,
                "max_acquisition_time_s": 0.5,
            }
        ),
        "02": ScenarioDefinition(
            id="02",
            name="HIGH SPEED TARGET",
            difficulty="MEDIUM",
            description="Rapid linear diagonal crossing simulating a low-earth orbit (LEO) satellite pass or high-speed aerial vehicle.",
            expected_challenge="Gimbal slew rate saturation and velocity feedforward lag compensation.",
            target_config={
                "motion_model": "linear",
                "speed": 320.0,
                "radius": 12,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 14.0,
                "inertia": 0.80,
            },
            disturbance_config={"preset": "NORMAL"},
            evaluation_criteria={
                "min_lock_retention_pct": 90.0,
                "max_rms_error_px": 10.0,
                "max_latency_error_px": 12.0,
            }
        ),
        "03": ScenarioDefinition(
            id="03",
            name="TARGET ACCELERATION",
            difficulty="HARD",
            description="Maneuvering target with sudden multi-G acceleration bursts and abrupt heading reversals.",
            expected_challenge="Overcoming acceleration lag and damping transient overshoots during sharp directional turns.",
            target_config={
                "motion_model": "random_walk",
                "speed": 180.0,
                "radius": 12,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 12.0,
                "inertia": 0.82,
            },
            disturbance_config={
                "preset": "NORMAL",
                "channels": {
                    "target_acceleration": {"enabled": True, "intensity": 150.0, "frequency": 0.5},
                    "target_angular_motion": {"enabled": True, "intensity": 0.8, "frequency": 1.0},
                }
            },
            evaluation_criteria={
                "min_lock_retention_pct": 88.0,
                "max_rms_error_px": 12.0,
                "max_error_px": 30.0,
            }
        ),
        "04": ScenarioDefinition(
            id="04",
            name="CAMERA VIBRATION",
            difficulty="MEDIUM",
            description="Simulates platform mechanical vibration from ship propulsion resonance or UAV rotor downwash.",
            expected_challenge="Damping multi-harmonic optical jitter and preventing controller hunting.",
            target_config={
                "motion_model": "linear",
                "speed": 100.0,
                "radius": 12,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 10.0,
                "inertia": 0.85,
            },
            disturbance_config={
                "preset": "NORMAL",
                "channels": {
                    "camera_vibration": {"enabled": True, "intensity": 1.4, "frequency": 6.0},
                    "platform_jitter": {"enabled": True, "intensity": 1.8, "frequency": 12.0},
                }
            },
            evaluation_criteria={
                "min_lock_retention_pct": 92.0,
                "max_rms_error_px": 8.0,
            }
        ),
        "05": ScenarioDefinition(
            id="05",
            name="IMAGE NOISE",
            difficulty="HARD",
            description="Severe low-light and thermal detector degradation with dense Gaussian and salt-and-pepper noise.",
            expected_challenge="Extracting true optical centroid amidst background false alarms and noisy pixel fluctuations.",
            target_config={
                "motion_model": "orbital",
                "speed": 120.0,
                "radius": 10,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 8.0,
                "inertia": 0.85,
            },
            disturbance_config={
                "preset": "NORMAL",
                "channels": {
                    "image_noise": {"enabled": True, "intensity": 35.0},
                }
            },
            evaluation_criteria={
                "min_lock_retention_pct": 85.0,
                "min_detection_rate_pct": 90.0,
                "max_rms_error_px": 10.0,
            }
        ),
        "06": ScenarioDefinition(
            id="06",
            name="TURBULENCE",
            difficulty="HARD",
            description="Strong atmospheric boundary layer turbulence inducing dynamic Kolmogorov wavefront tilt and beam wander.",
            expected_challenge="Optical centroid displacement warping and beam wander filtered by state estimation.",
            target_config={
                "motion_model": "sinusoidal",
                "speed": 90.0,
                "radius": 12,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 8.0,
                "inertia": 0.88,
            },
            disturbance_config={
                "preset": "NORMAL",
                "channels": {
                    "turbulence": {"enabled": True, "intensity": 6.0, "frequency": 2.5},
                }
            },
            evaluation_criteria={
                "min_lock_retention_pct": 88.0,
                "max_rms_error_px": 9.0,
            }
        ),
        "07": ScenarioDefinition(
            id="07",
            name="TEMPORARY OCCLUSION",
            difficulty="HARD",
            description="Periodic line-of-sight blockage simulating passing clouds, antenna masts, or structural struts.",
            expected_challenge="Dead-reckoning coasting during signal blackout and seamless re-acquisition upon clearing.",
            target_config={
                "motion_model": "linear",
                "speed": 110.0,
                "radius": 12,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 8.0,
                "inertia": 0.85,
            },
            disturbance_config={
                "preset": "NORMAL",
                "channels": {
                    "target_occlusion": {"enabled": True, "intensity": 0.95, "duration": 2.0, "start_delay": 3.0},
                }
            },
            evaluation_criteria={
                "min_lock_retention_pct": 75.0,
                "max_recovery_time_s": 0.8,
            }
        ),
        "08": ScenarioDefinition(
            id="08",
            name="TARGET LOSS",
            difficulty="SEVERE",
            description="Deep atmospheric scintillation fade and high-speed breakout causing target loss outside boresight.",
            expected_challenge="Triggering TARGET_LOST, dead-reckoning prediction, and executing expanding spiral re-acquisition.",
            target_config={
                "motion_model": "orbital",
                "speed": 220.0,
                "radius": 10,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 10.0,
                "inertia": 0.85,
            },
            disturbance_config={
                "preset": "NORMAL",
                "channels": {
                    "random_target_loss": {"enabled": True, "intensity": 0.4, "frequency": 0.15},
                    "brightness_variation": {"enabled": True, "intensity": 0.6, "frequency": 2.0},
                }
            },
            evaluation_criteria={
                "min_recoveries_count": 1,
                "max_recovery_time_s": 1.5,
            }
        ),
        "09": ScenarioDefinition(
            id="09",
            name="COMBINED DISTURBANCE",
            difficulty="SEVERE",
            description="Multi-domain operational aerospace stress: turbulence, platform vibration, sensor noise, and target maneuvers.",
            expected_challenge="Simultaneous rejection of multi-physics perturbations across spatial and optical domains.",
            target_config={
                "motion_model": "sinusoidal",
                "speed": 150.0,
                "radius": 12,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 10.0,
                "inertia": 0.85,
            },
            disturbance_config={"preset": "MODERATE DISTURBANCE"},
            evaluation_criteria={
                "min_lock_retention_pct": 82.0,
                "max_rms_error_px": 10.0,
            }
        ),
        "10": ScenarioDefinition(
            id="10",
            name="EXTREME STRESS TEST",
            difficulty="EXTREME",
            description="Boundary stress test: high-G turns, extreme turbulence, violent vibration, dense noise, and prolonged dropouts.",
            expected_challenge="System survivability, zero-crash execution, and rapid re-acquisition under worst-case parameters.",
            target_config={
                "motion_model": "random_walk",
                "speed": 260.0,
                "radius": 10,
            },
            camera_config={
                "fov_width": 640,
                "fov_height": 480,
                "max_slew_rate": 16.0,
                "inertia": 0.80,
            },
            disturbance_config={"preset": "EXTREME STRESS TEST"},
            evaluation_criteria={
                "min_lock_retention_pct": 60.0,
                "max_recovery_time_s": 2.0,
            }
        ),
    }
