"""
SAM 2 Segmentation Module
Handles automatic segmentation of infographic elements using Segment Anything Model
"""

import logging
from typing import List, Optional, Tuple
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from .config import SAMConfig
from .data_structures import SegmentedElement, BoundingBox

logger = logging.getLogger(__name__)


class SAMSegmenter:
    """
    Segment Anything Model wrapper for infographic segmentation.
    
    Uses SAM to automatically detect all distinct visual elements in an image.
    """
    
    def __init__(self, config: SAMConfig = None):
        self.config = config or SAMConfig()
        self.device = self._get_device()
        self.model = None
        self.mask_generator = None
        self._initialized = False
    
    def _get_device(self) -> str:
        """Determine the best device to use"""
        if self.config.device != "auto":
            return self.config.device
        
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    def initialize(self):
        """Initialize SAM model (lazy loading)"""
        if self._initialized:
            return
        
        logger.info(f"Initializing SAM ({self.config.model_type}) on {self.device}...")
        
        try:
            # Try to import SAM 2
            from sam2.build_sam import build_sam2
            from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
            
            # Model configurations
            model_configs = {
                "vit_h": ("sam2_hiera_large.pt", "sam2_hiera_l.yaml"),
                "vit_l": ("sam2_hiera_large.pt", "sam2_hiera_l.yaml"),
                "vit_b": ("sam2_hiera_base_plus.pt", "sam2_hiera_b+.yaml"),
            }
            
            checkpoint, config_file = model_configs.get(
                self.config.model_type, 
                model_configs["vit_h"]
            )
            
            # Download checkpoint if needed
            checkpoint_path = self._ensure_checkpoint(checkpoint)
            
            # Build model
            self.model = build_sam2(config_file, checkpoint_path, device=self.device)
            
            # Create mask generator
            self.mask_generator = SAM2AutomaticMaskGenerator(
                model=self.model,
                points_per_side=self.config.points_per_side,
                pred_iou_thresh=self.config.pred_iou_thresh,
                stability_score_thresh=self.config.stability_score_thresh,
                min_mask_region_area=self.config.min_mask_region_area,
            )
            
            logger.info("SAM 2 initialized successfully")
            
        except ImportError:
            logger.warning("SAM 2 not available, falling back to SAM 1")
            self._initialize_sam1()
        
        self._initialized = True
    
    def _initialize_sam1(self):
        """Fallback to SAM 1 if SAM 2 is not available"""
        from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
        
        model_configs = {
            "vit_h": "sam_vit_h_4b8939.pth",
            "vit_l": "sam_vit_l_0b3195.pth",
            "vit_b": "sam_vit_b_01ec64.pth",
        }
        
        checkpoint = model_configs.get(self.config.model_type, model_configs["vit_h"])
        checkpoint_path = self._ensure_checkpoint(checkpoint)
        
        self.model = sam_model_registry[self.config.model_type](checkpoint=checkpoint_path)
        self.model.to(device=self.device)
        
        self.mask_generator = SamAutomaticMaskGenerator(
            model=self.model,
            points_per_side=self.config.points_per_side,
            pred_iou_thresh=self.config.pred_iou_thresh,
            stability_score_thresh=self.config.stability_score_thresh,
            min_mask_region_area=self.config.min_mask_region_area,
        )
        
        logger.info("SAM 1 initialized successfully")
    
    def _ensure_checkpoint(self, checkpoint_name: str) -> str:
        """Download checkpoint if not present"""
        cache_dir = Path.home() / ".cache" / "sam_checkpoints"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_path = cache_dir / checkpoint_name
        
        if checkpoint_path.exists():
            return str(checkpoint_path)
        
        # Download from HuggingFace or Facebook
        logger.info(f"Downloading SAM checkpoint: {checkpoint_name}")
        
        urls = {
            "sam_vit_h_4b8939.pth": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
            "sam_vit_l_0b3195.pth": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth",
            "sam_vit_b_01ec64.pth": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth",
            "sam2_hiera_large.pt": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt",
            "sam2_hiera_base_plus.pt": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_base_plus.pt",
        }
        
        if checkpoint_name in urls:
            import urllib.request
            urllib.request.urlretrieve(urls[checkpoint_name], checkpoint_path)
            logger.info(f"Downloaded checkpoint to {checkpoint_path}")
        else:
            raise FileNotFoundError(f"Unknown checkpoint: {checkpoint_name}")
        
        return str(checkpoint_path)
    
    def segment(self, image: np.ndarray) -> List[SegmentedElement]:
        """
        Segment image into distinct elements.
        
        Args:
            image: RGB image as numpy array (H, W, 3)
            
        Returns:
            List of SegmentedElement objects
        """
        self.initialize()
        
        logger.info(f"Segmenting image of shape {image.shape}...")
        
        # Generate masks
        masks = self.mask_generator.generate(image)
        
        logger.info(f"SAM generated {len(masks)} raw masks")
        
        # Convert to SegmentedElement objects
        elements = []
        for i, mask_data in enumerate(masks):
            mask = mask_data['segmentation']
            bbox = BoundingBox.from_mask(mask)
            
            # Skip tiny elements
            if bbox.width < 10 or bbox.height < 10:
                continue
            
            element = SegmentedElement(
                id=f"seg_{i:04d}",
                mask=mask,
                bbox=bbox,
                area=int(mask_data['area']),
                stability_score=float(mask_data['stability_score']),
                predicted_iou=float(mask_data['predicted_iou']),
            )
            
            # Extract RGBA image
            element.image_rgba = self._extract_rgba(image, mask, bbox)
            
            elements.append(element)
        
        # Sort by area (largest first for later processing)
        elements.sort(key=lambda e: e.area, reverse=True)
        
        logger.info(f"Retained {len(elements)} valid segments")
        
        return elements
    
    def _extract_rgba(self, image: np.ndarray, mask: np.ndarray, 
                      bbox: BoundingBox) -> np.ndarray:
        """Extract RGBA image with mask as alpha channel"""
        # Crop to bounding box
        cropped_image = image[bbox.y:bbox.y2, bbox.x:bbox.x2].copy()
        cropped_mask = mask[bbox.y:bbox.y2, bbox.x:bbox.x2]
        
        # Create RGBA
        if cropped_image.shape[2] == 3:
            rgba = np.zeros((*cropped_image.shape[:2], 4), dtype=np.uint8)
            rgba[:, :, :3] = cropped_image
            rgba[:, :, 3] = (cropped_mask * 255).astype(np.uint8)
        else:
            rgba = cropped_image.copy()
            rgba[:, :, 3] = (cropped_mask * 255).astype(np.uint8)
        
        return rgba
    
    def segment_with_prompts(self, image: np.ndarray, 
                             points: List[Tuple[int, int]] = None,
                             boxes: List[Tuple[int, int, int, int]] = None,
                             labels: List[int] = None) -> List[SegmentedElement]:
        """
        Segment image with point or box prompts.
        
        Args:
            image: RGB image
            points: List of (x, y) points to segment around
            boxes: List of (x1, y1, x2, y2) boxes
            labels: Point labels (1 = foreground, 0 = background)
            
        Returns:
            List of SegmentedElement objects
        """
        self.initialize()
        
        # This requires the predictor interface instead of automatic generator
        try:
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            predictor = SAM2ImagePredictor(self.model)
        except ImportError:
            from segment_anything import SamPredictor
            predictor = SamPredictor(self.model)
        
        predictor.set_image(image)
        
        elements = []
        
        if points:
            point_coords = np.array(points)
            point_labels = np.array(labels if labels else [1] * len(points))
            
            masks, scores, _ = predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                multimask_output=True,
            )
            
            # Take highest scoring mask
            best_idx = np.argmax(scores)
            mask = masks[best_idx]
            bbox = BoundingBox.from_mask(mask)
            
            element = SegmentedElement(
                id="seg_prompt_0000",
                mask=mask,
                bbox=bbox,
                area=int(mask.sum()),
                stability_score=float(scores[best_idx]),
                predicted_iou=float(scores[best_idx]),
            )
            element.image_rgba = self._extract_rgba(image, mask, bbox)
            elements.append(element)
        
        if boxes:
            for i, box in enumerate(boxes):
                box_array = np.array(box)
                
                masks, scores, _ = predictor.predict(
                    box=box_array,
                    multimask_output=True,
                )
                
                best_idx = np.argmax(scores)
                mask = masks[best_idx]
                bbox = BoundingBox.from_mask(mask)
                
                element = SegmentedElement(
                    id=f"seg_box_{i:04d}",
                    mask=mask,
                    bbox=bbox,
                    area=int(mask.sum()),
                    stability_score=float(scores[best_idx]),
                    predicted_iou=float(scores[best_idx]),
                )
                element.image_rgba = self._extract_rgba(image, mask, bbox)
                elements.append(element)
        
        return elements


def filter_overlapping_segments(elements: List[SegmentedElement], 
                                iou_threshold: float = 0.7) -> List[SegmentedElement]:
    """
    Filter out highly overlapping segments, keeping the more stable ones.
    
    Args:
        elements: List of segmented elements
        iou_threshold: IoU threshold above which to consider overlap
        
    Returns:
        Filtered list of elements
    """
    if not elements:
        return []
    
    # Sort by stability score (highest first)
    sorted_elements = sorted(elements, key=lambda e: e.stability_score, reverse=True)
    
    kept = []
    kept_masks = []
    
    for element in sorted_elements:
        # Check overlap with kept elements
        should_keep = True
        
        for kept_mask in kept_masks:
            intersection = np.logical_and(element.mask, kept_mask).sum()
            union = np.logical_or(element.mask, kept_mask).sum()
            iou = intersection / union if union > 0 else 0
            
            if iou > iou_threshold:
                should_keep = False
                break
        
        if should_keep:
            kept.append(element)
            kept_masks.append(element.mask)
    
    return kept


def merge_nested_segments(elements: List[SegmentedElement],
                          containment_threshold: float = 0.85) -> List[SegmentedElement]:
    """
    Identify parent-child relationships between segments.
    
    Returns elements with updated properties indicating containment.
    """
    # Sort by area (largest first = potential parents)
    sorted_elements = sorted(elements, key=lambda e: e.area, reverse=True)
    
    for i, potential_parent in enumerate(sorted_elements):
        for potential_child in sorted_elements[i+1:]:
            # Check if child is mostly contained in parent
            intersection = np.logical_and(
                potential_parent.mask, 
                potential_child.mask
            ).sum()
            
            containment = intersection / potential_child.area if potential_child.area > 0 else 0
            
            if containment > containment_threshold:
                # Mark relationship (could extend data structure for this)
                pass
    
    return sorted_elements
