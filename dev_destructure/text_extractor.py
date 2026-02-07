"""
Text extraction module with OCR and font identification
Step 1: Text OCR with styled font identification and bounding box identification
"""

import cv2
import numpy as np
import pytesseract
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass, field

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# Import font classifier
try:
    from font_classifier import get_font_classifier, FontPrediction
    FONT_CLASSIFIER_AVAILABLE = True
except Exception as _e:
    FONT_CLASSIFIER_AVAILABLE = False

from utils import BoundingBox, save_debug_image
from config import OCR_CONFIG, DEBUG

logger = logging.getLogger(__name__)

if not FONT_CLASSIFIER_AVAILABLE:
    logger.warning(f"Font classifier not available: {_e}")


@dataclass
class TextElement:
    """Represents extracted text with styling information"""
    text: str
    bbox: BoundingBox
    font_family: str = 'Arial'
    font_size: int = 12
    font_weight: str = 'normal'
    font_style: str = 'normal'
    color: str = '#000000'
    confidence: float = 0.0
    # New fields for enhanced text handling
    font_confidence: float = 0.0
    fallback_fonts: List[str] = field(default_factory=lambda: ['Helvetica', 'sans-serif'])
    line_height: float = 1.2
    letter_spacing: float = 0.0
    # Font classification results
    classified_font: str = ''
    classified_font_version: str = ''
    font_classification_confidence: float = 0.0
    # Line count
    num_lines: int = 1
    

class TextExtractor:
    """Extract text from images using OCR"""
    
    def __init__(self, config: Dict = None):
        self.config = config or OCR_CONFIG
        self.easyocr_reader = None
        self.image_width = None
        self.image_height = None
        
        if self.config.get('use_easyocr', False) and EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(self.config.get('languages', ['en']))
                logger.info("EasyOCR initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR: {e}")
    
    def extract_text_elements(self, image: np.ndarray) -> List[TextElement]:
        """
        Extract all text elements from image
        
        Args:
            image: Input image (BGR format)
        
        Returns:
            List of TextElement objects
        """
        logger.info("Starting text extraction...")
        
        # Store image dimensions for font size normalization
        self.image_height, self.image_width = image.shape[:2]
        logger.info(f"Image dimensions: {self.image_width}x{self.image_height}")
        
        # Try EasyOCR first if available (better accuracy)
        if self.easyocr_reader:
            text_elements = self._extract_with_easyocr(image)
        else:
            text_elements = self._extract_with_tesseract(image)
        
        # Enhance font identification
        text_elements = self._identify_fonts(image, text_elements)
        
        # Extract colors
        text_elements = self._extract_text_colors(image, text_elements)
        
        # Normalize font sizes relative to image dimensions
        text_elements = self._normalize_font_sizes(text_elements)
        
        logger.info(f"Extracted {len(text_elements)} text elements")
        
        if DEBUG.get('save_intermediate_steps', False):
            self._save_debug_visualization(image, text_elements)
        
        return text_elements
    
    def _extract_with_tesseract(self, image: np.ndarray) -> List[TextElement]:
        """Extract text using Tesseract OCR"""
        logger.info("Using Tesseract OCR...")
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply preprocessing
        processed = self._preprocess_for_ocr(gray)
        
        # Get detailed OCR data
        data = pytesseract.image_to_data(processed, 
                                         config=self.config['tesseract_config'],
                                         output_type=pytesseract.Output.DICT)
        
        text_elements = []
        min_conf = self.config.get('min_confidence', 60)
        
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            conf = float(data['conf'][i])
            
            if text and conf >= min_conf:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                bbox = BoundingBox(x, y, w, h, label='text', confidence=conf/100)
                
                element = TextElement(
                    text=text,
                    bbox=bbox,
                    confidence=conf/100
                )
                text_elements.append(element)
        
        return text_elements
    
    def _extract_with_easyocr(self, image: np.ndarray) -> List[TextElement]:
        """Extract text using EasyOCR"""
        logger.info("Using EasyOCR...")
        
        results = self.easyocr_reader.readtext(image)
        text_elements = []
        
        for bbox_coords, text, confidence in results:
            # EasyOCR returns coordinates as [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            x_coords = [pt[0] for pt in bbox_coords]
            y_coords = [pt[1] for pt in bbox_coords]
            
            x = int(min(x_coords))
            y = int(min(y_coords))
            w = int(max(x_coords) - x)
            h = int(max(y_coords) - y)
            
            bbox = BoundingBox(x, y, w, h, label='text', confidence=confidence)
            
            element = TextElement(
                text=text,
                bbox=bbox,
                confidence=confidence
            )
            text_elements.append(element)
        
        return text_elements
    
    def _preprocess_for_ocr(self, gray: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results"""
        # Apply bilateral filter to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(gray, 5, 50, 50)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        
        return thresh
    
    def _identify_fonts(self, image: np.ndarray, text_elements: List[TextElement]) -> List[TextElement]:
        """
        Identify font properties (size, weight, style, family) from text regions
        Uses ML-based font classifier if available
        """
        # Initialize font classifier if available
        font_classifier = None
        if FONT_CLASSIFIER_AVAILABLE:
            try:
                font_classifier = get_font_classifier()
                logger.info("Using font classifier for font identification")
            except Exception as e:
                logger.warning(f"Failed to initialize font classifier: {e}")
        
        for element in text_elements:
            bbox = element.bbox
            
            # Extract text region
            text_region = image[bbox.y:bbox.y2, bbox.x:bbox.x2]
            
            if text_region.size == 0:
                continue
            
            # Count number of lines in the text FIRST (needed for font size estimation)
            # Trust the OCR output - it's reliable for line detection
            element.num_lines = self._count_text_lines(element.text, text_region, bbox.h)
            
            # Estimate font size based on bounding box height and line count
            # Uses image dimensions for standardization
            element.font_size = self._estimate_font_size(
                bbox.h, 
                element.num_lines,
                image_width=self.image_width,
                image_height=self.image_height
            )
            
            # Detect bold text (simplified check based on pixel density)
            element.font_weight = self._detect_font_weight(text_region)
            
            # Detect italic (simplified check based on slant)
            element.font_style = self._detect_font_style(text_region)
            
            # Use font classifier to identify font family
            if font_classifier is not None:
                try:
                    prediction = font_classifier.predict(text_region)
                    element.classified_font = prediction.font_name
                    element.classified_font_version = prediction.font_version
                    element.font_classification_confidence = prediction.confidence
                    element.font_family = prediction.font_name  # Use classified font as primary
                    logger.debug(f"Font classified: {prediction.font_name} (confidence: {prediction.confidence:.3f})")
                except Exception as e:
                    logger.debug(f"Font classification failed for text '{element.text[:20]}...': {e}")
        
        return text_elements
    
    def _count_text_lines(self, text: str, text_region: np.ndarray, bbox_height: int) -> int:
        """
        Count the number of lines in the text
        
        Primary method: Trust the OCR text output
        - OCR engines (EasyOCR, Tesseract) already handle line detection well
        - If text contains newlines, use that count
        - If text is a single block without newlines, it's likely single-line
        
        Visual analysis is only used as a secondary check for text blocks
        that appear to span multiple lines but OCR merged them.
        """
        # Method 1: Count explicit newlines in OCR text (most reliable)
        # OCR engines are good at detecting line breaks
        newline_count = text.count('\n') + 1
        
        logger.debug(f"Line count for '{text[:30]}...': OCR detected {newline_count} line(s)")
        
        # Trust the OCR output - if it says single line, it probably is
        # This is more reliable than visual analysis which can be fooled by:
        # - Light colored text on light backgrounds
        # - Text with descenders/ascenders creating gaps
        # - Noise or artifacts
        return newline_count
    
    def _estimate_font_size(self, height: int, num_lines: int = 1, 
                           image_width: int = None, image_height: int = None) -> int:
        """
        Estimate font size from text bounding box height in pixels.
        
        Simple and direct: font size ≈ pixel height / line spacing factor
        
        Args:
            height: Bounding box height in pixels
            num_lines: Number of text lines (to divide height appropriately)
            image_width: Total image width (unused, kept for API compatibility)
            image_height: Total image height (unused, kept for API compatibility)
        
        Returns:
            Estimated font size in points
        """
        # Adjust for multi-line text
        line_height = height / max(1, num_lines)
        
        # Account for line spacing (typically 1.15-1.2x font size for tight text)
        # Bounding box height ≈ font_size * line_spacing_factor
        # So: font_size ≈ line_height / 1.15
        font_size = int(line_height / 1.15)
        
        # Clamp between reasonable bounds
        font_size = max(6, min(200, font_size))
        
        logger.debug(f"Font size estimate: height={height}px, lines={num_lines}, "
                    f"line_height={line_height:.1f}px, font_size={font_size}pt")
        
        return font_size
    
    def _normalize_font_sizes(self, text_elements: List[TextElement]) -> List[TextElement]:
        """
        Normalize font sizes across all text elements for consistency
        
        Uses clustering to group similar font sizes together, then assigns
        a consistent size to each cluster. This ensures that text which
        visually appears the same size gets the same font size value.
        
        Args:
            text_elements: List of text elements with estimated font sizes
        
        Returns:
            List of text elements with normalized font sizes
        """
        if not text_elements:
            return text_elements
        
        # Check if normalization is enabled
        if not self.config.get('normalize_font_sizes', True):
            logger.info("Font size normalization disabled in config")
            return text_elements
        
        logger.info("Normalizing font sizes for consistency...")
        
        # Collect all font sizes for analysis
        font_sizes = [elem.font_size for elem in text_elements]
        
        if len(font_sizes) == 0:
            return text_elements
        
        # Calculate statistics
        min_size = min(font_sizes)
        max_size = max(font_sizes)
        avg_size = np.mean(font_sizes)
        
        logger.info(f"Font size distribution before normalization: min={min_size}, max={max_size}, avg={avg_size:.1f}")
        logger.info(f"All sizes: {sorted(font_sizes)}")
        
        # Cluster similar font sizes together using both relative and absolute tolerance
        # This handles both small text (where 2pt difference matters) and large text
        relative_tolerance = self.config.get('font_size_cluster_tolerance', 0.30)  # 30%
        absolute_tolerance = 4  # Always group sizes within 4pt of each other
        
        # Sort sizes and create clusters
        sorted_sizes = sorted(set(font_sizes))
        clusters = []
        
        for size in sorted_sizes:
            # Try to add to existing cluster
            added = False
            for cluster in clusters:
                cluster_avg = np.mean(cluster)
                # Check if within EITHER relative OR absolute tolerance
                relative_diff = abs(size - cluster_avg) / max(cluster_avg, 1)
                absolute_diff = abs(size - cluster_avg)
                
                if relative_diff <= relative_tolerance or absolute_diff <= absolute_tolerance:
                    cluster.append(size)
                    added = True
                    break
            
            if not added:
                # Create new cluster
                clusters.append([size])
        
        logger.info(f"Found {len(clusters)} distinct font size clusters: {clusters}")
        
        # For each cluster, calculate the representative size (median of cluster)
        cluster_map = {}  # original_size -> normalized_size
        for cluster in clusters:
            # Use median, but round to a "nice" number
            cluster_median = np.median(cluster)
            # Round to nearest even number for cleaner output
            normalized = int(round(cluster_median / 2) * 2)
            normalized = max(6, normalized)  # Ensure minimum size
            
            for size in cluster:
                cluster_map[size] = normalized
            logger.info(f"  Cluster {cluster} -> {normalized}pt")
        
        # Apply normalization to all elements
        for element in text_elements:
            original_size = element.font_size
            normalized_size = cluster_map.get(original_size, original_size)
            
            # Apply min/max bounds from config
            min_font = self.config.get('min_font_size', 6)
            max_font = self.config.get('max_font_size', 200)
            normalized_size = int(max(min_font, min(max_font, normalized_size)))
            
            element.font_size = normalized_size
            
            if original_size != normalized_size:
                logger.debug(f"Normalized font: '{element.text[:25]}...' | "
                            f"{original_size}pt -> {normalized_size}pt")
        
        # Log final distribution
        final_sizes = [elem.font_size for elem in text_elements]
        unique_sizes = sorted(set(final_sizes))
        logger.info(f"Normalized to {len(unique_sizes)} distinct font sizes: {unique_sizes}")
        
        return text_elements
    
    def _detect_font_weight(self, text_region: np.ndarray) -> str:
        """Detect if text is bold based on pixel density"""
        if text_region.size == 0:
            return 'normal'
        
        gray = cv2.cvtColor(text_region, cv2.COLOR_BGR2GRAY) if len(text_region.shape) == 3 else text_region
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        
        # Calculate ratio of dark pixels
        dark_ratio = np.sum(binary > 0) / binary.size
        
        # Bold text typically has higher pixel density
        return 'bold' if dark_ratio > 0.4 else 'normal'
    
    def _detect_font_style(self, text_region: np.ndarray) -> str:
        """Detect if text is italic based on slant (simplified)"""
        # This is a very simplified check - real italic detection is complex
        # Would require analyzing character slant angles
        return 'normal'  # Default to normal for now
    
    def _extract_text_colors(self, image: np.ndarray, text_elements: List[TextElement]) -> List[TextElement]:
        """Extract dominant color for each text element"""
        for element in text_elements:
            bbox = element.bbox
            text_region = image[bbox.y:bbox.y2, bbox.x:bbox.x2]
            
            if text_region.size == 0:
                continue
            
            # Convert to LAB color space for better color analysis
            lab = cv2.cvtColor(text_region, cv2.COLOR_BGR2LAB)
            
            # Get L channel (lightness)
            l_channel = lab[:, :, 0]
            
            # Separate foreground (text) and background
            _, mask = cv2.threshold(l_channel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Get text pixels (assuming text is darker)
            if np.mean(mask) > 127:  # If mostly white, invert
                mask = cv2.bitwise_not(mask)
            
            # Extract color from text pixels
            text_pixels = text_region[mask > 0]
            
            if len(text_pixels) > 0:
                # Get median color
                median_color = np.median(text_pixels, axis=0).astype(int)
                element.color = f'#{median_color[2]:02x}{median_color[1]:02x}{median_color[0]:02x}'
        
        return text_elements
    
    def _save_debug_visualization(self, image: np.ndarray, text_elements: List[TextElement]):
        """Save visualization of detected text with font information"""
        debug_img = image.copy()
        
        print("\n" + "="*100)
        print(f"{'Text Content':<40} {'Font':<20} {'Size':<6} {'Lines':<6} {'Confidence':<10}")
        print("="*100)
        
        for element in text_elements:
            bbox = element.bbox
            
            # Draw bounding box
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), (0, 255, 0), 2)
            
            # Prepare label with font info
            font_info = element.classified_font if element.classified_font else element.font_family
            label = f"{element.text[:15]}... | {font_info} {element.font_size}pt"
            
            # Add label
            cv2.putText(debug_img, label, (bbox.x, bbox.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Print detailed info to console
            text_preview = element.text.replace('\n', ' ')[:40]
            font_display = f"{element.classified_font} {element.classified_font_version}".strip() if element.classified_font else element.font_family
            confidence_display = f"{element.font_classification_confidence:.3f}" if element.classified_font else f"{element.confidence:.3f}"
            
            print(f"{text_preview:<40} {font_display:<20} {element.font_size:<6} {element.num_lines:<6} {confidence_display:<10}")
        
        print("="*100 + "\n")
        
        save_debug_image(debug_img, '01_text_detection.png', DEBUG.get('output_dir', './debug_output'))
