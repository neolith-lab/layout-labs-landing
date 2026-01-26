"""
Image detection and processing module
Steps 3, 4, 5: Image bounding box detection, removal, and optional SVG conversion
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import logging
from dataclasses import dataclass

from utils import BoundingBox, save_debug_image, calculate_dominant_color, inpaint_image
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
                     shape_bboxes: List[BoundingBox] = None) -> Tuple[List[ImageElement], List[ImageElement]]:
        """
        Detect embedded images in the infographic
        
        Args:
            image: Input image
            text_bboxes: Already detected text regions to exclude
            shape_bboxes: Already detected shape regions to exclude
        
        Returns:
            Tuple of (kept_images, filtered_images)
            - kept_images: Actual images/icons to include in SVG
            - filtered_images: Container-like detections that were filtered out
        """
        logger.info("Detecting embedded images...")
        
        # Create exclusion mask
        exclusion_mask = self._create_exclusion_mask(image.shape, text_bboxes, shape_bboxes)
        
        # Detect image regions using various methods
        image_candidates = []
        
        # Method 1: Color variance analysis (detects photos/complex graphics)
        image_candidates.extend(self._detect_by_color_variance(image, exclusion_mask))
        
        # Method 2: Edge density analysis (detects complex graphics)
        image_candidates.extend(self._detect_by_edge_density(image, exclusion_mask))
        
        # Method 3: Texture analysis (detects textured images)
        image_candidates.extend(self._detect_by_texture(image, exclusion_mask))
        
        # Method 4: Line icon detection (NEW - detects simple line icons/logos)
        image_candidates.extend(self._detect_by_line_icons(image, exclusion_mask))
        
        # Merge overlapping detections
        all_image_elements = self._merge_and_validate_detections(image, image_candidates)
        
        logger.info(f"Detected {len(all_image_elements)} total image regions")
        
        # Filter out container-like detections
        kept_images, filtered_images = self._filter_container_like_images(image, all_image_elements)
        
        logger.info(f"After filtering: {len(kept_images)} kept, {len(filtered_images)} filtered (likely containers)")
        
        if DEBUG.get('save_intermediate_steps', False):
            self._save_debug_visualization(image, kept_images, filtered_images)
        
        return kept_images, filtered_images
    
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
        
        # Threshold to find high variance regions - LOWERED threshold for better detection
        variance_threshold = self.config.get('color_variance_threshold', 70)
        _, thresh = cv2.threshold(variance_map, variance_threshold, 255, cv2.THRESH_BINARY)
        
        # Apply exclusion mask
        thresh = cv2.bitwise_and(thresh, cv2.bitwise_not(exclusion_mask))
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        min_size = self.config.get('min_image_size', 30)
        
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
        
        # Threshold - LOWERED from 30 to catch simpler icons
        edge_threshold = self.config.get('edge_density_threshold', 15)
        edge_density = cv2.normalize(edge_density, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, thresh = cv2.threshold(edge_density, edge_threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        min_size = self.config.get('min_image_size', 30)
        
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
        
        # Normalize and threshold - LOWERED threshold for better detection
        texture_threshold = self.config.get('texture_threshold', 35)
        texture = cv2.normalize(texture, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, thresh = cv2.threshold(texture, texture_threshold, 255, cv2.THRESH_BINARY)
        
        # Apply exclusion mask
        thresh = cv2.bitwise_and(thresh, cv2.bitwise_not(exclusion_mask))
        
        # Morphological operations to connect nearby regions
        kernel = np.ones((10, 10), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        min_size = self.config.get('min_image_size', 30)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w >= min_size and h >= min_size:
                bboxes.append(BoundingBox(x, y, w, h, label='image'))
        
        return bboxes
    
    def _detect_by_line_icons(self, image: np.ndarray,
                              exclusion_mask: np.ndarray) -> List[BoundingBox]:
        """
        Detect simple line icons/logos that other methods miss
        
        This method targets:
        - Simple line drawings
        - Monochrome icons
        - Icons with thin strokes on uniform backgrounds
        
        Strategy:
        1. Use MULTIPLE adaptive thresholding variations (works well for line art)
        2. Find contours of reasonable size
        3. Filter by shape characteristics with RELAXED parameters
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # IMPROVED: Try MULTIPLE adaptive thresholding variations
        # This catches icons with different stroke widths and contrasts
        thresh1 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 11, 2)
        
        thresh2 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 15, 2)
        
        thresh3 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 21, 3)
        
        # NEW: Add mean-based adaptive threshold for different lighting
        thresh4 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                        cv2.THRESH_BINARY_INV, 15, 3)
        
        # NEW: Also try with smaller C value for lower contrast icons
        thresh5 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 11, 1)
        
        # Combine ALL thresholds to catch maximum variations
        combined = cv2.bitwise_or(thresh1, thresh2)
        combined = cv2.bitwise_or(combined, thresh3)
        combined = cv2.bitwise_or(combined, thresh4)
        combined = cv2.bitwise_or(combined, thresh5)
        
        # Apply exclusion mask
        combined = cv2.bitwise_and(combined, cv2.bitwise_not(exclusion_mask))
        
        # Morphological operations to connect icon parts
        kernel_small = np.ones((3, 3), np.uint8)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_small)
        
        # Dilate slightly to merge nearby components - REDUCED for tighter bboxes
        kernel_dilate = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(combined, kernel_dilate, iterations=1)
        
        # Find contours
        contours, hierarchy = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        min_icon_size = self.config.get('min_icon_size', 20)
        max_icon_size = self.config.get('max_icon_size', 150)
        min_fill_ratio = self.config.get('min_fill_ratio', 0.05)  # LOWERED from 0.1
        min_contrast = self.config.get('min_contrast_std', 5)  # LOWERED from 10
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size - icons are typically small to medium
            if w < min_icon_size or h < min_icon_size:
                continue
            if w > max_icon_size and h > max_icon_size:
                continue  # Too large for an icon
            
            # Filter by aspect ratio - icons are usually not too elongated
            aspect_ratio = max(w, h) / (min(w, h) + 1)
            if aspect_ratio > 4.0:
                continue  # Too elongated
            
            # Check if it has reasonable fill (not just noise) - RELAXED threshold
            area = cv2.contourArea(contour)
            bbox_area = w * h
            fill_ratio = area / bbox_area if bbox_area > 0 else 0
            
            if fill_ratio < min_fill_ratio:
                continue  # Too sparse, likely noise
            
            # Additional check: verify there's actual content in the region - RELAXED threshold
            region = gray[y:y+h, x:x+w]
            if region.size > 0:
                # Check contrast - icons should have some contrast
                region_std = np.std(region)
                if region_std < min_contrast:
                    continue  # Too uniform, not an icon
            
            bboxes.append(BoundingBox(x, y, w, h, label='icon'))
        
        logger.debug(f"Line icon detection found {len(bboxes)} candidates")
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
    
    def _save_debug_visualization(self, image: np.ndarray, 
                                  kept_images: List[ImageElement],
                                  filtered_images: List[ImageElement]):
        """Save visualization of detected images with color coding"""
        debug_img = image.copy()
        
        # Add summary text at top
        summary = f"Images: Kept={len(kept_images)} (RED) | Filtered={len(filtered_images)} (GREEN)"
        cv2.putText(debug_img, summary, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 3)
        cv2.putText(debug_img, summary, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
        
        # Track used label positions to avoid overlap
        used_regions = []
        
        def find_label_position(bbox, label_height=65):
            """Find non-overlapping position for label"""
            # Try positions in order: top, bottom, left, right
            positions = [
                (bbox.x, bbox.y - label_height),  # Top
                (bbox.x, bbox.y2 + 5),            # Bottom
                (bbox.x - 260, bbox.y),           # Left (wider for 4 lines)
                (bbox.x2 + 5, bbox.y),            # Right
            ]
            
            for x, y in positions:
                # Clamp to image bounds
                y = max(45, min(y, image.shape[0] - label_height))
                x = max(0, min(x, image.shape[1] - 260))
                
                # Check if this position overlaps with existing labels
                proposed_region = (x, y, x + 260, y + label_height)
                
                overlaps = False
                for used in used_regions:
                    if not (proposed_region[2] < used[0] or  # right of used
                           proposed_region[0] > used[2] or   # left of used
                           proposed_region[3] < used[1] or   # above used
                           proposed_region[1] > used[3]):    # below used
                        overlaps = True
                        break
                
                if not overlaps:
                    used_regions.append(proposed_region)
                    return x, y
            
            # Fallback: use original position even if overlapping
            x, y = bbox.x, max(45, bbox.y - label_height)
            used_regions.append((x, y, x + 260, y + label_height))
            return x, y
        
        # Draw kept images in RED (these will be in final SVG)
        for i, element in enumerate(kept_images):
            bbox = element.bbox
            color = (0, 0, 255)  # RED in BGR
            
            # Draw bounding box (thicker for visibility)
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 3)
            
            # Get debug info if available
            debug_info = getattr(element, 'debug_info', {})
            area_ratio = debug_info.get('area_ratio', 0)
            size_score = debug_info.get('size_score', 0)
            color_score = debug_info.get('color_score', 0)
            edge_score = debug_info.get('edge_score', 0)
            fill_score = debug_info.get('fill_score', 0)
            edge_complexity = debug_info.get('edge_complexity', 0)
            edge_density = debug_info.get('edge_density', 0)
            edge_variance = debug_info.get('edge_variance', 0)
            unique_colors = debug_info.get('unique_colors', 0)
            fill_ratio = debug_info.get('fill_ratio', 0)
            
            # If not in debug_info, calculate for display
            if unique_colors == 0:
                unique_colors = len(np.unique(element.image_data.reshape(-1, 3), axis=0))
            if fill_ratio == 0:
                fill_ratio = self._calculate_fill_ratio(element.image_data)
            
            # Extract total score from label if available
            total_score = bbox.label.split(':')[1] if ':' in bbox.label else '?'
            
            # Build annotation with 4 lines showing all scores
            line1 = f"{bbox.w}x{bbox.h} | clr:{unique_colors} | fill:{fill_ratio:.0%} | TOTAL:{total_score}"
            line2 = f"Size:{size_score} | Color:{color_score} | Edge:{edge_score} | Fill:{fill_score}"
            line3 = f"area:{area_ratio:.1%} | edge_cmplx:{edge_complexity:.3f}"
            line4 = f"edge_dens:{edge_density:.3f} | edge_var:{edge_variance:.3f}"
            
            # Find non-overlapping position for label
            label_x, label_y = find_label_position(bbox, label_height=65)
            
            # Draw label background (taller for 4 lines)
            cv2.rectangle(debug_img, (label_x, label_y), (label_x + 260, label_y + 65), color, -1)
            
            # Draw labels (4 lines)
            cv2.putText(debug_img, line1, (label_x + 2, label_y + 14),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
            cv2.putText(debug_img, line2, (label_x + 2, label_y + 29),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
            cv2.putText(debug_img, line3, (label_x + 2, label_y + 44),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
            cv2.putText(debug_img, line4, (label_x + 2, label_y + 59),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
        
        # Draw filtered images in GREEN (likely containers)
        for i, element in enumerate(filtered_images):
            bbox = element.bbox
            color = (0, 255, 0)  # GREEN in BGR
            
            # Draw bounding box (thicker for visibility)
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 3)
            
            # Get debug info if available
            debug_info = getattr(element, 'debug_info', {})
            area_ratio = debug_info.get('area_ratio', 0)
            size_score = debug_info.get('size_score', 0)
            color_score = debug_info.get('color_score', 0)
            edge_score = debug_info.get('edge_score', 0)
            fill_score = debug_info.get('fill_score', 0)
            edge_complexity = debug_info.get('edge_complexity', 0)
            edge_density = debug_info.get('edge_density', 0)
            edge_variance = debug_info.get('edge_variance', 0)
            unique_colors = debug_info.get('unique_colors', 0)
            fill_ratio = debug_info.get('fill_ratio', 0)
            
            # If not in debug_info, calculate for display
            if unique_colors == 0:
                unique_colors = len(np.unique(element.image_data.reshape(-1, 3), axis=0))
            if fill_ratio == 0:
                fill_ratio = self._calculate_fill_ratio(element.image_data)
            
            # Extract total score from label
            total_score = bbox.label.split(':')[1] if ':' in bbox.label else '?'
            
            # Build annotation with 4 lines showing all scores
            line1 = f"{bbox.w}x{bbox.h} | clr:{unique_colors} | fill:{fill_ratio:.0%} | TOTAL:{total_score}"
            line2 = f"Size:{size_score} | Color:{color_score} | Edge:{edge_score} | Fill:{fill_score}"
            line3 = f"area:{area_ratio:.1%} | edge_cmplx:{edge_complexity:.3f}"
            line4 = f"edge_dens:{edge_density:.3f} | edge_var:{edge_variance:.3f}"
            
            # Find non-overlapping position for label
            label_x, label_y = find_label_position(bbox, label_height=65)
            
            # Draw label background (taller for 4 lines)
            cv2.rectangle(debug_img, (label_x, label_y), (label_x + 260, label_y + 65), color, -1)
            
            # Draw labels (4 lines)
            cv2.putText(debug_img, line1, (label_x + 2, label_y + 14),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
            cv2.putText(debug_img, line2, (label_x + 2, label_y + 29),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
            cv2.putText(debug_img, line3, (label_x + 2, label_y + 44),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
            cv2.putText(debug_img, line4, (label_x + 2, label_y + 59),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
        
        save_debug_image(debug_img, '03_image_detection.png', DEBUG.get('output_dir', './debug_output'))
        
        # Also save Canny edge debug visualization
        self._save_canny_edge_debug(image, kept_images, filtered_images)
    
    def _save_canny_edge_debug(self, image: np.ndarray,
                               kept_images: List[ImageElement],
                               filtered_images: List[ImageElement]):
        """
        Save a debug visualization showing Canny edge detection with edge metrics annotated.
        
        This shows the edge map of the full image with bounding boxes for each detected
        element and their edge_density, edge_variance, edge_complexity, and edge_score values.
        """
        # Convert full image to grayscale and compute Canny edges
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        # Convert edges to 3-channel BGR for annotation (white edges on black)
        debug_img = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        
        # Add title
        title = "Canny Edge Detection - Edge Metrics per Region"
        cv2.putText(debug_img, title, (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Track used label positions to avoid overlap
        used_regions = []
        
        def find_label_position(bbox, label_height=50):
            """Find non-overlapping position for label"""
            positions = [
                (bbox.x, bbox.y - label_height),  # Top
                (bbox.x, bbox.y2 + 5),            # Bottom
                (bbox.x - 220, bbox.y),           # Left
                (bbox.x2 + 5, bbox.y),            # Right
            ]
            
            for x, y in positions:
                y = max(35, min(y, image.shape[0] - label_height))
                x = max(0, min(x, image.shape[1] - 220))
                
                proposed_region = (x, y, x + 220, y + label_height)
                
                overlaps = False
                for used in used_regions:
                    if not (proposed_region[2] < used[0] or
                           proposed_region[0] > used[2] or
                           proposed_region[3] < used[1] or
                           proposed_region[1] > used[3]):
                        overlaps = True
                        break
                
                if not overlaps:
                    used_regions.append(proposed_region)
                    return x, y
            
            x, y = bbox.x, max(35, bbox.y - label_height)
            used_regions.append((x, y, x + 220, y + label_height))
            return x, y
        
        all_elements = kept_images + filtered_images
        
        for element in all_elements:
            bbox = element.bbox
            debug_info = getattr(element, 'debug_info', {})
            
            # Determine color based on kept vs filtered
            is_kept = element in kept_images
            color = (0, 0, 255) if is_kept else (0, 255, 0)  # RED for kept, GREEN for filtered
            
            # Draw bounding box on edge image
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 2)
            
            # Get edge metrics
            edge_complexity = debug_info.get('edge_complexity', 0)
            edge_density = debug_info.get('edge_density', 0)
            edge_variance = debug_info.get('edge_variance', 0)
            edge_score = debug_info.get('edge_score', 0)
            
            # Build annotation lines
            status = "KEPT" if is_kept else "FILTERED"
            line1 = f"{status} {bbox.w}x{bbox.h}"
            line2 = f"dens:{edge_density:.4f} | var:{edge_variance:.3f}"
            line3 = f"cmplx:{edge_complexity:.4f} | Score:{edge_score}"
            
            # Find non-overlapping position for label
            label_x, label_y = find_label_position(bbox, label_height=50)
            
            # Draw label background
            cv2.rectangle(debug_img, (label_x, label_y), (label_x + 220, label_y + 50), color, -1)
            
            # Draw labels (3 lines)
            text_color = (255, 255, 255) if is_kept else (0, 0, 0)
            cv2.putText(debug_img, line1, (label_x + 2, label_y + 14),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_color, 1)
            cv2.putText(debug_img, line2, (label_x + 2, label_y + 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_color, 1)
            cv2.putText(debug_img, line3, (label_x + 2, label_y + 46),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_color, 1)
        
        # Add legend at bottom
        legend_y = image.shape[0] - 30
        cv2.putText(debug_img, "RED=Kept Images | GREEN=Filtered Containers | Edge values on INPAINTED regions",
                   (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        save_debug_image(debug_img, '03b_canny_edge_metrics.png', DEBUG.get('output_dir', './debug_output'))

    def _filter_container_like_images(self, image: np.ndarray,
                                      image_elements: List[ImageElement]) -> Tuple[List[ImageElement], List[ImageElement]]:
        """
        Filter out container-like detections using heuristics
        
        Heuristics (UPDATED - Rebalanced to total 100 points):
        1. Size: > 2% of total image area → likely container (0-40 points) - HIGHEST WEIGHT
           - NEW: Minimum size 50x50 for containers (smaller = definitely not container)
        2. Color simplicity: < 1500 unique colors → likely container (0-10 points)
           - NEW: Inpaints nested images first for accurate color count
           - NEW: Uses tolerance=5 to ignore anti-aliasing artifacts
        3. Edge simplicity: low edge complexity → likely container (0-20 points)
           - NEW: Calculated on inpainted image (nested images removed)
           - FIXED: Low edge density (fewer edges) = HIGH container score
        4. Fill ratio: > 70% uniform fill → likely container (0-30 points)
           - NEW: Calculated on inpainted image (nested images removed)
        
        Total possible: 100 points
        Score ≥ 35 → Filter as container
        
        Returns:
            (kept_images, filtered_images)
        """
        total_area = image.shape[0] * image.shape[1]
        size_threshold = self.config.get('container_size_threshold', 0.08)
        min_colors_threshold = self.config.get('container_min_unique_colors', 1500)
        edge_threshold = self.config.get('container_edge_simplicity_threshold', 0.4)
        fill_ratio_threshold = self.config.get('container_fill_ratio_threshold', 0.70)
        score_threshold = self.config.get('container_score_threshold', 35)
        min_container_dimension = 50  # Minimum 50x50 to be considered a container
        inpaint_radius = self.config.get('inpaint_radius', 5)
        
        kept_images = []
        filtered_images = []
        
        # Step 1: Build parent-child relationships (which images are nested inside others)
        nested_info = self._find_nested_images(image_elements)
        
        for element in image_elements:
            container_score = 0
            debug_info = {}
            
            # Pre-check: Containers must be at least 50x50
            # Anything smaller is definitely an icon/image, not a container
            if element.bbox.w < min_container_dimension or element.bbox.h < min_container_dimension:
                kept_images.append(element)
                element.bbox.label = "score:0-small"
                logger.debug(f"Kept (too small for container): {element.bbox.w}x{element.bbox.h}")
                continue
            
            # Heuristic 1: Size check (0-40 points) - HIGHEST WEIGHT
            # Size doesn't need inpainting - it's based on bbox area
            area_ratio = element.bbox.area / total_area
            debug_info['area_ratio'] = area_ratio
            if area_ratio > size_threshold:
                # Larger regions get higher scores
                # Formula: max 40 points at 12% area (threshold is 2%)
                size_score = min(40, int((area_ratio - size_threshold) * 400))
                container_score += size_score
                debug_info['size_score'] = size_score
            
            # Step 2: Get inpainted image data (nested images removed) for remaining heuristics
            # This gives us the "true" container appearance without embedded content
            element_idx = self._get_element_index(element, image_elements)
            inpainted_data = self._get_inpainted_image_data(
                element, element_idx, nested_info, image_elements, inpaint_radius
            )
            
            # Heuristic 2: Color uniformity (0-10 points)
            # Calculate unique colors on INPAINTED image
            unique_colors = self._count_unique_colors_with_tolerance(
                inpainted_data.reshape(-1, 3), tolerance=5
            )
            debug_info['unique_colors'] = unique_colors
            if unique_colors < min_colors_threshold:
                color_score = int(10 * (1 - unique_colors / min_colors_threshold))
                container_score += color_score
                debug_info['color_score'] = color_score
            
            # Heuristic 3: Edge simplicity (0-20 points)
            # Calculate edge complexity on INPAINTED image (get detailed values)
            edge_complexity, edge_density, edge_variance = self._calculate_edge_complexity(
                inpainted_data, return_details=True
            )
            debug_info['edge_complexity'] = edge_complexity
            debug_info['edge_density'] = edge_density
            debug_info['edge_variance'] = edge_variance
            if edge_complexity < edge_threshold:
                edge_score = int(20 * (1 - edge_complexity / edge_threshold))
                container_score += edge_score
                debug_info['edge_score'] = edge_score
            
            # Heuristic 4: Fill ratio (0-30 points)
            # Calculate fill ratio on INPAINTED image
            fill_ratio = self._calculate_fill_ratio(inpainted_data)
            debug_info['fill_ratio'] = fill_ratio
            if fill_ratio > fill_ratio_threshold:
                fill_score = int(30 * ((fill_ratio - fill_ratio_threshold) / (1.0 - fill_ratio_threshold)))
                container_score += fill_score
                debug_info['fill_score'] = fill_score
            
            # Store debug info in element for visualization
            element.debug_info = debug_info
            
            # Store scores for debugging
            element.bbox.label = f"score:{container_score}"
            
            # Classify based on combined score
            if container_score >= score_threshold:
                filtered_images.append(element)
                logger.debug(f"Filtered container-like: {element.bbox.w}x{element.bbox.h}, "
                           f"area={area_ratio:.3f}, colors={unique_colors}, "
                           f"edge={edge_complexity:.3f}, fill={fill_ratio:.3f}, score={container_score}")
            else:
                kept_images.append(element)
                logger.debug(f"Kept image: {element.bbox.w}x{element.bbox.h}, "
                           f"colors={unique_colors}, fill={fill_ratio:.3f}, score={container_score}")
        
        return kept_images, filtered_images
    
    def _find_nested_images(self, image_elements: List[ImageElement]) -> Dict[int, List[int]]:
        """
        Find which images are nested inside other images.
        
        Returns:
            Dictionary mapping parent index to list of child indices
            e.g., {0: [2, 3, 5]} means element 0 contains elements 2, 3, and 5
        """
        nested_info = {}
        
        for i, parent in enumerate(image_elements):
            children = []
            parent_bbox = parent.bbox
            
            for j, child in enumerate(image_elements):
                if i == j:
                    continue
                    
                child_bbox = child.bbox
                
                # Check if child is fully contained within parent
                if (child_bbox.x >= parent_bbox.x and 
                    child_bbox.y >= parent_bbox.y and
                    child_bbox.x2 <= parent_bbox.x2 and 
                    child_bbox.y2 <= parent_bbox.y2):
                    children.append(j)
            
            if children:
                nested_info[i] = children
                
        return nested_info
    
    def _get_element_index(self, element: ImageElement, all_elements: List[ImageElement]) -> Optional[int]:
        """Get the index of an element in the list"""
        for i, el in enumerate(all_elements):
            if el is element:
                return i
        return None
    
    def _get_inpainted_image_data(
        self,
        element: ImageElement,
        element_idx: Optional[int],
        nested_info: Dict[int, List[int]],
        all_elements: List[ImageElement],
        inpaint_radius: int = 5
    ) -> np.ndarray:
        """
        Get image data with nested images inpainted (removed and filled).
        
        This provides the "true" appearance of a container without embedded icons/images.
        Uses the same Telea inpainting method as text removal.
        
        Args:
            element: The parent element
            element_idx: Index of the element in all_elements
            nested_info: Dictionary of parent -> [children] relationships
            all_elements: All detected image elements
            inpaint_radius: Radius for inpainting algorithm
            
        Returns:
            Image data with nested images inpainted
        """
        # If no nested children, return original image data
        if element_idx is None or element_idx not in nested_info:
            return element.image_data.copy()
        
        # Create a copy to work with
        image_data = element.image_data.copy()
        h, w = image_data.shape[:2]
        
        # Create a mask for inpainting (255 = areas to inpaint)
        inpaint_mask = np.zeros((h, w), dtype=np.uint8)
        
        # Mark all nested child regions in the mask
        parent_bbox = element.bbox
        for child_idx in nested_info[element_idx]:
            child = all_elements[child_idx]
            child_bbox = child.bbox
            
            # Convert child bbox to parent-relative coordinates
            rel_x = child_bbox.x - parent_bbox.x
            rel_y = child_bbox.y - parent_bbox.y
            rel_x2 = rel_x + child_bbox.w
            rel_y2 = rel_y + child_bbox.h
            
            # Clamp to valid range
            rel_x = max(0, rel_x)
            rel_y = max(0, rel_y)
            rel_x2 = min(w, rel_x2)
            rel_y2 = min(h, rel_y2)
            
            # Mark this region for inpainting
            inpaint_mask[rel_y:rel_y2, rel_x:rel_x2] = 255
        
        # If no regions to inpaint, return original
        if np.count_nonzero(inpaint_mask) == 0:
            return image_data
        
        # Inpaint using Telea method (same as text inpainting)
        try:
            inpainted = inpaint_image(image_data, inpaint_mask, method='telea', radius=inpaint_radius)
            logger.debug(f"Inpainted {len(nested_info[element_idx])} nested regions in element {element_idx}")
            return inpainted
        except Exception as e:
            logger.warning(f"Inpainting failed: {e}, using original image")
            return image_data
    
    def _calculate_unique_colors_excluding_nested(
        self, 
        element: ImageElement, 
        nested_info: Dict[int, List[int]],
        all_elements: List[ImageElement]
    ) -> int:
        """
        Calculate unique colors in an element, excluding pixels from nested child images.
        
        This gives a more accurate color count for containers - the container's actual
        colors without the embedded icons/images inflating the count.
        """
        # Find this element's index
        element_idx = None
        for i, el in enumerate(all_elements):
            if el is element:
                element_idx = i
                break
        
        # If this element has no children, use standard calculation
        if element_idx is None or element_idx not in nested_info:
            return len(np.unique(element.image_data.reshape(-1, 3), axis=0))
        
        # Create a mask for this element's region
        h, w = element.image_data.shape[:2]
        mask = np.ones((h, w), dtype=bool)
        
        # Mask out all nested child regions
        parent_bbox = element.bbox
        for child_idx in nested_info[element_idx]:
            child = all_elements[child_idx]
            child_bbox = child.bbox
            
            # Convert child bbox to parent-relative coordinates
            rel_x = child_bbox.x - parent_bbox.x
            rel_y = child_bbox.y - parent_bbox.y
            rel_x2 = rel_x + child_bbox.w
            rel_y2 = rel_y + child_bbox.h
            
            # Clamp to valid range
            rel_x = max(0, rel_x)
            rel_y = max(0, rel_y)
            rel_x2 = min(w, rel_x2)
            rel_y2 = min(h, rel_y2)
            
            # Mask out this child region
            mask[rel_y:rel_y2, rel_x:rel_x2] = False
        
        # Get pixels only from non-masked (non-child) regions
        masked_pixels = element.image_data[mask]
        
        if masked_pixels.size == 0:
            return 0
            
        # Reshape to (N, 3) for unique color counting with tolerance
        masked_pixels = masked_pixels.reshape(-1, 3)
        unique_colors = self._count_unique_colors_with_tolerance(masked_pixels, tolerance=5)
        
        logger.debug(f"Element {element_idx}: {len(nested_info[element_idx])} nested images, "
                    f"unique colors (excluding nested, tolerance=5): {unique_colors}")
        
        return unique_colors
    
    def _count_unique_colors_with_tolerance(self, pixels: np.ndarray, tolerance: int = 5) -> int:
        """
        Count unique colors with tolerance - colors within 'tolerance' distance are considered same.
        
        This handles anti-aliasing and subtle gradients more accurately.
        E.g., RGB(100,150,200) and RGB(101,150,201) are the same color with tolerance=5
        
        Args:
            pixels: Nx3 array of RGB pixels
            tolerance: Minimum distance to consider colors different
            
        Returns:
            Number of unique colors
        """
        if pixels.size == 0:
            return 0
        
        # For very small regions, just use unique count (faster)
        if len(pixels) < 100:
            return len(np.unique(pixels, axis=0))
        
        # Use k-means clustering to group similar colors
        # Estimate k based on image complexity
        max_clusters = min(500, len(pixels) // 10)  # Cap at 500 unique colors
        
        try:
            # Convert to float for k-means
            pixels_float = pixels.astype(np.float32)
            
            # Use tolerance to determine number of clusters
            # Start with a reasonable estimate
            k = max(2, min(max_clusters, len(pixels) // 50))
            
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1.0)
            _, labels, centers = cv2.kmeans(pixels_float, k, None, criteria, 3, 
                                            cv2.KMEANS_PP_CENTERS)
            
            # Now merge clusters that are within tolerance distance
            centers_int = centers.astype(np.int32)
            unique_centers = []
            
            for center in centers_int:
                # Check if this center is similar to any existing unique center
                is_unique = True
                for unique_center in unique_centers:
                    # Calculate Euclidean distance in RGB space
                    distance = np.sqrt(np.sum((center - unique_center) ** 2))
                    if distance < tolerance:
                        is_unique = False
                        break
                
                if is_unique:
                    unique_centers.append(center)
            
            return len(unique_centers)
            
        except Exception as e:
            logger.warning(f"K-means clustering failed, using fallback: {e}")
            # Fallback: simple unique count
            return len(np.unique(pixels, axis=0))
    
    def _calculate_fill_ratio(self, image_data: np.ndarray) -> float:
        """
        Calculate what percentage of the region is uniform (single color)
        
        Containers typically have 70-95% uniform fill
        Photos/icons typically have 10-50% uniform (more varied)
        
        Returns:
            Float between 0-1 representing fill uniformity
        """
        if image_data.size == 0:
            return 0.0
        
        # Reshape to list of pixels
        pixels = image_data.reshape(-1, 3)
        total_pixels = len(pixels)
        
        if total_pixels == 0:
            return 0.0
        
        # Find the most common color (with tolerance for similar colors)
        # Use k-means with k=3 to find dominant color clusters
        try:
            pixels_float = pixels.astype(np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1.0)
            _, labels, centers = cv2.kmeans(pixels_float, 3, None, criteria, 5, 
                                            cv2.KMEANS_PP_CENTERS)
            
            # Count pixels in each cluster
            unique, counts = np.unique(labels, return_counts=True)
            
            # Get the largest cluster (dominant color)
            max_count = np.max(counts)
            fill_ratio = max_count / total_pixels
            
            return fill_ratio
            
        except Exception as e:
            # Fallback: simple histogram approach
            # Convert to single value per pixel (for faster processing)
            gray = cv2.cvtColor(image_data, cv2.COLOR_BGR2GRAY) if len(image_data.shape) == 3 else image_data
            
            # Calculate histogram
            hist = cv2.calcHist([gray], [0], None, [32], [0, 256])  # 32 bins
            
            # Find max bin
            max_bin = np.max(hist)
            fill_ratio = max_bin / total_pixels
            
            return fill_ratio
        
        return kept_images, filtered_images
    
    def _calculate_edge_complexity(self, image_data: np.ndarray, return_details: bool = False):
        """
        Calculate edge complexity metric (0-1 range)
        Lower values = simpler edges (like containers)
        Higher values = complex edges (like photos/icons)
        
        FIXED: Low edge density (fewer edges) now correctly contributes to LOW complexity
        
        Components:
        - Edge density: % of pixels that are edges (lower = simpler = container)
        - Edge variance: How spread out edges are (lower = borders only = container)
        
        Args:
            image_data: Image to analyze
            return_details: If True, returns (complexity, density, variance) tuple
            
        Returns:
            If return_details=False: float (complexity)
            If return_details=True: tuple (complexity, edge_density, edge_variance)
        """
        if image_data.size == 0:
            return (0.0, 0.0, 0.0) if return_details else 0.0
        
        # Convert to grayscale
        if len(image_data.shape) == 3:
            gray = cv2.cvtColor(image_data, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_data
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Calculate edge density (what % of pixels are edges)
        edge_pixels = np.count_nonzero(edges)
        total_pixels = edges.shape[0] * edges.shape[1]
        edge_density = edge_pixels / total_pixels
        
        # Calculate edge variance (how spread out edges are)
        # Containers typically have edges only at borders
        # Photos/icons have edges throughout
        if edge_pixels > 0:
            # Get edge pixel coordinates
            edge_coords = np.argwhere(edges > 0)
            if len(edge_coords) > 1:
                # Calculate variance in edge distribution
                variance = np.var(edge_coords, axis=0).mean()
                # Normalize by image size
                max_variance = (gray.shape[0]**2 + gray.shape[1]**2) / 12  # variance of uniform distribution
                edge_variance = min(1.0, variance / max_variance)
            else:
                edge_variance = 0.0
        else:
            edge_variance = 0.0
        
        # Combine metrics: BOTH should be low for containers
        # Low edge density (fewer edges) = simple container
        # Low edge variance (edges at borders) = simple container
        # Average them - both contribute equally
        complexity = (edge_density + edge_variance) / 2
        complexity = edge_density
        
        if return_details:
            return (complexity, edge_density, edge_variance)
        return complexity
