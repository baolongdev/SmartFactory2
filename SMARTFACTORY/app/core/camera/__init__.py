"""
Camera processing package v1.0

Provides modules for:
- Camera capture with threading
- Color object definitions (HSV/BGR)
- Color detection using HSV thresholds
- Object tracking with IDs and trajectory
- Drawing bounding boxes, labels, and trajectories
- Full pipeline integration
"""

from .camera_reader import CameraReader
from .color_object import ColorObject
from .color_detector import ColorDetector
from .tracker import Tracker
from .draw_manager import DrawManager
from .pipeline import CameraPipeline

__all__ = [
    "CameraReader",
    "ColorObject",
    "ColorDetector",
    "Tracker",
    "DrawManager",
    "CameraPipeline",
]
