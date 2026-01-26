"""
Data structures for the ML pipeline
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import numpy as np


@dataclass
class BoundingBox:
    """Axis-aligned bounding box"""
    x: int
    y: int
    width: int
    height: int
    
    @property
    def x2(self) -> int:
        return self.x + self.width
    
    @property
    def y2(self) -> int:
        return self.y + self.height
    
    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    def to_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)
    
    def to_xyxy(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.x2, self.y2)
    
    @classmethod
    def from_xyxy(cls, x1: int, y1: int, x2: int, y2: int) -> 'BoundingBox':
        return cls(x=x1, y=y1, width=x2-x1, height=y2-y1)
    
    @classmethod
    def from_mask(cls, mask: np.ndarray) -> 'BoundingBox':
        """Create bounding box from binary mask"""
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if not np.any(rows) or not np.any(cols):
            return cls(0, 0, 0, 0)
        y1, y2 = np.where(rows)[0][[0, -1]]
        x1, x2 = np.where(cols)[0][[0, -1]]
        return cls(x=int(x1), y=int(y1), width=int(x2-x1+1), height=int(y2-y1+1))


@dataclass
class SegmentedElement:
    """Represents a segmented element from SAM"""
    id: str
    mask: np.ndarray  # Binary mask (H, W)
    bbox: BoundingBox
    area: int
    stability_score: float
    predicted_iou: float
    
    # Extracted image region (with alpha channel)
    image_rgba: Optional[np.ndarray] = None
    
    def get_cropped_mask(self) -> np.ndarray:
        """Get mask cropped to bounding box"""
        return self.mask[self.bbox.y:self.bbox.y2, self.bbox.x:self.bbox.x2]
    
    def get_cropped_image(self, image: np.ndarray) -> np.ndarray:
        """Get image region cropped to bounding box"""
        return image[self.bbox.y:self.bbox.y2, self.bbox.x:self.bbox.x2]


@dataclass
class ClassifiedElement(SegmentedElement):
    """Element with classification results from CLIP"""
    category: str = ""  # e.g., "logo", "icon", "photo"
    category_confidence: float = 0.0
    all_scores: Dict[str, float] = field(default_factory=dict)
    
    # Additional classification metadata
    contains_text: bool = False
    is_complex: bool = False  # Has high visual complexity


@dataclass
class TextElement:
    """Extracted text with styling"""
    text: str
    bbox: BoundingBox
    confidence: float
    
    # Styling (estimated)
    font_size: int = 16
    font_weight: str = "normal"  # normal, bold
    font_style: str = "normal"  # normal, italic
    color: str = "#000000"
    alignment: str = "left"
    
    # Relationship to parent element
    parent_element_id: Optional[str] = None


@dataclass
class LayerElement:
    """Final processed element ready for export"""
    id: str
    category: str
    layer_index: int  # Z-order (0 = bottom)
    bbox: BoundingBox
    
    # Visual data
    mask: np.ndarray
    image_rgba: np.ndarray  # Extracted with transparency
    
    # For text elements
    text_content: Optional[List[TextElement]] = None
    
    # For vectorizable elements
    svg_path: Optional[str] = None  # SVG path data if vectorized
    
    # Metadata
    confidence: float = 0.0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedInfographic:
    """Complete processed infographic with all layers"""
    # Original image info
    original_path: str
    width: int
    height: int
    
    # Processed layers (ordered back to front)
    layers: List[LayerElement] = field(default_factory=list)
    
    # Background (inpainted)
    background: Optional[np.ndarray] = None
    
    # All detected text
    text_elements: List[TextElement] = field(default_factory=list)
    
    # Processing metadata
    processing_time: float = 0.0
    model_versions: Dict[str, str] = field(default_factory=dict)
    
    def get_layers_by_category(self, category: str) -> List[LayerElement]:
        """Get all layers of a specific category"""
        return [l for l in self.layers if l.category == category]
    
    def get_layer_order(self) -> List[str]:
        """Get layer IDs in z-order"""
        sorted_layers = sorted(self.layers, key=lambda l: l.layer_index)
        return [l.id for l in sorted_layers]


def calculate_iou(mask1: np.ndarray, mask2: np.ndarray) -> float:
    """Calculate Intersection over Union between two masks"""
    intersection = np.logical_and(mask1, mask2).sum()
    union = np.logical_or(mask1, mask2).sum()
    return intersection / union if union > 0 else 0.0


def calculate_containment(inner: np.ndarray, outer: np.ndarray) -> float:
    """Calculate what fraction of inner is contained in outer"""
    intersection = np.logical_and(inner, outer).sum()
    inner_area = inner.sum()
    return intersection / inner_area if inner_area > 0 else 0.0
