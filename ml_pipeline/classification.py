"""
CLIP Classification Module
Classifies segmented elements into infographic categories
"""

import logging
from typing import List, Dict, Optional, Tuple

import numpy as np
import torch
from PIL import Image

from .config import CLIPConfig
from .data_structures import SegmentedElement, ClassifiedElement

logger = logging.getLogger(__name__)


class CLIPClassifier:
    """
    CLIP-based zero-shot classifier for infographic elements.
    
    Uses CLIP to classify each segmented region into predefined categories
    like logo, icon, photo, text, etc.
    """
    
    def __init__(self, config: CLIPConfig = None):
        self.config = config or CLIPConfig()
        self.device = self._get_device()
        self.model = None
        self.preprocess = None
        self.text_features = None
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
        """Initialize CLIP model and precompute text features"""
        if self._initialized:
            return
        
        logger.info(f"Initializing CLIP ({self.config.model_name}) on {self.device}...")
        
        try:
            import clip
            self.model, self.preprocess = clip.load(
                self.config.model_name, 
                device=self.device
            )
        except ImportError:
            # Fallback to transformers CLIP
            logger.info("Using transformers CLIP implementation")
            from transformers import CLIPProcessor, CLIPModel
            
            model_map = {
                "ViT-B/32": "openai/clip-vit-base-patch32",
                "ViT-L/14": "openai/clip-vit-large-patch14",
            }
            
            model_name = model_map.get(self.config.model_name, "openai/clip-vit-base-patch32")
            
            self.model = CLIPModel.from_pretrained(model_name).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name)
            self._use_transformers = True
        else:
            self._use_transformers = False
        
        # Precompute text features for categories
        self._precompute_text_features()
        
        self._initialized = True
        logger.info("CLIP initialized successfully")
    
    def _precompute_text_features(self):
        """Precompute text embeddings for all categories"""
        logger.info("Computing text features for categories...")
        
        categories = self.config.categories
        
        if hasattr(self, '_use_transformers') and self._use_transformers:
            inputs = self.processor(text=categories, return_tensors="pt", padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                self.text_features = self.model.get_text_features(**inputs)
                self.text_features = self.text_features / self.text_features.norm(dim=-1, keepdim=True)
        else:
            import clip
            text_tokens = clip.tokenize(categories).to(self.device)
            
            with torch.no_grad():
                self.text_features = self.model.encode_text(text_tokens)
                self.text_features = self.text_features / self.text_features.norm(dim=-1, keepdim=True)
    
    def classify(self, elements: List[SegmentedElement], 
                 original_image: np.ndarray) -> List[ClassifiedElement]:
        """
        Classify segmented elements into categories.
        
        Args:
            elements: List of segmented elements
            original_image: Original RGB image for context
            
        Returns:
            List of ClassifiedElement with category assignments
        """
        self.initialize()
        
        logger.info(f"Classifying {len(elements)} elements...")
        
        classified = []
        
        for element in elements:
            # Get the image region for this element
            if element.image_rgba is not None:
                # Use the extracted RGBA, but convert to RGB with white background
                rgba = element.image_rgba
                rgb = self._rgba_to_rgb_white_bg(rgba)
            else:
                # Fallback: crop from original
                rgb = element.get_cropped_image(original_image)
            
            # Classify this region
            category, confidence, all_scores = self._classify_region(rgb)
            
            # Check for additional properties
            contains_text = self._check_contains_text(rgb)
            is_complex = self._check_complexity(rgb)
            
            # Create classified element
            classified_elem = ClassifiedElement(
                id=element.id,
                mask=element.mask,
                bbox=element.bbox,
                area=element.area,
                stability_score=element.stability_score,
                predicted_iou=element.predicted_iou,
                image_rgba=element.image_rgba,
                category=category,
                category_confidence=confidence,
                all_scores=all_scores,
                contains_text=contains_text,
                is_complex=is_complex,
            )
            
            classified.append(classified_elem)
            
            logger.debug(f"  {element.id}: {category} ({confidence:.2f})")
        
        logger.info(f"Classification complete")
        self._log_category_summary(classified)
        
        return classified
    
    def _classify_region(self, image: np.ndarray) -> Tuple[str, float, Dict[str, float]]:
        """
        Classify a single image region.
        
        Returns:
            (category, confidence, all_scores_dict)
        """
        # Convert to PIL Image
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)
        
        pil_image = Image.fromarray(image)
        
        # Get image features
        if hasattr(self, '_use_transformers') and self._use_transformers:
            inputs = self.processor(images=pil_image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        else:
            image_input = self.preprocess(pil_image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        # Compute similarity with text features
        similarity = (image_features @ self.text_features.T).squeeze(0)
        
        # Apply softmax to get probabilities
        probs = torch.softmax(similarity * 100, dim=-1)  # Temperature scaling
        
        # Get results
        probs_np = probs.cpu().numpy()
        categories = self.config.categories
        mapping = self.config.category_mapping
        
        # Build scores dict
        all_scores = {}
        for i, cat in enumerate(categories):
            simplified = mapping.get(cat, cat)
            if simplified in all_scores:
                all_scores[simplified] = max(all_scores[simplified], float(probs_np[i]))
            else:
                all_scores[simplified] = float(probs_np[i])
        
        # Get top category
        top_idx = probs_np.argmax()
        top_category = mapping.get(categories[top_idx], categories[top_idx])
        top_confidence = float(probs_np[top_idx])
        
        return top_category, top_confidence, all_scores
    
    def _rgba_to_rgb_white_bg(self, rgba: np.ndarray) -> np.ndarray:
        """Convert RGBA to RGB with white background"""
        if rgba.shape[2] == 3:
            return rgba
        
        rgb = rgba[:, :, :3].astype(np.float32)
        alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
        
        # Blend with white background
        white = np.ones_like(rgb) * 255
        blended = rgb * alpha + white * (1 - alpha)
        
        return blended.astype(np.uint8)
    
    def _check_contains_text(self, image: np.ndarray) -> bool:
        """
        Quick check if image region likely contains text.
        Uses edge/gradient analysis heuristic.
        """
        import cv2
        
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Text typically has many small connected components
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Count small, elongated contours (text-like)
        text_like = 0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if 20 < area < 2000:  # Small-ish regions
                aspect = max(w, h) / (min(w, h) + 1)
                if aspect < 8:  # Not too elongated
                    text_like += 1
        
        # Threshold: if many text-like components, likely contains text
        return text_like > 5
    
    def _check_complexity(self, image: np.ndarray) -> bool:
        """Check if image has high visual complexity (like a photo)"""
        import cv2
        
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
        
        # Calculate histogram
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()
        
        # Calculate entropy
        hist = hist[hist > 0]  # Remove zeros
        entropy = -np.sum(hist * np.log2(hist))
        
        # Photos typically have high entropy (> 6)
        # Icons/shapes have low entropy (< 4)
        return entropy > 5.5
    
    def _log_category_summary(self, elements: List[ClassifiedElement]):
        """Log summary of classification results"""
        category_counts = {}
        for elem in elements:
            cat = elem.category
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        logger.info("Category distribution:")
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {cat}: {count}")


def reclassify_by_context(elements: List[ClassifiedElement], 
                          image: np.ndarray) -> List[ClassifiedElement]:
    """
    Refine classifications using spatial context.
    
    For example:
    - Small elements in corners are likely logos
    - Elements containing other elements are likely containers
    - Adjacent similar elements might be icons in a list
    """
    h, w = image.shape[:2]
    
    for element in elements:
        bbox = element.bbox
        
        # Corner detection for logos
        in_corner = (
            (bbox.x < w * 0.15 or bbox.x2 > w * 0.85) and
            (bbox.y < h * 0.15 or bbox.y2 > h * 0.85)
        )
        
        if in_corner and element.area < (w * h * 0.05):  # Small and in corner
            if element.category in ["icon", "illustration", "shape"]:
                # Might be a logo
                if element.all_scores.get("logo", 0) > 0.1:
                    element.category = "logo"
                    element.category_confidence = element.all_scores.get("logo", 0.5)
        
        # Large elements covering most of width might be containers
        if bbox.width > w * 0.7 and element.category == "shape":
            element.category = "container"
    
    return elements
