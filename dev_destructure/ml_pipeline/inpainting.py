"""
LaMa Inpainting Module
Handles background reconstruction by removing foreground elements
"""

import logging
from typing import List, Optional, Tuple
from pathlib import Path

import numpy as np
import cv2

from .config import LamaConfig
from .data_structures import ClassifiedElement, BoundingBox

logger = logging.getLogger(__name__)


class LamaInpainter:
    """
    LaMa-based inpainting for background reconstruction.
    
    Removes foreground elements and reconstructs the background
    using Large Mask Inpainting (LaMa).
    """
    
    def __init__(self, config: LamaConfig = None):
        self.config = config or LamaConfig()
        self.device = self._get_device()
        self.model = None
        self._initialized = False
    
    def _get_device(self) -> str:
        """Determine the best device to use"""
        if self.config.device != "auto":
            return self.config.device
        
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"
    
    def initialize(self):
        """Initialize LaMa model"""
        if self._initialized:
            return
        
        logger.info(f"Initializing LaMa inpainting on {self.device}...")
        
        try:
            # Try simple-lama-inpainting package first (easier to install)
            from simple_lama_inpainting import SimpleLama
            self.model = SimpleLama()
            self._use_simple_lama = True
            logger.info("Using simple-lama-inpainting")
        except ImportError:
            logger.info("simple-lama-inpainting not available, trying alternative...")
            try:
                # Try lama-cleaner
                from lama_cleaner.model_manager import ModelManager
                from lama_cleaner.schema import Config
                
                self.model = ModelManager(name="lama", device=self.device)
                self._use_simple_lama = False
                self._use_lama_cleaner = True
                logger.info("Using lama-cleaner")
            except ImportError:
                # Fallback to OpenCV inpainting
                logger.warning("No ML inpainting available, using OpenCV fallback")
                self.model = None
                self._use_simple_lama = False
                self._use_lama_cleaner = False
        
        self._initialized = True
        logger.info("Inpainting module initialized")
    
    def inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        Inpaint masked regions of the image.
        
        Args:
            image: RGB image (H, W, 3)
            mask: Binary mask where 255 = regions to inpaint (H, W)
            
        Returns:
            Inpainted image
        """
        self.initialize()
        
        # Ensure mask is binary
        mask = (mask > 127).astype(np.uint8) * 255
        
        # Dilate mask slightly to cover edges
        if self.config.mask_dilation > 0:
            kernel = np.ones((self.config.mask_dilation, self.config.mask_dilation), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=1)
        
        if self._use_simple_lama:
            return self._inpaint_simple_lama(image, mask)
        elif hasattr(self, '_use_lama_cleaner') and self._use_lama_cleaner:
            return self._inpaint_lama_cleaner(image, mask)
        else:
            return self._inpaint_opencv(image, mask)
    
    def _inpaint_simple_lama(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Inpaint using simple-lama-inpainting"""
        from PIL import Image
        
        # Convert to PIL
        pil_image = Image.fromarray(image)
        pil_mask = Image.fromarray(mask)
        
        # Inpaint
        result = self.model(pil_image, pil_mask)
        
        return np.array(result)
    
    def _inpaint_lama_cleaner(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Inpaint using lama-cleaner"""
        result = self.model(image, mask)
        return result
    
    def _inpaint_opencv(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Fallback: OpenCV inpainting (not as good as LaMa)"""
        logger.debug("Using OpenCV inpainting fallback")
        
        # Convert RGB to BGR for OpenCV
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # Use Telea algorithm
        result_bgr = cv2.inpaint(image_bgr, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
        
        # Convert back to RGB
        return cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    
    def reconstruct_background(self, image: np.ndarray, 
                               elements: List[ClassifiedElement],
                               exclude_categories: List[str] = None) -> np.ndarray:
        """
        Reconstruct background by removing all foreground elements.
        
        Args:
            image: Original RGB image
            elements: Classified elements to remove
            exclude_categories: Categories to NOT remove (keep in background)
            
        Returns:
            Clean background image
        """
        self.initialize()
        
        exclude_categories = exclude_categories or []
        
        # Build combined mask of all elements to remove
        h, w = image.shape[:2]
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        
        # Sort elements by layer order (process back-to-front)
        # This helps with overlapping regions
        elements_to_remove = [
            e for e in elements 
            if e.category not in exclude_categories
        ]
        
        logger.info(f"Removing {len(elements_to_remove)} elements for background reconstruction")
        
        for element in elements_to_remove:
            combined_mask = np.maximum(combined_mask, element.mask.astype(np.uint8) * 255)
        
        if combined_mask.max() == 0:
            logger.info("No elements to remove, returning original")
            return image.copy()
        
        # Inpaint
        logger.info("Inpainting background...")
        background = self.inpaint(image, combined_mask)
        
        return background
    
    def reconstruct_layered(self, image: np.ndarray,
                           elements: List[ClassifiedElement],
                           layer_order: List[str]) -> Tuple[np.ndarray, List[np.ndarray]]:
        """
        Reconstruct background layer by layer for proper occlusion handling.
        
        This processes elements in z-order, inpainting at each step to properly
        handle overlapping elements.
        
        Args:
            image: Original RGB image
            elements: All classified elements
            layer_order: Category order (bottom to top)
            
        Returns:
            (final_background, list_of_intermediate_backgrounds)
        """
        self.initialize()
        
        # Group elements by category
        elements_by_category = {}
        for e in elements:
            if e.category not in elements_by_category:
                elements_by_category[e.category] = []
            elements_by_category[e.category].append(e)
        
        # Process in reverse layer order (top to bottom)
        current_image = image.copy()
        intermediate_backgrounds = []
        
        for category in reversed(layer_order):
            if category not in elements_by_category:
                continue
            if category == "background":
                continue
            
            category_elements = elements_by_category[category]
            
            # Build mask for this category
            h, w = image.shape[:2]
            category_mask = np.zeros((h, w), dtype=np.uint8)
            
            for element in category_elements:
                category_mask = np.maximum(category_mask, element.mask.astype(np.uint8) * 255)
            
            if category_mask.max() > 0:
                logger.info(f"Inpainting {len(category_elements)} '{category}' elements...")
                current_image = self.inpaint(current_image, category_mask)
                intermediate_backgrounds.append(current_image.copy())
        
        return current_image, intermediate_backgrounds


class IterativeInpainter:
    """
    Advanced inpainter that processes regions iteratively for better quality.
    
    Useful when you have many overlapping elements or large areas to inpaint.
    """
    
    def __init__(self, base_inpainter: LamaInpainter):
        self.inpainter = base_inpainter
    
    def inpaint_regions(self, image: np.ndarray, 
                       masks: List[np.ndarray],
                       order: str = "area") -> np.ndarray:
        """
        Inpaint multiple regions iteratively.
        
        Args:
            image: Original image
            masks: List of binary masks
            order: How to order regions - "area" (largest first) or "position" (top-left first)
            
        Returns:
            Fully inpainted image
        """
        if order == "area":
            # Sort by area (largest first - these affect the most context)
            masks = sorted(masks, key=lambda m: m.sum(), reverse=True)
        elif order == "position":
            # Sort by position (top-left to bottom-right)
            def get_position(mask):
                rows = np.any(mask, axis=1)
                cols = np.any(mask, axis=0)
                if not np.any(rows):
                    return (float('inf'), float('inf'))
                y = np.where(rows)[0][0]
                x = np.where(cols)[0][0]
                return (y, x)
            masks = sorted(masks, key=get_position)
        
        result = image.copy()
        
        for i, mask in enumerate(masks):
            if mask.max() == 0:
                continue
            
            logger.debug(f"Inpainting region {i+1}/{len(masks)}")
            result = self.inpainter.inpaint(result, mask.astype(np.uint8) * 255)
        
        return result


def create_inpaint_mask_from_elements(elements: List[ClassifiedElement],
                                     image_shape: Tuple[int, int],
                                     categories_to_remove: List[str] = None,
                                     dilation: int = 3) -> np.ndarray:
    """
    Create a combined inpainting mask from multiple elements.
    
    Args:
        elements: List of classified elements
        image_shape: (height, width) of the image
        categories_to_remove: Which categories to include in mask (None = all)
        dilation: Pixels to dilate mask by
        
    Returns:
        Binary mask (H, W) where 255 = inpaint
    """
    h, w = image_shape
    mask = np.zeros((h, w), dtype=np.uint8)
    
    for element in elements:
        if categories_to_remove is not None:
            if element.category not in categories_to_remove:
                continue
        
        mask = np.maximum(mask, element.mask.astype(np.uint8) * 255)
    
    if dilation > 0:
        kernel = np.ones((dilation, dilation), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)
    
    return mask
