"""
Container detection module
Detects container shapes (rounded rectangles, cards, boxes) that hold images or text
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import logging
from dataclasses import dataclass, field
from enum import Enum

from utils import BoundingBox, save_debug_image, rgb_to_hex
from config import DEBUG

logger = logging.getLogger(__name__)


class ContainerType(Enum):
    """Types of containers"""
    ROUNDED_RECTANGLE = "rounded_rectangle"
    RECTANGLE = "rectangle"
    CARD = "card"  # Rectangle with shadow/border
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    CUSTOM = "custom"


@dataclass
class ContainerElement:
    """Represents a container shape that holds content"""
    container_type: ContainerType
    bbox: BoundingBox
    contour: np.ndarray
    fill_color: str
    stroke_color: str
    stroke_width: int = 1
    corner_radius: int = 0  # For rounded rectangles
    contains_image: bool = False
    contains_text: bool = False
    content_bboxes: List[BoundingBox] = field(default_factory=list)
    properties: Dict = field(default_factory=dict)


class ContainerDetector:
    """
    Detect container shapes in infographics.
    
    Containers are shapes that:
    1. Have a distinct fill color (often light/white)
    2. May have rounded corners
    3. Contain images, text, or both
    4. Are typically larger than simple decorative shapes
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.min_container_size = self.config.get('min_container_size', 80)
        self.min_container_area = self.config.get('min_container_area', 5000)
    
    def detect_containers(self, image: np.ndarray,
                         text_bboxes: List[BoundingBox] = None,
                         image_bboxes: List[BoundingBox] = None) -> List[ContainerElement]:
        """
        Detect container shapes in the image
        
        Args:
            image: Input image
            text_bboxes: Detected text regions
            image_bboxes: Detected image regions
        
        Returns:
            List of ContainerElement objects
        """
        logger.info("Detecting containers...")
        
        # Detect potential container shapes
        container_candidates = self._detect_container_shapes(image)
        
        # Classify containers and determine their contents
        containers = []
        for candidate in container_candidates:
            container = self._classify_container(
                image, candidate, text_bboxes, image_bboxes
            )
            if container:
                containers.append(container)
        
        # Filter out containers that are inside other containers
        containers = self._filter_nested_containers(containers)
        
        logger.info(f"Detected {len(containers)} containers")
        
        if DEBUG.get('save_intermediate_steps', False):
            self._save_debug_visualization(image, containers, text_bboxes, image_bboxes)
        
        return containers
    
    def _detect_container_shapes(self, image: np.ndarray) -> List[Tuple[np.ndarray, BoundingBox]]:
        """Detect potential container shapes using edge detection and contour analysis"""
        candidates = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Use multiple thresholding approaches
        
        # Approach 1: Adaptive thresholding
        thresh1 = cv2.adaptiveThreshold(filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 11, 2)
        
        # Approach 2: Canny edge detection
        edges = cv2.Canny(filtered, 30, 100)
        
        # Dilate edges to connect nearby edges
        kernel = np.ones((3, 3), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # Find contours from both approaches
        for binary in [thresh1, edges_dilated]:
            contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, 
                                                   cv2.CHAIN_APPROX_SIMPLE)
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                # Filter by area
                if area < self.min_container_area:
                    continue
                
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by size
                if w < self.min_container_size or h < self.min_container_size:
                    continue
                
                # Filter by aspect ratio (containers shouldn't be too elongated)
                aspect_ratio = max(w, h) / (min(w, h) + 1)
                if aspect_ratio > 5:
                    continue
                
                # Check if this could be a container (has reasonable fill ratio)
                hull = cv2.convexHull(contour)
                hull_area = cv2.contourArea(hull)
                if hull_area > 0 and area / hull_area > 0.5:  # Not too irregular
                    bbox = BoundingBox(x, y, w, h, label='container')
                    candidates.append((contour, bbox))
        
        # Remove duplicates (similar bounding boxes)
        candidates = self._remove_duplicate_candidates(candidates)
        
        return candidates
    
    def _remove_duplicate_candidates(self, 
                                    candidates: List[Tuple[np.ndarray, BoundingBox]]
                                    ) -> List[Tuple[np.ndarray, BoundingBox]]:
        """Remove duplicate/very similar candidates"""
        if not candidates:
            return []
        
        # Sort by area (largest first)
        candidates = sorted(candidates, key=lambda x: x[1].area, reverse=True)
        
        unique = []
        for contour, bbox in candidates:
            is_duplicate = False
            for _, existing_bbox in unique:
                # Calculate IoU
                x1 = max(bbox.x, existing_bbox.x)
                y1 = max(bbox.y, existing_bbox.y)
                x2 = min(bbox.x2, existing_bbox.x2)
                y2 = min(bbox.y2, existing_bbox.y2)
                
                if x2 > x1 and y2 > y1:
                    intersection = (x2 - x1) * (y2 - y1)
                    union = bbox.area + existing_bbox.area - intersection
                    iou = intersection / union
                    
                    if iou > 0.5:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique.append((contour, bbox))
        
        return unique
    
    def _classify_container(self, image: np.ndarray,
                           candidate: Tuple[np.ndarray, BoundingBox],
                           text_bboxes: List[BoundingBox] = None,
                           image_bboxes: List[BoundingBox] = None) -> Optional[ContainerElement]:
        """Classify a container candidate and determine its contents"""
        contour, bbox = candidate
        
        # Determine container type
        container_type, properties = self._determine_container_type(contour)
        
        # Extract colors
        fill_color = self._extract_fill_color(image, contour)
        stroke_color = self._extract_stroke_color(image, contour)
        
        # Check what content is inside
        contains_image = False
        contains_text = False
        content_bboxes = []
        
        if image_bboxes:
            for img_bbox in image_bboxes:
                if self._is_contained(img_bbox, bbox):
                    contains_image = True
                    content_bboxes.append(img_bbox)
        
        if text_bboxes:
            for text_bbox in text_bboxes:
                if self._is_contained(text_bbox, bbox):
                    contains_text = True
                    content_bboxes.append(text_bbox)
        
        # A valid container should contain something
        if not contains_image and not contains_text:
            # Check if it looks like an empty card/placeholder
            if not self._looks_like_container(image, bbox):
                return None
        
        # Estimate corner radius for rounded rectangles
        corner_radius = 0
        if container_type == ContainerType.ROUNDED_RECTANGLE:
            corner_radius = self._estimate_corner_radius(contour, bbox)
        
        return ContainerElement(
            container_type=container_type,
            bbox=bbox,
            contour=contour,
            fill_color=fill_color,
            stroke_color=stroke_color,
            stroke_width=self._estimate_stroke_width(image, contour),
            corner_radius=corner_radius,
            contains_image=contains_image,
            contains_text=contains_text,
            content_bboxes=content_bboxes,
            properties=properties
        )
    
    def _determine_container_type(self, contour: np.ndarray) -> Tuple[ContainerType, Dict]:
        """Determine the type of container shape"""
        properties = {}
        
        # Approximate contour
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # Check for circle
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            if circularity > 0.8:
                (cx, cy), radius = cv2.minEnclosingCircle(contour)
                properties['center'] = (int(cx), int(cy))
                properties['radius'] = int(radius)
                return ContainerType.CIRCLE, properties
        
        # Check for ellipse
        if len(contour) >= 5:
            try:
                ellipse = cv2.fitEllipse(contour)
                (center, axes, angle) = ellipse
                aspect_ratio = max(axes) / (min(axes) + 1)
                if 1.2 < aspect_ratio < 3.0:
                    # Check if contour matches ellipse well
                    ellipse_mask = np.zeros((int(axes[1] * 2), int(axes[0] * 2)), dtype=np.uint8)
                    # If it's close to an ellipse
                    if circularity > 0.6:
                        properties['ellipse'] = ellipse
                        return ContainerType.ELLIPSE, properties
            except:
                pass
        
        # Check for rectangle (4 vertices)
        if len(approx) == 4:
            # Check if it's a proper rectangle
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
            box_area = cv2.contourArea(box)
            if box_area > 0 and area / box_area > 0.9:
                properties['rect'] = rect
                return ContainerType.RECTANGLE, properties
        
        # Check for rounded rectangle (more than 4 vertices but rectangle-like)
        if 4 < len(approx) <= 12:
            x, y, w, h = cv2.boundingRect(contour)
            rect_area = w * h
            if area / rect_area > 0.85:  # Close to rectangular
                properties['is_rounded'] = True
                return ContainerType.ROUNDED_RECTANGLE, properties
        
        # Default to custom shape
        properties['vertices'] = len(approx)
        properties['points'] = approx
        return ContainerType.CUSTOM, properties
    
    def _estimate_corner_radius(self, contour: np.ndarray, bbox: BoundingBox) -> int:
        """Estimate the corner radius of a rounded rectangle"""
        # Sample points near corners and estimate curvature
        x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
        
        # Get contour points
        points = contour.reshape(-1, 2)
        
        # Find points near top-left corner
        corner_region = 0.15  # 15% from corner
        corner_points = []
        
        for px, py in points:
            # Check if point is near any corner
            near_left = px < x + w * corner_region
            near_right = px > x + w * (1 - corner_region)
            near_top = py < y + h * corner_region
            near_bottom = py > y + h * (1 - corner_region)
            
            if (near_left or near_right) and (near_top or near_bottom):
                corner_points.append((px, py))
        
        if len(corner_points) < 3:
            return 0
        
        # Estimate radius based on corner point distribution
        corner_points = np.array(corner_points)
        
        # Simple heuristic: average distance from corner
        corners = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
        
        min_distances = []
        for cx, cy in corners:
            distances = np.sqrt((corner_points[:, 0] - cx)**2 + (corner_points[:, 1] - cy)**2)
            if len(distances) > 0:
                min_distances.append(np.min(distances))
        
        if min_distances:
            return int(np.mean(min_distances))
        
        return int(min(w, h) * 0.1)  # Default to 10% of smaller dimension
    
    def _is_contained(self, inner: BoundingBox, outer: BoundingBox, threshold: float = 0.6) -> bool:
        """Check if inner bbox is mostly contained within outer bbox"""
        # Calculate intersection
        x1 = max(inner.x, outer.x)
        y1 = max(inner.y, outer.y)
        x2 = min(inner.x2, outer.x2)
        y2 = min(inner.y2, outer.y2)
        
        if x2 <= x1 or y2 <= y1:
            return False
        
        intersection_area = (x2 - x1) * (y2 - y1)
        
        return intersection_area / inner.area >= threshold
    
    def _looks_like_container(self, image: np.ndarray, bbox: BoundingBox) -> bool:
        """Check if a region looks like an empty container/card"""
        region = image[bbox.y:bbox.y2, bbox.x:bbox.x2]
        
        if region.size == 0:
            return False
        
        # Check if region has uniform fill (like a card)
        lab = cv2.cvtColor(region, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        
        # Calculate variance - containers typically have low variance in the interior
        # but may have borders
        interior = l_channel[5:-5, 5:-5] if l_channel.shape[0] > 10 and l_channel.shape[1] > 10 else l_channel
        variance = np.var(interior)
        
        # Low variance suggests a filled container
        return variance < 500
    
    def _extract_fill_color(self, image: np.ndarray, contour: np.ndarray) -> str:
        """Extract fill color of container"""
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        
        # Erode to get interior only
        kernel = np.ones((10, 10), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        
        pixels = image[mask > 0]
        
        if len(pixels) == 0:
            return '#FFFFFF'
        
        median_color = np.median(pixels, axis=0).astype(int)
        return rgb_to_hex(tuple(median_color[::-1]))
    
    def _extract_stroke_color(self, image: np.ndarray, contour: np.ndarray) -> str:
        """Extract stroke/border color of container"""
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, 3)
        
        pixels = image[mask > 0]
        
        if len(pixels) == 0:
            return '#000000'
        
        median_color = np.median(pixels, axis=0).astype(int)
        return rgb_to_hex(tuple(median_color[::-1]))
    
    def _estimate_stroke_width(self, image: np.ndarray, contour: np.ndarray) -> int:
        """Estimate stroke width"""
        return 2  # Default
    
    def _filter_nested_containers(self, containers: List[ContainerElement]) -> List[ContainerElement]:
        """Filter out containers that are completely inside other containers"""
        if len(containers) <= 1:
            return containers
        
        # Sort by area (largest first)
        containers = sorted(containers, key=lambda c: c.bbox.area, reverse=True)
        
        filtered = []
        for container in containers:
            is_nested = False
            for existing in filtered:
                if self._is_contained(container.bbox, existing.bbox, threshold=0.9):
                    is_nested = True
                    break
            
            if not is_nested:
                filtered.append(container)
        
        return filtered
    
    def _save_debug_visualization(self, image: np.ndarray, 
                                  containers: List[ContainerElement],
                                  text_bboxes: List[BoundingBox] = None,
                                  image_bboxes: List[BoundingBox] = None):
        """Save visualization of detected containers"""
        debug_img = image.copy()
        
        # Draw containers
        for i, container in enumerate(containers):
            bbox = container.bbox
            
            # Color based on content
            if container.contains_image and container.contains_text:
                color = (255, 0, 255)  # Magenta - both
            elif container.contains_image:
                color = (0, 255, 0)    # Green - image only
            elif container.contains_text:
                color = (255, 255, 0)  # Cyan - text only
            else:
                color = (128, 128, 128)  # Gray - empty
            
            # Draw contour
            cv2.drawContours(debug_img, [container.contour], -1, color, 3)
            
            # Add label
            label = f"{container.container_type.value}"
            if container.corner_radius > 0:
                label += f" r={container.corner_radius}"
            cv2.putText(debug_img, label, (bbox.x, bbox.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        save_debug_image(debug_img, '02_container_detection.png', 
                        DEBUG.get('output_dir', './debug_output'))
    
    def get_images_in_containers(self, containers: List[ContainerElement],
                                image_elements: List) -> Tuple[List, List]:
        """
        Separate images into those inside containers and those outside
        
        Returns:
            (images_in_containers, images_outside_containers)
        """
        images_in = []
        images_out = []
        
        for img_elem in image_elements:
            in_container = False
            for container in containers:
                if self._is_contained(img_elem.bbox, container.bbox):
                    in_container = True
                    break
            
            if in_container:
                images_in.append(img_elem)
            else:
                images_out.append(img_elem)
        
        return images_in, images_out
