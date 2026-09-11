"""
ASTRATRACK — Target Perception Package
"""

from perception.interface import (
    IDetector, DetectionResult, DetectionStatus, BoundingBox
)
from perception.classical import ClassicalDetector
from perception.ai_detector import AIDetector
from perception.detector import BeaconDetector
from perception.factory import create_detector
from perception.preprocessing import preprocess

__all__ = [
    "IDetector",
    "DetectionResult",
    "DetectionStatus",
    "BoundingBox",
    "ClassicalDetector",
    "AIDetector",
    "BeaconDetector",
    "create_detector",
    "preprocess",
]
