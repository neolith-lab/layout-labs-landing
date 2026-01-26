"""
Shape detection and reconstruction module
Steps 6, 7, 8: Shape identification, removal, and reconstruction
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import logging
from dataclasses import dataclass
from enum import Enum

from utils import (BoundingBox, get_contour_approx, is_circle, is_rectangle,
                  save_debug_image, rgb_to_hex)
from config import SHAPE_DETECTION, DEBUG

logger = logging.getLogger(__name__)


class ShapeType(Enum):
    """Types of shapes that can be detected"""
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    LINE = "line"
    ARROW = "arrow"
    UNKNOWN = "unknown"


@dataclass
class ShapeElement:
    """Represents a detected shape"""
    shape_type: ShapeType
    bbox: BoundingBox
    contour: np.ndarray
    fill_color: str
    stroke_color: str
    stroke_width: int = 1
    properties: Dict = None  # Additional shape-specific properties
    

class ShapeDetector:
    """Detect and classify shapes in infographic"""
    
    def __init__(self, config: Dict = None):
        self.config = config or SHAPE_DETECTION
    
    def detect_shapes(self, image: np.ndarray, text_bboxes: List[BoundingBox] = None,
                     image_bboxes: List[BoundingBox] = None) -> List[ShapeElement]:
        """
        Detect geometric shapes in the image
        
        Args:
            image: Input image
            text_bboxes: Already detected text regions to exclude
            image_bboxes: Already detected image regions to exclude
        
        Returns:
            List of detected shape elements
        """
        logger.info("Detecting shapes...")
        
        # Create exclusion mask
        exclusion_mask = self._create_exclusion_mask(image.shape, text_bboxes, image_bboxes)
        
        # Preprocess image for shape detection
        processed = self._preprocess_for_shapes(image)
        
        # Find contours
        contours = self._find_shape_contours(processed, exclusion_mask)
        
        # Classify and create shape elements
        shape_elements = []
        for contour in contours:
            shape = self._classify_and_create_shape(image, contour)
            if shape:
                shape_elements.append(shape)
        
        logger.info(f"Detected {len(shape_elements)} shapes")
        
        if DEBUG.get('save_intermediate_steps', False):
            self._save_debug_visualization(image, shape_elements)
        
        return shape_elements
    
    def _create_exclusion_mask(self, image_shape: Tuple[int, int, int],
                              text_bboxes: List[BoundingBox] = None,
                              image_bboxes: List[BoundingBox] = None) -> np.ndarray:
        """Create mask of regions to exclude"""
        mask = np.zeros(image_shape[:2], dtype=np.uint8)
        
        all_bboxes = []
        if text_bboxes:
            all_bboxes.extend(text_bboxes)
        if image_bboxes:
            all_bboxes.extend(image_bboxes)
        
        for bbox in all_bboxes:
            mask[bbox.y:bbox.y2, bbox.x:bbox.x2] = 255
        
        return mask
    
    def _preprocess_for_shapes(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for shape detection"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 11, 2)
        
        # Morphological operations to clean up
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        return thresh
    
    def _find_shape_contours(self, binary_image: np.ndarray,
                            exclusion_mask: np.ndarray) -> List[np.ndarray]:
        """Find contours that likely represent shapes"""
        # Apply exclusion mask
        binary_image = cv2.bitwise_and(binary_image, cv2.bitwise_not(exclusion_mask))
        
        # Find contours
        contours, hierarchy = cv2.findContours(binary_image, cv2.RETR_TREE,
                                               cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by area
        min_area = self.config.get('min_area', 100)
        filtered_contours = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                filtered_contours.append(contour)
        
        return filtered_contours
    
    def _classify_and_create_shape(self, image: np.ndarray, contour: np.ndarray) -> Optional[ShapeElement]:
        """Classify contour and create ShapeElement"""
        # Approximate contour
        approx = get_contour_approx(contour, self.config.get('epsilon_factor', 0.02))
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        bbox = BoundingBox(x, y, w, h, label='shape')
        
        # Classify shape
        shape_type, properties = self._classify_shape(contour, approx)
        
        # Extract colors
        fill_color = self._extract_fill_color(image, contour)
        stroke_color = self._extract_stroke_color(image, contour)
        stroke_width = self._estimate_stroke_width(image, contour)
        
        shape = ShapeElement(
            shape_type=shape_type,
            bbox=bbox,
            contour=contour,
            fill_color=fill_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            properties=properties
        )
        
        return shape
    
    def _classify_shape(self, contour: np.ndarray, approx: np.ndarray) -> Tuple[ShapeType, Dict]:
        """Classify the shape type"""
        properties = {}
        
        # Check for circle
        if is_circle(contour, self.config.get('min_circle_ratio', 0.7)):
            (x, y), radius = cv2.minEnclosingCircle(contour)
            properties['center'] = (int(x), int(y))
            properties['radius'] = int(radius)
            return ShapeType.CIRCLE, properties
        
        # Check for rectangle
        if len(approx) == 4 and is_rectangle(contour, self.config.get('min_rect_ratio', 0.85)):
            rect = cv2.minAreaRect(contour)
            properties['rect'] = rect
            return ShapeType.RECTANGLE, properties
        
        # Check for ellipse
        if len(contour) >= 5:
            try:
                ellipse = cv2.fitEllipse(contour)
                # Check if it's actually an ellipse (not too elongated)
                (center, axes, angle) = ellipse
                aspect_ratio = max(axes) / min(axes) if min(axes) > 0 else 0
                if 1.2 < aspect_ratio < 3.0:
                    properties['ellipse'] = ellipse
                    return ShapeType.ELLIPSE, properties
            except:
                pass
        
        # Check for line
        if len(approx) == 2 or (len(approx) <= 4 and self._is_line_like(contour)):
            [vx, vy, x, y] = cv2.fitLine(contour, cv2.DIST_L2, 0, 0.01, 0.01)
            properties['line_params'] = (vx[0], vy[0], x[0], y[0])
            return ShapeType.LINE, properties
        
        # Check for arrow (heuristic: line with triangle at end)
        if self._is_arrow(approx):
            properties['points'] = approx
            return ShapeType.ARROW, properties
        
        # Polygon for everything else
        properties['vertices'] = len(approx)
        properties['points'] = approx
        return ShapeType.POLYGON, properties
    
    def _is_line_like(self, contour: np.ndarray) -> bool:
        """Check if contour represents a line"""
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = max(w, h) / (min(w, h) + 1)
        return aspect_ratio > 5
    
    def _is_arrow(self, approx: np.ndarray) -> bool:
        """Heuristic check if shape is an arrow"""
        # Simple check: polygon with specific vertex pattern
        # This is simplified - real arrow detection would be more complex
        if len(approx) >= 5 and len(approx) <= 8:
            # Check for one very acute angle (arrowhead)
            # This is a simplified heuristic
            return True
        return False
    
    def _extract_fill_color(self, image: np.ndarray, contour: np.ndarray) -> str:
        """Extract fill color of shape"""
        # Create mask for the shape
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        
        # Erode to get interior pixels only
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        
        # Get pixels within shape
        pixels = image[mask > 0]
        
        if len(pixels) == 0:
            return '#FFFFFF'
        
        # Calculate median color
        median_color = np.median(pixels, axis=0).astype(int)
        return rgb_to_hex(tuple(median_color[::-1]))  # BGR to RGB
    
    def _extract_stroke_color(self, image: np.ndarray, contour: np.ndarray) -> str:
        """Extract stroke/border color of shape"""
        # Create mask for the contour only
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, 2)
        
        # Get pixels on contour
        pixels = image[mask > 0]
        
        if len(pixels) == 0:
            return '#000000'
        
        # Calculate median color
        median_color = np.median(pixels, axis=0).astype(int)
        return rgb_to_hex(tuple(median_color[::-1]))  # BGR to RGB
    
    def _estimate_stroke_width(self, image: np.ndarray, contour: np.ndarray) -> int:
        """Estimate stroke width of shape"""
        # This is a simplified estimation
        # Real implementation would analyze the border thickness
        return 2  # Default value
    
    def _save_debug_visualization(self, image: np.ndarray, shape_elements: List[ShapeElement]):
        """Save visualization of detected shapes"""
        debug_img = image.copy()
        
        for i, shape in enumerate(shape_elements):
            # Draw contour
            cv2.drawContours(debug_img, [shape.contour], -1, (0, 255, 255), 2)
            
            # Draw bounding box
            bbox = shape.bbox
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), (255, 0, 255), 1)
            
            # Add label
            label = f"{shape.shape_type.value}"
            cv2.putText(debug_img, label, (bbox.x, bbox.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        save_debug_image(debug_img, '06_shape_detection.png', DEBUG.get('output_dir', './debug_output'))
