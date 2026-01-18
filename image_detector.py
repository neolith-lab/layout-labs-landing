"""
Image detection and processing module
Steps 3, 4, 5: Image bounding box detection, removal, and optional SVG conversion
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import logging
from dataclasses import dataclass

from utils import BoundingBox, save_debug_image, calculate_dominant_color
from config import IMAGE_PROCESSING, DEBUG

logger = logging.getLogger(__name__)


@dataclass
class ImageElement:
    """Represents a detected image within the infographic"""
    bbox: BoundingBox
    image_data: np.ndarray
    is_photo: bool = True
    dominant_colors: List[Tuple[int, int, int]] = None
    

class ImageDetector:
    """Detect and extract embedded images from infographic"""
    
    def __init__(self, config: Dict = None):
        self.config = config or IMAGE_PROCESSING
    
    def detect_images(self, image: np.ndarray, text_bboxes: List[BoundingBox] = None,
                     shape_bboxes: List[BoundingBox] = None) -> List[ImageElement]:
        """
        Detect embedded images in the infographic
        
        Args:
            image: Input image
            text_bboxes: Already detected text regions to exclude
            shape_bboxes: Already detected shape regions to exclude
        
        Returns:
            List of detected image elements
        """
        logger.info("Detecting embedded images...")
        
        # Create exclusion mask
        exclusion_mask = self._create_exclusion_mask(image.shape, text_bboxes, shape_bboxes)
        
        # Detect image regions using various methods
        image_candidates = []
        
        # Method 1: Color variance analysis
        image_candidates.extend(self._detect_by_color_variance(image, exclusion_mask))
        
        # Method 2: Edge density analysis
        image_candidates.extend(self._detect_by_edge_density(image, exclusion_mask))
        
        # Method 3: Texture analysis
        image_candidates.extend(self._detect_by_texture(image, exclusion_mask))
        
        # Merge overlapping detections
        image_elements = self._merge_and_validate_detections(image, image_candidates)
        
        logger.info(f"Detected {len(image_elements)} image regions")
        
        if DEBUG.get('save_intermediate_steps', False):
            self._save_debug_visualization(image, image_elements)
        
        return image_elements
    
    def _create_exclusion_mask(self, image_shape: Tuple[int, int, int],
                              text_bboxes: List[BoundingBox] = None,
                              shape_bboxes: List[BoundingBox] = None) -> np.ndarray:
        """Create mask of regions to exclude from image detection"""
        mask = np.zeros(image_shape[:2], dtype=np.uint8)
        
        all_bboxes = []
        if text_bboxes:
            all_bboxes.extend(text_bboxes)
        if shape_bboxes:
            all_bboxes.extend(shape_bboxes)
        
        for bbox in all_bboxes:
            mask[bbox.y:bbox.y2, bbox.x:bbox.x2] = 255
        
        return mask
    
    def _detect_by_color_variance(self, image: np.ndarray, 
                                  exclusion_mask: np.ndarray) -> List[BoundingBox]:
        """Detect images based on color variance (photos have high variance)"""
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        
        # Calculate local variance
        kernel_size = 15
        variance_map = np.zeros(image.shape[:2], dtype=np.float32)
        
        for i in range(3):
            channel = lab[:, :, i].astype(np.float32)
            mean = cv2.blur(channel, (kernel_size, kernel_size))
            sqr_mean = cv2.blur(channel**2, (kernel_size, kernel_size))
            variance_map += sqr_mean - mean**2
        
        # Normalize
        variance_map = cv2.normalize(variance_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # Threshold to find high variance regions
        _, thresh = cv2.threshold(variance_map, 100, 255, cv2.THRESH_BINARY)
        
        # Apply exclusion mask
        thresh = cv2.bitwise_and(thresh, cv2.bitwise_not(exclusion_mask))
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        min_size = self.config.get('min_image_size', 100)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w >= min_size and h >= min_size:
                bboxes.append(BoundingBox(x, y, w, h, label='image'))
        
        return bboxes
    
    def _detect_by_edge_density(self, image: np.ndarray,
                                exclusion_mask: np.ndarray) -> List[BoundingBox]:
        """Detect images based on edge density"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Apply exclusion mask
        edges = cv2.bitwise_and(edges, cv2.bitwise_not(exclusion_mask))
        
        # Calculate local edge density
        kernel_size = 20
        kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size**2)
        edge_density = cv2.filter2D(edges.astype(np.float32), -1, kernel)
        
        # Threshold
        edge_density = cv2.normalize(edge_density, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, thresh = cv2.threshold(edge_density, 30, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        min_size = self.config.get('min_image_size', 100)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w >= min_size and h >= min_size:
                bboxes.append(BoundingBox(x, y, w, h, label='image'))
        
        return bboxes
    
    def _detect_by_texture(self, image: np.ndarray,
                          exclusion_mask: np.ndarray) -> List[BoundingBox]:
        """Detect images based on texture complexity"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Calculate local binary pattern (simplified)
        kernel_size = 15
        mean = cv2.blur(gray.astype(np.float32), (kernel_size, kernel_size))
        
        # Calculate texture measure (standard deviation)
        sqr_mean = cv2.blur(gray.astype(np.float32)**2, (kernel_size, kernel_size))
        texture = np.sqrt(np.maximum(sqr_mean - mean**2, 0))
        
        # Normalize and threshold
        texture = cv2.normalize(texture, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, thresh = cv2.threshold(texture, 50, 255, cv2.THRESH_BINARY)
        
        # Apply exclusion mask
        thresh = cv2.bitwise_and(thresh, cv2.bitwise_not(exclusion_mask))
        
        # Morphological operations to connect nearby regions
        kernel = np.ones((10, 10), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        min_size = self.config.get('min_image_size', 100)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w >= min_size and h >= min_size:
                bboxes.append(BoundingBox(x, y, w, h, label='image'))
        
        return bboxes
    
    def _merge_and_validate_detections(self, image: np.ndarray,
                                       candidates: List[BoundingBox]) -> List[ImageElement]:
        """Merge overlapping detections and validate"""
        from utils import merge_overlapping_boxes
        
        # Merge overlapping boxes
        merged = merge_overlapping_boxes(candidates, iou_threshold=0.3)
        
        # Create ImageElement objects with extracted data
        image_elements = []
        for bbox in merged:
            # Extract image data
            img_data = image[bbox.y:bbox.y2, bbox.x:bbox.x2].copy()
            
            # Determine if it's a photo or graphic
            is_photo = self._is_photographic(img_data)
            
            # Extract dominant colors
            dominant_colors = self._extract_dominant_colors(img_data)
            
            element = ImageElement(
                bbox=bbox,
                image_data=img_data,
                is_photo=is_photo,
                dominant_colors=dominant_colors
            )
            image_elements.append(element)
        
        return image_elements
    
    def _is_photographic(self, image_data: np.ndarray) -> bool:
        """Determine if image is photographic or graphic"""
        # Calculate color diversity
        unique_colors = len(np.unique(image_data.reshape(-1, 3), axis=0))
        total_pixels = image_data.shape[0] * image_data.shape[1]
        
        color_ratio = unique_colors / total_pixels
        
        # Photos typically have more unique colors
        return color_ratio > 0.1
    
    def _extract_dominant_colors(self, image_data: np.ndarray, n_colors: int = 5) -> List[Tuple[int, int, int]]:
        """Extract dominant colors using k-means clustering"""
        # Reshape image
        pixels = image_data.reshape(-1, 3).astype(np.float32)
        
        # Use k-means to find dominant colors
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
        _, labels, centers = cv2.kmeans(pixels, n_colors, None, criteria, 10, 
                                        cv2.KMEANS_PP_CENTERS)
        
        # Convert to int tuples
        centers = centers.astype(int)
        dominant_colors = [tuple(color) for color in centers]
        
        return dominant_colors
    
    def _save_debug_visualization(self, image: np.ndarray, image_elements: List[ImageElement]):
        """Save visualization of detected images"""
        debug_img = image.copy()
        
        for i, element in enumerate(image_elements):
            bbox = element.bbox
            color = (255, 0, 0) if element.is_photo else (0, 0, 255)
            
            # Draw bounding box
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 2)
            
            # Add label
            label_type = "Photo" if element.is_photo else "Graphic"
            label = f"Img {i+1}: {label_type}"
            cv2.putText(debug_img, label, (bbox.x, bbox.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        save_debug_image(debug_img, '03_image_detection.png', DEBUG.get('output_dir', './debug_output'))
