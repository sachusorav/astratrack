"""
ASTRATRACK — State Estimation & Prediction Benchmark Suite

Rigorous quantitative comparison across:
1. Detection-Only Tracking (raw measurements)
2. Filtered Tracking (Kalman Filter ON, Prediction OFF)
3. Predictive Tracking (Kalman Filter ON, Prediction ON)

Evaluates:
- Position Tracking RMSE against ground truth
- Velocity Estimation RMSE
- Latency-Compensated Error RMSE (simulating 2-frame actuation delay)
- Noise Attenuation Ratio
- Occlusion / Dropout Survival Error
- Tracking Stability (%)
"""

import sys
import os
import time
import math
import argparse
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# Ensure workspace root in path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from core.config import KalmanConfig
from estimation.kalman import KalmanTracker, TrackingMode, TrackState
from estimation.predictor import MotionPredictor


@dataclass
class EstimationBenchmarkMetrics:
    """Benchmark results for a specific tracking paradigm."""
    mode_name: str
    prediction_enabled: bool
    position_rmse_px: float
    velocity_rmse_px: float
    latency_error_rmse_px: float
    noise_attenuation_ratio: float
    occlusion_mean_error_px: float
    lock_stability_pct: float
    mean_update_us: float


def run_estimation_benchmark(num_steps: int = 500,
                             dt: float = 0.02,
                             noise_sigma: float = 6.0,
                             occlusion_start: int = 200,
                             occlusion_len: int = 25,
                             latency_frames: int = 2,
                             seed: int = 42) -> List[EstimationBenchmarkMetrics]:
    """
    Execute standardized dynamic simulation comparing all three tracking modes.

    Trajectory: Harmonic sine-wave flight path with varying acceleration.
    """
    rng = np.random.RandomState(seed)

    # 1. Generate Ground Truth Kinematics
    t = np.arange(num_steps) * dt
    # Complex 2D path: UAV crossing with oscillation
    gt_x = 320.0 + 80.0 * np.sin(0.4 * t) + 12.0 * t
    gt_y = 240.0 + 50.0 * np.cos(0.5 * t) - 4.0 * t
    gt_vx = 32.0 * np.cos(0.4 * t) + 12.0
    gt_vy = -25.0 * np.sin(0.5 * t) - 4.0

    # 2. Generate Noisy Detections with Occlusion Window
    measurements: List[Optional[Tuple[float, float]]] = []
    for i in range(num_steps):
        # Occlusion window
        if occlusion_start <= i < (occlusion_start + occlusion_len):
            measurements.append(None)
        else:
            mx = gt_x[i] + rng.normal(0, noise_sigma)
            my = gt_y[i] + rng.normal(0, noise_sigma)
            measurements.append((mx, my))

    # Mock Detection class
    class MockDetection:
        def __init__(self, pos):
            self.x, self.y = pos
            self.confidence = 0.95

    # 3. Test Configurations
    test_modes = [
        ("Detection-Only Tracking", TrackingMode.DETECTION_ONLY, False),
        ("Filtered Tracking (Pred OFF)", TrackingMode.FILTERED, False),
        ("Predictive Tracking (Pred ON)", TrackingMode.PREDICTIVE, True),
    ]

    results: List[EstimationBenchmarkMetrics] = []

    for name, mode, pred_toggle in test_modes:
        cfg = KalmanConfig(
            process_noise=1.5,
            measurement_noise=noise_sigma ** 2,
            initial_covariance=10.0,
            coast_limit=60,
            prediction_horizon=latency_frames
        )
        tracker = KalmanTracker(
            config=cfg,
            prediction_enabled=pred_toggle,
            prediction_horizon=latency_frames
        )
        tracker.set_tracking_mode(mode)

        pos_sq_errs = []
        vel_sq_errs = []
        latency_sq_errs = []
        occlusion_errs = []
        latencies_us = []
        locked_count = 0

        last_raw = None
        for i in range(num_steps):
            meas = measurements[i]
            det = MockDetection(meas) if meas is not None else None

            t0 = time.perf_counter()
            state = tracker.update(det, dt=dt)
            dt_us = (time.perf_counter() - t0) * 1e6
            latencies_us.append(dt_us)

            # Ground truth for current time
            gx, gy = gt_x[i], gt_y[i]
            gvx, gvy = gt_vx[i], gt_vy[i]

            # Tracking output coordinate used by gimbal control
            if mode == TrackingMode.DETECTION_ONLY:
                if meas is not None:
                    tracked_x, tracked_y = meas
                    if last_raw is not None:
                        calc_vx = (meas[0] - last_raw[0]) / dt
                        calc_vy = (meas[1] - last_raw[1]) / dt
                    else:
                        calc_vx, calc_vy = 0.0, 0.0
                    last_raw = meas
                else:
                    tracked_x, tracked_y = (last_raw if last_raw is not None else tracker.fov_center)
                    calc_vx, calc_vy = 0.0, 0.0
            elif mode == TrackingMode.FILTERED:
                tracked_x, tracked_y = state.estimated_pos
                calc_vx, calc_vy = state.estimated_vel
            else:  # PREDICTIVE
                tracked_x, tracked_y = state.predicted_pos
                calc_vx, calc_vy = state.estimated_vel

            # Position Error vs Ground Truth at current time
            err_dist = math.sqrt((tracked_x - gx) ** 2 + (tracked_y - gy) ** 2)
            pos_sq_errs.append(err_dist ** 2)

            # Velocity Error vs Ground Truth velocity
            vel_err = math.sqrt((calc_vx - gvx) ** 2 + (calc_vy - gvy) ** 2)
            vel_sq_errs.append(vel_err ** 2)

            # Latency-compensated error:
            # Control action at time i will hit target at time i + latency_frames!
            target_future_idx = min(num_steps - 1, i + latency_frames)
            future_gx, future_gy = gt_x[target_future_idx], gt_y[target_future_idx]
            lat_err = math.sqrt((tracked_x - future_gx) ** 2 + (tracked_y - future_gy) ** 2)
            latency_sq_errs.append(lat_err ** 2)

            # Occlusion error
            if occlusion_start <= i < (occlusion_start + occlusion_len):
                occlusion_errs.append(err_dist)

            # Lock stability (within 20px of true position)
            if err_dist < 20.0:
                locked_count += 1

        pos_rmse = math.sqrt(float(np.mean(pos_sq_errs)))
        vel_rmse = math.sqrt(float(np.mean(vel_sq_errs)))
        lat_rmse = math.sqrt(float(np.mean(latency_sq_errs)))
        noise_ratio = pos_rmse / max(1e-4, noise_sigma)
        occ_mean = float(np.mean(occlusion_errs)) if occlusion_errs else 0.0
        stability = (locked_count / num_steps) * 100.0
        mean_us = float(np.mean(latencies_us))

        results.append(EstimationBenchmarkMetrics(
            mode_name=name,
            prediction_enabled=pred_toggle,
            position_rmse_px=pos_rmse,
            velocity_rmse_px=vel_rmse,
            latency_error_rmse_px=lat_rmse,
            noise_attenuation_ratio=noise_ratio,
            occlusion_mean_error_px=occ_mean,
            lock_stability_pct=stability,
            mean_update_us=mean_us
        ))

    return results


def print_estimation_benchmark_table(results: List[EstimationBenchmarkMetrics]):
    """Print formatted ASCII report comparing tracking modes."""
    print("\n" + "=" * 96)
    print("                ASTRATRACK STATE ESTIMATION & PREDICTION BENCHMARK")
    print("=" * 96)
    header = (
        f"{'Tracking Mode':<30} | {'Pos RMSE':<9} | {'Vel RMSE':<9} | "
        f"{'Latency RMSE':<12} | {'Noise Ratio':<11} | {'Occ Error':<10} | {'Stability':<9}"
    )
    print(header)
    print("-" * 96)

    for r in results:
        row = (
            f"{r.mode_name:<30} | {r.position_rmse_px:>7.2f} px | {r.velocity_rmse_px:>7.2f} px | "
            f"{r.latency_error_rmse_px:>9.2f} px | {r.noise_attenuation_ratio:>11.2f} | "
            f"{r.occlusion_mean_error_px:>8.2f} px | {r.lock_stability_pct:>8.1f}%"
        )
        print(row)
    print("=" * 96)
    print("  * Latency RMSE: Error when compensating for 2-frame actuation delay.")
    print("  * Occ Error: Mean tracking drift during a 25-frame measurement blackout.")
    print("  * Noise Ratio: Position RMSE / Measurement Noise (lower is better, <1.0 = filtered).\n")


def main():
    parser = argparse.ArgumentParser(description="ASTRATRACK Estimation Benchmark")
    parser.add_argument("--steps", type=int, default=500, help="Simulation steps")
    parser.add_argument("--noise", type=float, default=6.0, help="Sensor noise sigma (pixels)")
    parser.add_argument("--latency", type=int, default=2, help="Actuation latency (frames)")
    args = parser.parse_args()

    print(f"[*] Running Estimation Benchmark ({args.steps} steps, noise={args.noise}px, latency={args.latency} frames)...")
    results = run_estimation_benchmark(
        num_steps=args.steps,
        noise_sigma=args.noise,
        latency_frames=args.latency
    )
    print_estimation_benchmark_table(results)


if __name__ == "__main__":
    main()
