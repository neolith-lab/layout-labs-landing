"""
Utility functions for the Raster to SVG converter
"""

import os
import cv2
import numpy as np
from typing import Tuple, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BoundingBox:
    """Represents a bounding box with coordinates and metadata"""
    
    def __init__(self, x: int, y: int, w: int, h: int, label: str = '', confidence: float = 1.0):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label = label
        self.confidence = confidence
    
    @property
    def x2(self) -> int:
        return self.x + self.w
    
    @property
    def y2(self) -> int:
        return self.y + self.h
    
    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)
    
    @property
    def area(self) -> int:
        return self.w * self.h
    
    def to_dict(self):
        return {
            'x': self.x,
            'y': self.y,
            'width': self.w,
            'height': self.h,
            'label': self.label,
            'confidence': self.confidence
        }
    
    def __repr__(self):
        return f"BBox({self.x},{self.y},{self.w},{self.h})"


def create_mask_from_bbox(image_shape: Tuple[int, int], bboxes: List[BoundingBox]) -> np.ndarray:
    """Create a binary mask from bounding boxes"""
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    for bbox in bboxes:
        mask[bbox.y:bbox.y2, bbox.x:bbox.x2] = 255
    return mask


def inpaint_image(image: np.ndarray, mask: np.ndarray, method: str = 'telea', radius: int = 5) -> np.ndarray:
    """
    Inpaint image using specified method
    
    Args:
        image: Input image
        mask: Binary mask where 255 indicates areas to inpaint
        method: 'telea' or 'ns' (Navier-Stokes)
        radius: Inpainting radius
    
    Returns:
        Inpainted image
    """
    if method == 'telea':
        return cv2.inpaint(image, mask, radius, cv2.INPAINT_TELEA)
    else:
        return cv2.inpaint(image, mask, radius, cv2.INPAINT_NS)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color string"""
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def calculate_dominant_color(image_region: np.ndarray) -> Tuple[int, int, int]:
    """Calculate dominant color in image region"""
    pixels = image_region.reshape(-1, 3)
    pixels = pixels[~np.all(pixels == 0, axis=1)]  # Remove black pixels
    
    if len(pixels) == 0:
        return (255, 255, 255)
    
    # Simple mean for speed, could use k-means for better accuracy
    return tuple(np.mean(pixels, axis=0).astype(int))


def get_contour_approx(contour: np.ndarray, epsilon_factor: float = 0.02) -> np.ndarray:
    """Approximate contour to reduce number of points"""
    epsilon = epsilon_factor * cv2.arcLength(contour, True)
    return cv2.approxPolyDP(contour, epsilon, True)


def is_circle(contour: np.ndarray, min_ratio: float = 0.7) -> bool:
    """Check if contour represents a circle"""
    area = cv2.contourArea(contour)
    if area == 0:
        return False
    
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return False
    
    circularity = 4 * np.pi * area / (perimeter * perimeter)
    return circularity >= min_ratio


def is_rectangle(contour: np.ndarray, min_ratio: float = 0.85) -> bool:
    """Check if contour represents a rectangle"""
    approx = get_contour_approx(contour, 0.02)
    if len(approx) != 4:
        return False
    
    area = cv2.contourArea(contour)
    x, y, w, h = cv2.boundingRect(contour)
    rect_area = w * h
    
    if rect_area == 0:
        return False
    
    return area / rect_area >= min_ratio


def save_debug_image(image: np.ndarray, filename: str, output_dir: str = './debug_output'):
    """Save debug image to output directory"""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    cv2.imwrite(filepath, image)
    logger.info(f"Saved debug image: {filepath}")


def merge_overlapping_boxes(bboxes: List[BoundingBox], iou_threshold: float = 0.3) -> List[BoundingBox]:
    """Merge overlapping bounding boxes"""
    if not bboxes:
        return []
    
    # Sort by area (descending)
    bboxes = sorted(bboxes, key=lambda b: b.area, reverse=True)
    merged = []
    
    while bboxes:
        current = bboxes.pop(0)
        overlaps = []
        remaining = []
        
        for bbox in bboxes:
            if calculate_iou(current, bbox) > iou_threshold:
                overlaps.append(bbox)
            else:
                remaining.append(bbox)
        
        if overlaps:
            # Merge overlapping boxes
            all_boxes = [current] + overlaps
            min_x = min(b.x for b in all_boxes)
            min_y = min(b.y for b in all_boxes)
            max_x = max(b.x2 for b in all_boxes)
            max_y = max(b.y2 for b in all_boxes)
            
            merged_bbox = BoundingBox(min_x, min_y, max_x - min_x, max_y - min_y,
                                     label=current.label, confidence=current.confidence)
            merged.append(merged_bbox)
        else:
            merged.append(current)
        
        bboxes = remaining
    
    return merged


def calculate_iou(bbox1: BoundingBox, bbox2: BoundingBox) -> float:
    """Calculate Intersection over Union between two bounding boxes"""
    x1 = max(bbox1.x, bbox2.x)
    y1 = max(bbox1.y, bbox2.y)
    x2 = min(bbox1.x2, bbox2.x2)
    y2 = min(bbox1.y2, bbox2.y2)
    
    if x2 < x1 or y2 < y1:
        return 0.0
    
    intersection = (x2 - x1) * (y2 - y1)
    union = bbox1.area + bbox2.area - intersection
    
    return intersection / union if union > 0 else 0.0
