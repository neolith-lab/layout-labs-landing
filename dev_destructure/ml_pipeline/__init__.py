"""
ML Pipeline for Infographic Layerization

Converts raster infographics to layered, editable formats using:
- SAM (Segment Anything) for segmentation
- CLIP for element classification
- LaMa for background inpainting
- PaddleOCR for text extraction
"""

from .config import (
    PipelineConfig,
    SAMConfig,
    CLIPConfig,
    LamaConfig,
    OCRConfig,
    OutputConfig,
    get_default_config,
    get_fast_config,
    get_quality_config,
)

from .data_structures import (
    BoundingBox,
    SegmentedElement,
    ClassifiedElement,
    TextElement,
    LayerElement,
    ProcessedInfographic,
)

from .pipeline import (
    InfographicLayerizer,
    process_infographic,
)

__version__ = "0.1.0"

__all__ = [
    # Config
    "PipelineConfig",
    "SAMConfig", 
    "CLIPConfig",
    "LamaConfig",
    "OCRConfig",
    "OutputConfig",
    "get_default_config",
    "get_fast_config",
    "get_quality_config",
    # Data structures
    "BoundingBox",
    "SegmentedElement",
    "ClassifiedElement",
    "TextElement",
    "LayerElement",
    "ProcessedInfographic",
    # Main API
    "InfographicLayerizer",
    "process_infographic",
]
