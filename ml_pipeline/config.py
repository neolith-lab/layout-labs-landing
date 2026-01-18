"""
Configuration for ML-powered infographic layerization pipeline
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path


@dataclass
class SAMConfig:
    """Configuration for Segment Anything Model"""
    model_type: str = "vit_h"  # vit_h, vit_l, vit_b
    checkpoint_path: Optional[str] = None  # Auto-download if None
    points_per_side: int = 16  # For automatic mask generation
    pred_iou_thresh: float = 0.86
    stability_score_thresh: float = 0.92
    min_mask_region_area: int = 100  # Minimum pixels for a valid mask
    device: str = "auto"  # auto, cuda, mps, cpu


@dataclass
class CLIPConfig:
    """Configuration for CLIP classification"""
    model_name: str = "ViT-B/32"  # ViT-B/32, ViT-L/14, etc.
    
    # Categories for infographic elements
    categories: List[str] = field(default_factory=lambda: [
        "a logo or brand mark",
        "an icon or symbol", 
        "a photograph or realistic image",
        "an illustration or cartoon drawing",
        "a heading or title text",
        "body text or paragraph",
        "a button or clickable element",
        "a decorative shape or background element",
        "a card or container box",
        "a chart or graph or data visualization",
        "a screenshot or UI element",
        "an arrow or connector line",
    ])
    
    # Simplified category mapping for output
    category_mapping: Dict[str, str] = field(default_factory=lambda: {
        "a logo or brand mark": "logo",
        "an icon or symbol": "icon",
        "a photograph or realistic image": "photo",
        "an illustration or cartoon drawing": "illustration",
        "a heading or title text": "text_heading",
        "body text or paragraph": "text_body",
        "a button or clickable element": "button",
        "a decorative shape or background element": "shape",
        "a card or container box": "container",
        "a chart or graph or data visualization": "chart",
        "a screenshot or UI element": "screenshot",
        "an arrow or connector line": "connector",
    })
    
    device: str = "auto"


@dataclass 
class LamaConfig:
    """Configuration for LaMa inpainting"""
    model_path: Optional[str] = None  # Auto-download if None
    device: str = "auto"
    # Dilation of masks before inpainting (helps with edge artifacts)
    mask_dilation: int = 5


@dataclass
class OCRConfig:
    """Configuration for PaddleOCR"""
    lang: str = "en"
    use_angle_cls: bool = True
    # use_gpu is deprecated in newer PaddleOCR versions
    det_db_thresh: float = 0.3
    det_db_box_thresh: float = 0.5
    # rec_algorithm: str = "SVTR_LCNet"  # May not be available in all versions


@dataclass
class OutputConfig:
    """Configuration for output generation"""
    # Output formats to generate
    formats: List[str] = field(default_factory=lambda: ["svg", "psd", "json"])
    
    # SVG settings
    svg_embed_images: bool = True  # Embed raster as base64 or external files
    svg_vectorize_shapes: bool = True  # Convert simple shapes to vectors
    
    # Layer naming
    layer_prefix: str = "layer_"
    
    # Debug output
    save_debug: bool = True
    debug_dir: str = "./debug_output"


@dataclass
class PipelineConfig:
    """Main pipeline configuration"""
    sam: SAMConfig = field(default_factory=SAMConfig)
    clip: CLIPConfig = field(default_factory=CLIPConfig)
    lama: LamaConfig = field(default_factory=LamaConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    # Processing settings
    max_image_size: int = 2048  # Resize if larger (preserves aspect ratio)
    min_element_size: int = 20  # Minimum dimension for valid element
    merge_overlap_threshold: float = 0.7  # IoU threshold for merging masks
    
    # Layer ordering
    layer_order: List[str] = field(default_factory=lambda: [
        "background",
        "container",
        "photo", 
        "illustration",
        "chart",
        "screenshot",
        "shape",
        "icon",
        "logo",
        "connector",
        "button",
        "text_body",
        "text_heading",
    ])


def get_default_config() -> PipelineConfig:
    """Get default pipeline configuration"""
    return PipelineConfig()


def get_fast_config() -> PipelineConfig:
    """Get configuration optimized for speed"""
    config = PipelineConfig()
    config.sam.model_type = "vit_b"  # Smaller model
    config.sam.points_per_side = 16  # Fewer points
    config.clip.model_name = "ViT-B/32"  # Smaller CLIP
    return config


def get_quality_config() -> PipelineConfig:
    """Get configuration optimized for quality"""
    config = PipelineConfig()
    config.sam.model_type = "vit_h"  # Largest model
    config.sam.points_per_side = 64  # More points
    config.sam.pred_iou_thresh = 0.9
    config.clip.model_name = "ViT-L/14"  # Larger CLIP
    return config
