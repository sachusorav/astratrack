"""
ASTRATRACK — 3D Tracking Scenarios

Preconfigured simulation scenarios covering standard and challenging
FSOC tracking regimes:

Ground → Satellite (Mode A)
1. Stationary Beacon           — calibration baseline
2. Linear Flight Path          — constant velocity cross-track transit
3. Orbital Arc (LEO Pass)      — satellite overpass arc
4. Atmospheric Turbulence Jitter — stochastic beam wander & intensity fading
5. High-Speed Crossing         — hypersonic / low-altitude flyby
6. Evasive / Erratic Trajectory — high-g maneuvers, random-walk

Satellite ↔ Satellite (Mode B)
7. Sat → Ground Uplink         — downward-arc satellite one-directional beacon
8. ISL Same-Plane              — bilateral inter-satellite link, co-planar orbit
9. ISL Crosslink               — bilateral ISL, cross-plane, high angular rate
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from simulator.target3d import TargetConfig, TrajectoryType
from simulator.camera3d import CameraConfig3D


@dataclass
class Scenario:
    """Complete specification for a 3D tracking simulation scenario."""
    id: str
    name: str
    description: str
    category: str
    target_config: TargetConfig
    camera_config: CameraConfig3D
    sim_duration_sec: float = 60.0
    recommended_dt: float = 0.02   # 50 Hz
    metadata: Dict = field(default_factory=dict)


def get_scenario_stationary() -> Scenario:
    """Scenario 1: Stationary optical beacon (boresight calibration & static jitter test)."""
    target = TargetConfig(
        initial_position=np.array([100.0, 400.0, 600.0]),
        initial_velocity=np.zeros(3),
        acceleration=np.zeros(3),
        trajectory_type=TrajectoryType.STATIC,
        speed=0.0,
        noise_sigma=0.05,
        random_seed=42,
    )
    camera = CameraConfig3D(
        position=np.array([0.0, 0.0, 0.0]),
        initial_pan_deg=10.0,
        initial_tilt_deg=30.0,
        fov_deg=8.0,
        pan_limit_deg=170.0,
        tilt_limit_deg=85.0,
        tilt_min_deg=2.0,
        max_angular_velocity=35.0,
        inertia=0.85,
        tracking_gain=3.0,
        vibration_amplitude=0.02,
        vibration_frequency=8.0,
    )
    return Scenario(
        id="stationary",
        name="Stationary Beacon",
        description="Static beacon at 728m slant range for pointing alignment and noise baseline.",
        category="Calibration",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=30.0,
        metadata={"target_range_m": 728.0, "difficulty": "Nominal"}
    )


def get_scenario_linear() -> Scenario:
    """Scenario 2: Linear flight path (constant velocity transit across ground station)."""
    target = TargetConfig(
        initial_position=np.array([-500.0, 350.0, 400.0]),
        initial_velocity=np.array([35.0, 2.0, 10.0]),
        acceleration=np.zeros(3),
        trajectory_type=TrajectoryType.LINEAR,
        speed=37.0,
        noise_sigma=0.1,
        random_seed=101,
    )
    camera = CameraConfig3D(
        position=np.array([0.0, 0.0, 0.0]),
        initial_pan_deg=-45.0,
        initial_tilt_deg=25.0,
        fov_deg=7.5,
        max_angular_velocity=45.0,
        inertia=0.88,
        tracking_gain=2.8,
    )
    return Scenario(
        id="linear",
        name="Linear Flight Path",
        description="Steady cross-track UAV/aircraft transit at 37 m/s with constant heading.",
        category="Standard Transit",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=35.0,
        metadata={"target_speed_mps": 37.0, "difficulty": "Low"}
    )


def get_scenario_orbital() -> Scenario:
    """Scenario 3: Orbital arc (LEO satellite pass across elevation azimuth)."""
    target = TargetConfig(
        initial_position=np.array([-600.0, 250.0, 300.0]),
        trajectory_type=TrajectoryType.ORBITAL,
        speed=65.0,
        orbit_radius=450.0,
        orbit_center=np.array([0.0, 450.0, 500.0]),
        noise_sigma=0.08,
        random_seed=202,
    )
    camera = CameraConfig3D(
        position=np.array([0.0, 0.0, 0.0]),
        initial_pan_deg=-30.0,
        initial_tilt_deg=20.0,
        fov_deg=6.0,
        max_angular_velocity=50.0,
        inertia=0.85,
        tracking_gain=3.2,
    )
    return Scenario(
        id="orbital",
        name="Orbital Arc (LEO Pass)",
        description="Simulated satellite pass with changing elevation velocity and perspective acceleration.",
        category="Spacecraft Tracking",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=45.0,
        metadata={"orbit_radius_m": 450.0, "difficulty": "Medium"}
    )


def get_scenario_turbulence() -> Scenario:
    """Scenario 4: Atmospheric turbulence jitter (high beam wander and high frequency jitter)."""
    target = TargetConfig(
        initial_position=np.array([50.0, 320.0, 550.0]),
        trajectory_type=TrajectoryType.SINUSOIDAL,
        speed=20.0,
        amplitude=np.array([80.0, 35.0, 60.0]),
        frequency=np.array([0.25, 0.35, 0.2]),
        noise_sigma=3.2,  # Strong atmospheric perturbation
        random_seed=303,
    )
    camera = CameraConfig3D(
        position=np.array([0.0, 0.0, 0.0]),
        initial_pan_deg=5.0,
        initial_tilt_deg=28.0,
        fov_deg=8.0,
        max_angular_velocity=40.0,
        inertia=0.80,
        tracking_gain=3.5,
        vibration_amplitude=0.35,  # Mast vibration in high winds
        vibration_frequency=12.0,
    )
    return Scenario(
        id="turbulence",
        name="Atmospheric Turbulence Jitter",
        description="High scintillation and beam wander with optical turbulence (Cn2 = 1e-13 m^-2/3) and mount vibration.",
        category="Disturbance",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=30.0,
        metadata={"turbulence_level": "Strong", "difficulty": "High"}
    )


def get_scenario_high_speed() -> Scenario:
    """Scenario 5: High-speed crossing (hypersonic / near-zenith flyby with severe slew demand)."""
    target = TargetConfig(
        initial_position=np.array([-800.0, 200.0, 250.0]),
        initial_velocity=np.array([120.0, 15.0, 40.0]),
        acceleration=np.array([2.5, 0.0, -1.0]),
        trajectory_type=TrajectoryType.LINEAR,
        speed=128.0,
        noise_sigma=0.15,
        random_seed=404,
    )
    camera = CameraConfig3D(
        position=np.array([0.0, 0.0, 0.0]),
        initial_pan_deg=-70.0,
        initial_tilt_deg=12.0,
        fov_deg=6.5,
        max_angular_velocity=60.0,  # Fast gimbal required
        inertia=0.78,
        tracking_gain=4.2,
    )
    return Scenario(
        id="high_speed",
        name="High-Speed Crossing",
        description="Fast target crossing near ground station at 128+ m/s pushing gimbal slew limits.",
        category="Stress Test",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=20.0,
        metadata={"target_speed_mps": 128.0, "difficulty": "Critical"}
    )


def get_scenario_evasive() -> Scenario:
    """Scenario 6: Evasive / erratic trajectory (high-g switching maneuvers and random walk)."""
    target = TargetConfig(
        initial_position=np.array([0.0, 300.0, 450.0]),
        trajectory_type=TrajectoryType.FIGURE_EIGHT,
        speed=60.0,
        amplitude=np.array([240.0, 90.0, 140.0]),
        frequency=np.array([0.3, 0.45, 0.25]),
        noise_sigma=1.8,
        random_seed=505,
    )
    camera = CameraConfig3D(
        position=np.array([0.0, 0.0, 0.0]),
        initial_pan_deg=0.0,
        initial_tilt_deg=30.0,
        fov_deg=8.0,
        max_angular_velocity=55.0,
        inertia=0.82,
        tracking_gain=3.8,
        vibration_amplitude=0.08,
        vibration_frequency=6.0,
    )
    return Scenario(
        id="evasive",
        name="Evasive / Erratic Trajectory",
        description="Complex figure-eight kinematics with rapid directional reversal and stochastic noise.",
        category="Extreme Maneuver",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=40.0,
        metadata={"maneuver": "3D Figure-8 + Stochastic", "difficulty": "Severe"}
    )


def get_scenario_sat_to_ground() -> Scenario:
    """Scenario 7: Satellite-to-ground downlink beacon (one-directional uplink arc)."""
    target = TargetConfig(
        initial_position=np.array([800.0, 1200.0, 900.0]),
        initial_velocity=np.array([-30.0, -18.0, -40.0]),
        acceleration=np.array([0.0, -1.5, 0.0]),  # Descending arc
        trajectory_type=TrajectoryType.ORBITAL,
        speed=52.0,
        orbit_radius=700.0,
        orbit_center=np.array([0.0, 500.0, 400.0]),
        noise_sigma=0.06,
        random_seed=606,
    )
    camera = CameraConfig3D(
        position=np.array([0.0, 0.0, 0.0]),
        initial_pan_deg=40.0,
        initial_tilt_deg=55.0,
        fov_deg=5.0,
        pan_limit_deg=175.0,
        tilt_limit_deg=88.0,
        tilt_min_deg=5.0,
        max_angular_velocity=45.0,
        inertia=0.82,
        tracking_gain=3.4,
        vibration_amplitude=0.05,
        vibration_frequency=5.0,
    )
    return Scenario(
        id="sat_to_ground",
        name="Sat → Ground Uplink",
        description="Satellite beacon on descending arc broadcasting to ground optical terminal. High elevation, long range.",
        category="Satellite ↔ Satellite",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=50.0,
        metadata={"link_direction": "downlink", "difficulty": "Medium", "mode": "sat_to_sat"}
    )


def get_scenario_isl_same_plane() -> Scenario:
    """Scenario 8: Inter-Satellite Link (ISL), same orbital plane bilateral tracking."""
    target = TargetConfig(
        initial_position=np.array([-300.0, 800.0, 600.0]),
        trajectory_type=TrajectoryType.ORBITAL,
        speed=78.0,
        orbit_radius=550.0,
        orbit_center=np.array([0.0, 700.0, 500.0]),
        noise_sigma=0.04,
        random_seed=707,
    )
    camera = CameraConfig3D(
        # Ground-station position elevated to simulate second satellite
        position=np.array([0.0, 600.0, 0.0]),
        initial_pan_deg=-15.0,
        initial_tilt_deg=10.0,
        fov_deg=4.5,
        pan_limit_deg=180.0,
        tilt_limit_deg=90.0,
        tilt_min_deg=-30.0,  # Can point slightly below horizon (in space)
        max_angular_velocity=55.0,
        inertia=0.80,
        tracking_gain=3.6,
        vibration_amplitude=0.03,
        vibration_frequency=3.0,
    )
    return Scenario(
        id="isl_same_plane",
        name="ISL Same-Plane",
        description="Bilateral inter-satellite optical link between two co-planar LEO nodes. Stable relative geometry.",
        category="Satellite ↔ Satellite",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=55.0,
        metadata={"link_direction": "bilateral", "difficulty": "Medium", "mode": "sat_to_sat"}
    )


def get_scenario_isl_crosslink() -> Scenario:
    """Scenario 9: ISL Cross-plane crosslink — high angular rate due to orbital plane difference."""
    target = TargetConfig(
        initial_position=np.array([400.0, 900.0, -200.0]),
        trajectory_type=TrajectoryType.FIGURE_EIGHT,
        speed=95.0,
        amplitude=np.array([350.0, 80.0, 220.0]),
        frequency=np.array([0.18, 0.22, 0.15]),
        noise_sigma=0.12,
        random_seed=808,
    )
    camera = CameraConfig3D(
        position=np.array([0.0, 700.0, 0.0]),
        initial_pan_deg=25.0,
        initial_tilt_deg=8.0,
        fov_deg=5.5,
        pan_limit_deg=180.0,
        tilt_limit_deg=90.0,
        tilt_min_deg=-45.0,
        max_angular_velocity=65.0,
        inertia=0.76,
        tracking_gain=4.0,
        vibration_amplitude=0.04,
        vibration_frequency=4.0,
    )
    return Scenario(
        id="isl_crosslink",
        name="ISL Crosslink",
        description="Cross-plane inter-satellite link with high relative angular rate. Fast gimbal demand and pointing precision required.",
        category="Satellite ↔ Satellite",
        target_config=target,
        camera_config=camera,
        sim_duration_sec=45.0,
        metadata={"link_direction": "bilateral", "difficulty": "High", "mode": "sat_to_sat"}
    )


# ------------------------------------------------------------------ #
# Registry & Mode Hierarchy
# ------------------------------------------------------------------ #

SCENARIO_REGISTRY: Dict[str, Scenario] = {
    # Ground → Satellite (Mode A)
    "1": get_scenario_stationary(),
    "stationary": get_scenario_stationary(),
    "2": get_scenario_linear(),
    "linear": get_scenario_linear(),
    "3": get_scenario_orbital(),
    "orbital": get_scenario_orbital(),
    "4": get_scenario_turbulence(),
    "turbulence": get_scenario_turbulence(),
    "5": get_scenario_high_speed(),
    "high_speed": get_scenario_high_speed(),
    "6": get_scenario_evasive(),
    "evasive": get_scenario_evasive(),
    # Satellite ↔ Satellite (Mode B)
    "7": get_scenario_sat_to_ground(),
    "sat_to_ground": get_scenario_sat_to_ground(),
    "8": get_scenario_isl_same_plane(),
    "isl_same_plane": get_scenario_isl_same_plane(),
    "9": get_scenario_isl_crosslink(),
    "isl_crosslink": get_scenario_isl_crosslink(),
}

# Two-level mode hierarchy for on-screen control UI
MODE_GROUPS: Dict[str, List[str]] = {
    "ground_to_sat": ["stationary", "linear", "orbital", "turbulence", "high_speed", "evasive"],
    "sat_to_sat":    ["sat_to_ground", "isl_same_plane", "isl_crosslink"],
}

MODE_LABELS: Dict[str, str] = {
    "ground_to_sat": "Ground → Satellite",
    "sat_to_sat":    "Satellite ↔ Satellite",
}


def list_scenarios() -> List[Scenario]:
    """Return all available scenarios in display order (unique, no duplicates from alias keys)."""
    seen = set()
    result = []
    for s in SCENARIO_REGISTRY.values():
        if s.id not in seen:
            seen.add(s.id)
            result.append(s)
    return result


def list_scenarios_by_mode(mode: str) -> List[Scenario]:
    """Return scenarios belonging to a specific communication mode."""
    ids = MODE_GROUPS.get(mode, [])
    return [SCENARIO_REGISTRY[sid] for sid in ids if sid in SCENARIO_REGISTRY]


def get_scenario_mode(scenario_id: str) -> str:
    """Return the communication mode ('ground_to_sat' or 'sat_to_sat') for a scenario ID."""
    for mode, ids in MODE_GROUPS.items():
        if scenario_id in ids:
            return mode
    return "ground_to_sat"  # Default


def get_scenario_by_id_or_key(key: str) -> Optional[Scenario]:
    """Look up scenario by numeric key ('1'-'9') or scenario ID string."""
    if key in SCENARIO_REGISTRY:
        return SCENARIO_REGISTRY[key]
    # Fallback: search by id field
    for s in SCENARIO_REGISTRY.values():
        if s.id == key:
            return s
    return None
