"""
ASTRATRACK — Target Detection Benchmark Suite

Evaluates and compares ClassicalDetector and AIDetector across:
- Inference latency (mean, median, 95th percentile, min, max in ms)
- Processing throughput (FPS)
- Confidence metrics
- Detection success rate (%)
- Localization error (RMSE in pixels against ground truth)
"""

import sys
import os
import time
import math
import argparse
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# Ensure project root in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from perception.interface import IDetector, DetectionStatus
from perception.classical import ClassicalDetector
from perception.ai_detector import AIDetector


@dataclass
class GroundTruthSample:
    """A benchmark test frame with known ground truth target properties."""
    frame: np.ndarray
    gt_center: Optional[Tuple[float, float]]  # None for negative frames
    gt_radius: float
    scenario_type: str


@dataclass
class BenchmarkResult:
    """Consolidated benchmark metrics for a detector."""
    detector_name: str
    device: str
    total_frames: int
    successful_detections: int
    false_positives: int
    detection_rate_pct: float
    mean_confidence: float
    mean_inference_ms: float
    median_inference_ms: float
    p95_inference_ms: float
    fps: float
    localization_rmse_px: float


def generate_benchmark_dataset(num_samples: int = 100,
                               width: int = 640,
                               height: int = 480,
                               seed: int = 42) -> List[GroundTruthSample]:
    """
    Generate a standardized, reproducible dataset of camera frames.

    Includes:
    - Nominal optical beacons
    - Atmospheric turbulence & beam wander
    - Severe sensor noise & scintillation
    - Solar / cloud glare interference
    - Occlusions & blank negative frames
    """
    rng = np.random.RandomState(seed)
    samples: List[GroundTruthSample] = []

    for i in range(num_samples):
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # 10% blank frames (negative testing)
        if i % 10 == 0:
            # Add some background sensor noise
            noise = rng.normal(15, 5, frame.shape).astype(np.uint8)
            frame = cv2.add(frame, noise)
            samples.append(GroundTruthSample(frame, None, 0.0, "blank_negative"))
            continue

        # Target center with margin
        margin = 40
        cx = float(rng.uniform(margin, width - margin))
        cy = float(rng.uniform(margin, height - margin))
        radius = float(rng.uniform(4.0, 14.0))

        # Scenario distribution
        scen_type = "nominal"
        if i % 4 == 1:
            scen_type = "turbulence"
        elif i % 4 == 2:
            scen_type = "sensor_noise"
        elif i % 4 == 3:
            scen_type = "solar_glare"

        # Background sky gradient (dark twilight to navy)
        sky_val = rng.randint(8, 25)
        frame[:, :] = (sky_val, sky_val + 2, sky_val + 5)

        if scen_type == "solar_glare":
            # Add a diffuse bright patch elsewhere in the frame
            gx, gy = rng.randint(50, width - 50), rng.randint(50, height - 50)
            cv2.circle(frame, (gx, gy), rng.randint(40, 90), (120, 140, 160), -1)

        # Draw optical beacon (multi-ring glow)
        # BGR red/white optical beacon
        cv2.circle(frame, (int(cx), int(cy)), int(radius * 2.8), (40, 60, 200), -1)
        cv2.circle(frame, (int(cx), int(cy)), int(radius * 1.5), (80, 120, 240), -1)
        cv2.circle(frame, (int(cx), int(cy)), int(radius * 0.7), (200, 220, 255), -1)
        cv2.circle(frame, (int(cx), int(cy)), max(1, int(radius * 0.3)), (255, 255, 255), -1)

        if scen_type in ("turbulence", "sensor_noise"):
            # Add Gaussian noise
            sigma = 18.0 if scen_type == "sensor_noise" else 10.0
            noise = rng.normal(0, sigma, frame.shape).astype(np.int16)
            noisy = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            frame = noisy

        # Apply slight blur to simulate optical PSF
        frame = cv2.GaussianBlur(frame, (3, 3), 0)

        samples.append(GroundTruthSample(frame, (cx, cy), radius, scen_type))

    return samples


def benchmark_detector(detector: IDetector,
                       dataset: List[GroundTruthSample],
                       warmup_frames: int = 10) -> BenchmarkResult:
    """
    Run comprehensive benchmark on an IDetector instance.
    """
    # Warm up
    for _ in range(warmup_frames):
        detector.detect(dataset[0].frame)

    latencies_ms: List[float] = []
    confidences: List[float] = []
    localization_sq_errors: List[float] = []

    positives = [s for s in dataset if s.gt_center is not None]
    negatives = [s for s in dataset if s.gt_center is None]

    successful_detections = 0
    false_positives = 0

    for sample in dataset:
        t0 = time.perf_counter()
        result = detector.detect(sample.frame)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(dt_ms)

        if sample.gt_center is not None:
            # Positive frame
            if result.status == DetectionStatus.DETECTED and result.center is not None:
                successful_detections += 1
                confidences.append(result.confidence)

                # Error distance
                dx = result.center[0] - sample.gt_center[0]
                dy = result.center[1] - sample.gt_center[1]
                localization_sq_errors.append(dx * dx + dy * dy)
        else:
            # Negative frame
            if result.status == DetectionStatus.DETECTED:
                false_positives += 1

    total_pos = len(positives)
    det_rate = (successful_detections / max(1, total_pos)) * 100.0
    mean_conf = float(np.mean(confidences)) if confidences else 0.0

    mean_lat = float(np.mean(latencies_ms))
    median_lat = float(np.median(latencies_ms))
    p95_lat = float(np.percentile(latencies_ms, 95))
    fps = 1000.0 / max(1e-4, mean_lat)

    rmse = math.sqrt(float(np.mean(localization_sq_errors))) if localization_sq_errors else 0.0

    return BenchmarkResult(
        detector_name=detector.detector_name,
        device=detector.device,
        total_frames=len(dataset),
        successful_detections=successful_detections,
        false_positives=false_positives,
        detection_rate_pct=det_rate,
        mean_confidence=mean_conf,
        mean_inference_ms=mean_lat,
        median_inference_ms=median_lat,
        p95_inference_ms=p95_lat,
        fps=fps,
        localization_rmse_px=rmse
    )


def print_benchmark_table(results: List[BenchmarkResult]):
    """Print formatted ASCII comparison table of benchmark results."""
    print("\n" + "=" * 88)
    print("                      ASTRATRACK DETECTION BENCHMARK REPORT")
    print("=" * 88)
    header = (
        f"{'Detector Name':<28} | {'Device':<6} | {'Success Rate':<12} | "
        f"{'Latency (ms)':<14} | {'FPS':<8} | {'Conf':<6} | {'RMSE (px)':<9}"
    )
    print(header)
    print("-" * 88)

    for r in results:
        lat_str = f"{r.mean_inference_ms:.2f} (p95: {r.p95_inference_ms:.1f})"
        row = (
            f"{r.detector_name:<28} | {r.device:<6} | {r.detection_rate_pct:>10.1f}% | "
            f"{lat_str:<14} | {r.fps:>8.1f} | {r.mean_confidence:>6.2f} | {r.localization_rmse_px:>9.2f}"
        )
        print(row)
    print("=" * 88 + "\n")


def main():
    parser = argparse.ArgumentParser(description="ASTRATRACK Detection Benchmark")
    parser.add_argument("--frames", type=int, default=100, help="Number of benchmark test frames")
    parser.add_argument("--detector", type=str, default="both",
                        choices=["classical", "ai", "both"], help="Detector to evaluate")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold")
    args = parser.parse_args()

    print(f"[*] Generating {args.frames} synthetic test frames...")
    dataset = generate_benchmark_dataset(num_samples=args.frames)

    detectors: List[IDetector] = []
    if args.detector in ("classical", "both"):
        detectors.append(ClassicalDetector(confidence_threshold=args.conf))
    if args.detector in ("ai", "both"):
        detectors.append(AIDetector(confidence_threshold=args.conf))

    results: List[BenchmarkResult] = []
    for d in detectors:
        print(f"[*] Benchmarking: {d.detector_name} on {d.device.upper()}...")
        res = benchmark_detector(d, dataset)
        results.append(res)

    print_benchmark_table(results)


if __name__ == "__main__":
    main()
