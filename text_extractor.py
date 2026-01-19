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
    from font_classifier import get_font_classifier, FontPrediction, SUPPORTED_FONTS
    FONT_CLASSIFIER_AVAILABLE = True
except ImportError:
    FONT_CLASSIFIER_AVAILABLE = False

from utils import BoundingBox, save_debug_image
from config import OCR_CONFIG, DEBUG

logger = logging.getLogger(__name__)


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
    

class TextExtractor:
    """Extract text from images using OCR"""
    
    def __init__(self, config: Dict = None):
        self.config = config or OCR_CONFIG
        self.easyocr_reader = None
        
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
        
        # Try EasyOCR first if available (better accuracy)
        if self.easyocr_reader:
            text_elements = self._extract_with_easyocr(image)
        else:
            text_elements = self._extract_with_tesseract(image)
        
        # Enhance font identification
        text_elements = self._identify_fonts(image, text_elements)
        
        # Extract colors
        text_elements = self._extract_text_colors(image, text_elements)
        
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
        Identify font properties (size, weight, style) from text regions
        This is a simplified version - real font identification would require ML models
        """
        for element in text_elements:
            bbox = element.bbox
            
            # Extract text region
            text_region = image[bbox.y:bbox.y2, bbox.x:bbox.x2]
            
            if text_region.size == 0:
                continue
            
            # Estimate font size based on bounding box height
            element.font_size = self._estimate_font_size(bbox.h)
            
            # Detect bold text (simplified check based on pixel density)
            element.font_weight = self._detect_font_weight(text_region)
            
            # Detect italic (simplified check based on slant)
            element.font_style = self._detect_font_style(text_region)
        
        return text_elements
    
    def _estimate_font_size(self, height: int) -> int:
        """Estimate font size from text height in pixels"""
        # Rough conversion: pixel height to point size
        # This is approximate and depends on DPI (assuming 96 DPI)
        point_size = int(height * 0.75)
        return max(8, min(72, point_size))  # Clamp between 8 and 72
    
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
        """Save visualization of detected text"""
        debug_img = image.copy()
        
        for element in text_elements:
            bbox = element.bbox
            # Draw bounding box
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), (0, 255, 0), 2)
            
            # Add label
            label = f"{element.text[:20]}... ({element.confidence:.2f})"
            cv2.putText(debug_img, label, (bbox.x, bbox.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        save_debug_image(debug_img, '01_text_detection.png', DEBUG.get('output_dir', './debug_output'))
