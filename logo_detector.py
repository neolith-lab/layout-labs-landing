"""
Logo detection module
Detects logos and complex graphics that should not have their text extracted separately
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import logging
from dataclasses import dataclass

from utils import BoundingBox, save_debug_image, merge_overlapping_boxes
from config import DEBUG

logger = logging.getLogger(__name__)


@dataclass
class LogoElement:
    """Represents a detected logo or complex graphic"""
    bbox: BoundingBox
    image_data: np.ndarray
    confidence: float = 0.0
    has_text: bool = True  # Logos typically contain text


class LogoDetector:
    """
    Detect logos and complex graphics in infographics.
    
    Logos are identified by:
    1. High edge density in compact regions
    2. Mixed text and graphics in close proximity
    3. Distinct color patterns
    4. Typically located in corners or header/footer areas
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.min_logo_size = self.config.get('min_logo_size', 50)
        self.max_logo_size = self.config.get('max_logo_size', 400)
        self.edge_density_threshold = self.config.get('edge_density_threshold', 0.15)
    
    def detect_logos(self, image: np.ndarray, 
                    text_bboxes: List[BoundingBox] = None) -> List[LogoElement]:
        """
        Detect logos in the image
        
        Args:
            image: Input image
            text_bboxes: Detected text regions (to find text clusters that might be logos)
        
        Returns:
            List of LogoElement objects
        """
        logger.info("Detecting logos...")
        
        logo_candidates = []
        
        # Method 1: Detect by text clustering (multiple text elements close together)
        if text_bboxes:
            logo_candidates.extend(self._detect_by_text_clustering(image, text_bboxes))
        
        # Method 2: Detect by edge/color complexity in compact regions
        logo_candidates.extend(self._detect_by_complexity(image))
        
        # Method 3: Detect in typical logo positions (corners, header)
        logo_candidates.extend(self._detect_by_position(image, text_bboxes))
        
        # Merge overlapping candidates
        merged_bboxes = merge_overlapping_boxes(
            [l.bbox for l in logo_candidates], 
            iou_threshold=0.3
        )
        
        # Create final logo elements
        logos = []
        for bbox in merged_bboxes:
            img_data = image[bbox.y:bbox.y2, bbox.x:bbox.x2].copy()
            logo = LogoElement(
                bbox=bbox,
                image_data=img_data,
                confidence=0.8,
                has_text=self._contains_text_like_features(img_data)
            )
            logos.append(logo)
        
        logger.info(f"Detected {len(logos)} logo regions")
        
        if DEBUG.get('save_intermediate_steps', False):
            self._save_debug_visualization(image, logos)
        
        return logos
    
    def _detect_by_text_clustering(self, image: np.ndarray, 
                                   text_bboxes: List[BoundingBox]) -> List[LogoElement]:
        """
        Detect logos by finding clusters of text elements that are likely part of a logo.
        
        Logo text characteristics:
        - Multiple text elements very close together
        - Mixed font sizes in small area
        - Surrounded by graphical elements
        """
        if not text_bboxes or len(text_bboxes) < 2:
            return []
        
        logos = []
        used_indices = set()
        
        # Find clusters of nearby text elements
        for i, bbox1 in enumerate(text_bboxes):
            if i in used_indices:
                continue
            
            cluster = [bbox1]
            cluster_indices = {i}
            
            # Find nearby text elements
            for j, bbox2 in enumerate(text_bboxes):
                if j in used_indices or j == i:
                    continue
                
                # Check if text elements are very close (within 20 pixels)
                if self._are_close(bbox1, bbox2, threshold=30):
                    cluster.append(bbox2)
                    cluster_indices.add(j)
            
            # If we have a cluster of 2+ text elements in a small area
            if len(cluster) >= 2:
                # Calculate cluster bounding box
                min_x = min(b.x for b in cluster)
                min_y = min(b.y for b in cluster)
                max_x = max(b.x2 for b in cluster)
                max_y = max(b.y2 for b in cluster)
                
                cluster_w = max_x - min_x
                cluster_h = max_y - min_y
                
                # Check if cluster is compact (logo-like)
                if (self.min_logo_size <= cluster_w <= self.max_logo_size and 
                    self.min_logo_size <= cluster_h <= self.max_logo_size):
                    
                    # Add some padding
                    padding = 10
                    min_x = max(0, min_x - padding)
                    min_y = max(0, min_y - padding)
                    max_x = min(image.shape[1], max_x + padding)
                    max_y = min(image.shape[0], max_y + padding)
                    
                    bbox = BoundingBox(min_x, min_y, max_x - min_x, max_y - min_y, label='logo')
                    
                    # Verify it has logo-like properties
                    region = image[min_y:max_y, min_x:max_x]
                    if self._has_logo_properties(region):
                        img_data = region.copy()
                        logos.append(LogoElement(
                            bbox=bbox,
                            image_data=img_data,
                            confidence=0.7,
                            has_text=True
                        ))
                        used_indices.update(cluster_indices)
        
        return logos
    
    def _detect_by_complexity(self, image: np.ndarray) -> List[LogoElement]:
        """Detect logos by finding regions with high visual complexity"""
        logos = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Calculate local edge density
        kernel_size = 30
        kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size ** 2)
        edge_density = cv2.filter2D(edges.astype(np.float32), -1, kernel)
        
        # Find high-density regions
        _, thresh = cv2.threshold(edge_density, 40, 255, cv2.THRESH_BINARY)
        thresh = thresh.astype(np.uint8)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Check size constraints
            if (self.min_logo_size <= w <= self.max_logo_size and 
                self.min_logo_size <= h <= self.max_logo_size):
                
                # Check aspect ratio (logos are typically not too elongated)
                aspect_ratio = max(w, h) / (min(w, h) + 1)
                if aspect_ratio < 4:
                    region = image[y:y+h, x:x+w]
                    if self._has_logo_properties(region):
                        bbox = BoundingBox(x, y, w, h, label='logo')
                        logos.append(LogoElement(
                            bbox=bbox,
                            image_data=region.copy(),
                            confidence=0.6,
                            has_text=self._contains_text_like_features(region)
                        ))
        
        return logos
    
    def _detect_by_position(self, image: np.ndarray, 
                           text_bboxes: List[BoundingBox] = None) -> List[LogoElement]:
        """Detect logos in typical positions (corners, header)"""
        logos = []
        h, w = image.shape[:2]
        
        # Define typical logo regions (corners, header center)
        logo_regions = [
            (0, 0, w // 4, h // 6),           # Top-left
            (3 * w // 4, 0, w // 4, h // 6),  # Top-right
            (0, 5 * h // 6, w // 4, h // 6),  # Bottom-left
            (3 * w // 4, 5 * h // 6, w // 4, h // 6),  # Bottom-right
            (w // 3, 0, w // 3, h // 8),      # Top-center
        ]
        
        for rx, ry, rw, rh in logo_regions:
            region = image[ry:ry+rh, rx:rx+rw]
            
            # Check if this region has logo-like content
            if self._has_logo_properties(region):
                # Find the actual content bounds within this region
                content_bbox = self._find_content_bounds(region)
                if content_bbox:
                    cx, cy, cw, ch = content_bbox
                    if (self.min_logo_size <= cw <= self.max_logo_size and
                        self.min_logo_size <= ch <= self.max_logo_size):
                        
                        bbox = BoundingBox(rx + cx, ry + cy, cw, ch, label='logo')
                        img_data = image[bbox.y:bbox.y2, bbox.x:bbox.x2].copy()
                        logos.append(LogoElement(
                            bbox=bbox,
                            image_data=img_data,
                            confidence=0.5,
                            has_text=self._contains_text_like_features(img_data)
                        ))
        
        return logos
    
    def _are_close(self, bbox1: BoundingBox, bbox2: BoundingBox, threshold: int = 20) -> bool:
        """Check if two bounding boxes are close to each other"""
        # Calculate minimum distance between boxes
        dx = max(0, max(bbox1.x, bbox2.x) - min(bbox1.x2, bbox2.x2))
        dy = max(0, max(bbox1.y, bbox2.y) - min(bbox1.y2, bbox2.y2))
        return dx <= threshold and dy <= threshold
    
    def _has_logo_properties(self, region: np.ndarray) -> bool:
        """Check if a region has logo-like properties"""
        if region.size == 0:
            return False
        
        # Check edge density
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        if edge_density < 0.05:  # Too few edges
            return False
        
        # Check color diversity (logos often have distinct colors)
        unique_colors = len(np.unique(region.reshape(-1, 3), axis=0))
        color_ratio = unique_colors / (region.shape[0] * region.shape[1])
        
        # Logos have moderate color diversity (not too uniform, not like photos)
        return 0.01 < color_ratio < 0.5
    
    def _contains_text_like_features(self, region: np.ndarray) -> bool:
        """Check if region contains text-like features"""
        if region.size == 0:
            return False
        
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Count small, compact contours (text-like)
        text_like_count = 0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if 10 < area < 500 and 0.2 < w/max(h, 1) < 5:
                text_like_count += 1
        
        return text_like_count >= 3
    
    def _find_content_bounds(self, region: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Find the bounds of actual content in a region"""
        if region.size == 0:
            return None
        
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        
        # Detect non-background pixels
        # Assume background is the most common color
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        bg_value = np.argmax(hist)
        
        # Create mask of non-background pixels
        mask = np.abs(gray.astype(np.int16) - bg_value) > 20
        
        # Find bounds
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        
        if not np.any(rows) or not np.any(cols):
            return None
        
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        
        return (int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min))
    
    def _save_debug_visualization(self, image: np.ndarray, logos: List[LogoElement]):
        """Save visualization of detected logos"""
        debug_img = image.copy()
        
        for i, logo in enumerate(logos):
            bbox = logo.bbox
            # Draw bounding box in orange
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), (0, 165, 255), 3)
            
            # Add label
            label = f"Logo {i+1} (conf: {logo.confidence:.2f})"
            cv2.putText(debug_img, label, (bbox.x, bbox.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)
        
        save_debug_image(debug_img, '00_logo_detection.png', DEBUG.get('output_dir', './debug_output'))
    
    def filter_text_in_logos(self, text_bboxes: List[BoundingBox], 
                            logos: List[LogoElement]) -> List[BoundingBox]:
        """
        Filter out text bounding boxes that are inside logo regions
        
        Args:
            text_bboxes: All detected text bounding boxes
            logos: Detected logo elements
        
        Returns:
            Filtered list of text bounding boxes (excluding those in logos)
        """
        if not logos:
            return text_bboxes
        
        filtered = []
        for text_bbox in text_bboxes:
            is_in_logo = False
            for logo in logos:
                if self._is_inside(text_bbox, logo.bbox):
                    is_in_logo = True
                    break
            
            if not is_in_logo:
                filtered.append(text_bbox)
        
        removed_count = len(text_bboxes) - len(filtered)
        if removed_count > 0:
            logger.info(f"Filtered out {removed_count} text elements inside logos")
        
        return filtered
    
    def _is_inside(self, inner: BoundingBox, outer: BoundingBox, threshold: float = 0.7) -> bool:
        """Check if inner bbox is mostly inside outer bbox"""
        # Calculate intersection
        x1 = max(inner.x, outer.x)
        y1 = max(inner.y, outer.y)
        x2 = min(inner.x2, outer.x2)
        y2 = min(inner.y2, outer.y2)
        
        if x2 <= x1 or y2 <= y1:
            return False
        
        intersection_area = (x2 - x1) * (y2 - y1)
        inner_area = inner.area
        
        return intersection_area / inner_area >= threshold
