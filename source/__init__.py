"""
Photo-Timestamper - 照片时间戳水印工具
"""

__version__ = "1.0.0"
__author__ = "Your Name"

from .core import (
    ConfigManager,
    StyleManager,
    ImageProcessor,
    BatchProcessor,
    TimeExtractor,
    WatermarkRenderer,
    process_single_image,
    scan_images
)

from .ui import MainWindow, run_app

__all__ = [
    'ConfigManager',
    'StyleManager',
    'ImageProcessor',
    'BatchProcessor',
    'TimeExtractor',
    'WatermarkRenderer',
    'process_single_image',
    'scan_images',
    'MainWindow',
    'run_app',
]