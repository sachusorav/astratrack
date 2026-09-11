"""
ASTRATRACK — Detector Factory

Provides unified creation and swapping between ClassicalDetector and AIDetector.
"""

from typing import Optional, Union, Dict, Any
from perception.interface import IDetector
from perception.classical import ClassicalDetector
from perception.ai_detector import AIDetector


def create_detector(detector_type: str = "classical",
                    confidence_threshold: float = 0.35,
                    device: str = "auto",
                    model_path: Optional[str] = None,
                    **kwargs) -> IDetector:
    """
    Factory function to instantiate any detector implementation.

    Args:
        detector_type: 'classical', 'ai' (or 'yolo').
        confidence_threshold: Minimum detection confidence (0.0 - 1.0).
        device: 'cpu', 'cuda', or 'auto'.
        model_path: Optional path to ONNX model weights (for AI detector).
        kwargs: Additional arguments passed to specific detector constructors.

    Returns:
        Instance implementing the IDetector interface.
    """
    dtype = detector_type.lower().strip()

    if dtype in ("ai", "yolo", "yolov8", "yolov5"):
        return AIDetector(
            model_path=model_path,
            confidence_threshold=confidence_threshold,
            device=device,
            **kwargs
        )
    elif dtype in ("classical", "cv", "hsv", "baseline"):
        return ClassicalDetector(
            confidence_threshold=confidence_threshold,
            device=device,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown detector_type '{detector_type}'. Supported: 'classical', 'ai'")
