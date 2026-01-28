"""
Background filling module for removed elements
Steps 2, 4, 7: Bounding box removal and background filling
"""

import cv2
import numpy as np
from typing import List, Optional, Dict
import logging

from utils import BoundingBox, create_mask_from_bbox, inpaint_image, save_debug_image
from config import IMAGE_PROCESSING, DEBUG

logger = logging.getLogger(__name__)


class BackgroundFiller:
    """Fill background after removing elements"""
    
    def __init__(self, config: Dict = None):
        self.config = config or IMAGE_PROCESSING
    
    def fill_with_border_average(self, image: np.ndarray, bboxes: List[BoundingBox],
                                  border_width: int = 2) -> np.ndarray:
        """
        Fill bounding box regions with the dominant color just outside each bounding box.
        
        Args:
            image: Input image
            bboxes: List of bounding boxes to fill
            border_width: Width of the border region to sample colors from (default: 2 for tighter sampling)
        
        Returns:
            Image with regions filled using dominant border color
        """
        if not bboxes:
            return image.copy()
        
        logger.info(f"Filling {len(bboxes)} regions with dominant border colors...")
        result = image.copy()
        
        for bbox in bboxes:
            dominant_color = self._get_border_dominant_color(image, bbox, border_width)
            # Fill the bounding box region with the dominant color
            result[bbox.y:bbox.y2, bbox.x:bbox.x2] = dominant_color
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(result, 'text_infilled.png', DEBUG.get('output_dir'))
        
        return result
    
    def _get_border_dominant_color(self, image: np.ndarray, bbox: BoundingBox, 
                                    border_width: int = 2) -> np.ndarray:
        """
        Get the dominant (most common) color of pixels just outside the bounding box.
        Uses color clustering to find the most frequent color, avoiding color mixing.
        
        Args:
            image: Input image
            bbox: Bounding box
            border_width: Width of the border region to sample (smaller = tighter sampling)
        
        Returns:
            Dominant color as numpy array (BGR)
        """
        h, w = image.shape[:2]
        
        # Define the outer boundary (expanded bbox) - use small border_width for tight sampling
        outer_x1 = max(0, bbox.x - border_width)
        outer_y1 = max(0, bbox.y - border_width)
        outer_x2 = min(w, bbox.x2 + border_width)
        outer_y2 = min(h, bbox.y2 + border_width)
        
        # Collect pixels from the border region (outside bbox but inside outer boundary)
        border_pixels = []
        
        # Top border
        if bbox.y > outer_y1:
            top_region = image[outer_y1:bbox.y, outer_x1:outer_x2]
            if top_region.size > 0:
                border_pixels.append(top_region.reshape(-1, 3))
        
        # Bottom border
        if bbox.y2 < outer_y2:
            bottom_region = image[bbox.y2:outer_y2, outer_x1:outer_x2]
            if bottom_region.size > 0:
                border_pixels.append(bottom_region.reshape(-1, 3))
        
        # Left border (excluding corners already counted)
        if bbox.x > outer_x1:
            left_region = image[bbox.y:bbox.y2, outer_x1:bbox.x]
            if left_region.size > 0:
                border_pixels.append(left_region.reshape(-1, 3))
        
        # Right border (excluding corners already counted)
        if bbox.x2 < outer_x2:
            right_region = image[bbox.y:bbox.y2, bbox.x2:outer_x2]
            if right_region.size > 0:
                border_pixels.append(right_region.reshape(-1, 3))
        
        if not border_pixels:
            # Fallback: use the median color of the entire image
            return np.median(image.reshape(-1, 3), axis=0).astype(np.uint8)
        
        all_pixels = np.vstack(border_pixels)
        
        # Find dominant color using clustering
        dominant_color = self._find_dominant_color(all_pixels)
        
        return dominant_color
    
    def _find_dominant_color(self, pixels: np.ndarray, n_clusters: int = 3) -> np.ndarray:
        """
        Find the dominant (most frequent) color in a set of pixels using k-means clustering.
        
        Args:
            pixels: Array of pixel colors (N x 3)
            n_clusters: Number of color clusters to identify
        
        Returns:
            The most common color as numpy array (BGR)
        """
        if len(pixels) < n_clusters:
            # Not enough pixels, just return the mean
            return np.mean(pixels, axis=0).astype(np.uint8)
        
        # Reduce number of clusters if we don't have many unique colors
        unique_colors = np.unique(pixels, axis=0)
        n_clusters = min(n_clusters, len(unique_colors))
        
        if n_clusters == 1:
            return unique_colors[0].astype(np.uint8)
        
        # Use k-means to find color clusters
        pixels_float = pixels.astype(np.float32)
        
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels_float, n_clusters, None, criteria, 
                                         attempts=3, flags=cv2.KMEANS_PP_CENTERS)
        
        # Count pixels in each cluster and find the most common one
        label_counts = np.bincount(labels.flatten(), minlength=n_clusters)
        dominant_cluster = np.argmax(label_counts)
        
        dominant_color = centers[dominant_cluster].astype(np.uint8)
        
        return dominant_color

    def remove_and_fill(self, image: np.ndarray, bboxes: List[BoundingBox],
                       label_filter: Optional[str] = None) -> np.ndarray:
        """
        Remove elements and fill their backgrounds
        
        Args:
            image: Input image
            bboxes: List of bounding boxes to remove
            label_filter: Only remove boxes with this label (None = all)
        
        Returns:
            Image with elements removed and background filled
        """
        if not bboxes:
            return image.copy()
        
        # Filter bboxes if needed
        if label_filter:
            bboxes = [b for b in bboxes if b.label == label_filter]
        
        logger.info(f"Removing and filling {len(bboxes)} regions...")
        
        # Create mask from bounding boxes
        mask = create_mask_from_bbox(image.shape, bboxes)
        
        # Expand mask slightly to ensure complete coverage
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)
        
        # Inpaint the image
        method = self.config.get('background_fill_method', 'inpaint_telea')
        radius = self.config.get('inpaint_radius', 5)
        
        if 'telea' in method.lower():
            filled = inpaint_image(image, mask, 'telea', radius)
        else:
            filled = inpaint_image(image, mask, 'ns', radius)
        
        # Apply additional smoothing at boundaries
        filled = self._smooth_boundaries(filled, mask)
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(mask, 'mask_for_filling.png', DEBUG.get('output_dir'))
            save_debug_image(filled, 'background_filled.png', DEBUG.get('output_dir'))
        
        return filled
    
    def _smooth_boundaries(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Smooth boundaries of inpainted regions"""
        # Create boundary mask
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(mask, kernel, iterations=1)
        boundary = dilated - mask
        
        # Apply Gaussian blur to boundary regions
        blurred = cv2.GaussianBlur(image, (5, 5), 0)
        
        # Blend boundary
        result = image.copy()
        boundary_bool = boundary > 0
        result[boundary_bool] = blurred[boundary_bool]
        
        return result
    
    def progressive_fill(self, image: np.ndarray, bbox_layers: List[List[BoundingBox]]) -> List[np.ndarray]:
        """
        Progressively remove and fill layers of elements
        
        Args:
            image: Input image
            bbox_layers: List of bbox lists, each representing a layer
        
        Returns:
            List of images, each with one more layer removed
        """
        results = [image.copy()]
        current_image = image.copy()
        
        for i, bboxes in enumerate(bbox_layers):
            logger.info(f"Processing layer {i+1}/{len(bbox_layers)}")
            current_image = self.remove_and_fill(current_image, bboxes)
            results.append(current_image.copy())
        
        return results
    
    def smart_fill_with_context(self, image: np.ndarray, bbox: BoundingBox, 
                                context_expansion: int = 20) -> np.ndarray:
        """
        Fill a single region using surrounding context
        
        Args:
            image: Input image
            bbox: Bounding box to fill
            context_expansion: Pixels to expand for context analysis
        
        Returns:
            Image with region filled
        """
        # Expand region for better context
        x1 = max(0, bbox.x - context_expansion)
        y1 = max(0, bbox.y - context_expansion)
        x2 = min(image.shape[1], bbox.x2 + context_expansion)
        y2 = min(image.shape[0], bbox.y2 + context_expansion)
        
        # Extract context region
        context_region = image[y1:y2, x1:x2].copy()
        
        # Create mask for the region within context
        mask = np.zeros(context_region.shape[:2], dtype=np.uint8)
        local_x = bbox.x - x1
        local_y = bbox.y - y1
        mask[local_y:local_y + bbox.h, local_x:local_x + bbox.w] = 255
        
        # Inpaint context region
        filled_region = cv2.inpaint(context_region, mask, 
                                    self.config.get('inpaint_radius', 5),
                                    cv2.INPAINT_TELEA)
        
        # Place back into original image
        result = image.copy()
        result[y1:y2, x1:x2] = filled_region
        
        return result
    
    def clean_container_interiors(self, image: np.ndarray, container_bboxes: List[BoundingBox],
                                   min_artifact_size: int = 100, 
                                   thin_threshold: int = 5) -> np.ndarray:
        """
        Clean the inside of containers by removing small specs and thin artifacts
        that may remain after image/text removal.
        
        Args:
            image: Input image (after text and image removal)
            container_bboxes: List of container bounding boxes to clean
            min_artifact_size: Minimum area (in pixels) for an artifact to be kept
                              Smaller artifacts are removed as specs
            thin_threshold: Maximum thickness for thin artifacts to be removed
        
        Returns:
            Image with cleaned container interiors
        """
        if not container_bboxes:
            return image.copy()
        
        logger.info(f"Cleaning interiors of {len(container_bboxes)} containers...")
        result = image.copy()
        total_artifacts_removed = 0
        
        for bbox in container_bboxes:
            # Extract the container region
            region = result[bbox.y:bbox.y2, bbox.x:bbox.x2].copy()
            
            if region.size == 0:
                continue
            
            # Find the dominant background color of the container
            dominant_color = self._get_border_dominant_color(result, bbox, border_width=3)
            
            # Convert to grayscale for artifact detection
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            
            # Create a mask of pixels that differ significantly from the dominant color
            # Convert dominant color to grayscale for comparison
            dominant_gray = int(0.299 * dominant_color[2] + 0.587 * dominant_color[1] + 0.114 * dominant_color[0])
            
            # Find pixels that are different from background
            diff = np.abs(gray.astype(np.int32) - dominant_gray)
            artifact_mask = (diff > 30).astype(np.uint8) * 255
            
            # Find connected components (artifacts)
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                artifact_mask, connectivity=8
            )
            
            # Create mask for artifacts to remove
            removal_mask = np.zeros_like(artifact_mask)
            
            for i in range(1, num_labels):  # Skip background (label 0)
                area = stats[i, cv2.CC_STAT_AREA]
                width = stats[i, cv2.CC_STAT_WIDTH]
                height = stats[i, cv2.CC_STAT_HEIGHT]
                
                # Remove if:
                # 1. Too small (specs)
                # 2. Too thin (thin lines/artifacts)
                is_small = area < min_artifact_size
                is_thin = min(width, height) < thin_threshold
                
                if is_small or is_thin:
                    removal_mask[labels == i] = 255
                    total_artifacts_removed += 1
            
            # Fill removed artifacts with dominant color
            if np.any(removal_mask):
                # Dilate the removal mask slightly for better coverage
                kernel = np.ones((3, 3), np.uint8)
                removal_mask = cv2.dilate(removal_mask, kernel, iterations=1)
                
                # Fill with dominant color
                region[removal_mask > 0] = dominant_color
                
                # Put the cleaned region back
                result[bbox.y:bbox.y2, bbox.x:bbox.x2] = region
        
        logger.info(f"Removed {total_artifacts_removed} small artifacts from containers")
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(result, '05_containers_cleaned.png', DEBUG.get('output_dir'))
        
        return result
