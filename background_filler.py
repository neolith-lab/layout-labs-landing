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
