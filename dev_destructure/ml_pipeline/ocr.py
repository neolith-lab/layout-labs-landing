"""
OCR Module using PaddleOCR
Extracts text content with position and styling information
"""

import logging
from typing import List, Dict, Optional, Tuple

import numpy as np
import cv2

from .config import OCRConfig
from .data_structures import TextElement, BoundingBox, ClassifiedElement

logger = logging.getLogger(__name__)


class TextExtractor:
    """
    PaddleOCR-based text extraction with styling detection.
    
    Extracts text content, position, and estimates styling properties
    like font size, weight, and color.
    """
    
    def __init__(self, config: OCRConfig = None):
        self.config = config or OCRConfig()
        self.ocr = None
        self._initialized = False
    
    def initialize(self):
        """Initialize PaddleOCR"""
        if self._initialized:
            return
        
        logger.info("Initializing PaddleOCR...")
        
        try:
            from paddleocr import PaddleOCR
            
            # Initialize PaddleOCR 3.x with new API
            self.ocr = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False
            )
            
            logger.info("PaddleOCR initialized successfully")
            
        except ImportError:
            logger.warning("PaddleOCR not available, falling back to EasyOCR")
            try:
                import easyocr
                self.ocr = easyocr.Reader([self.config.lang])
                self._use_easyocr = True
            except ImportError:
                logger.error("No OCR library available!")
                self.ocr = None
        
        self._initialized = True
    
    def extract(self, image: np.ndarray) -> List[TextElement]:
        """
        Extract all text from image.
        
        Args:
            image: RGB image
            
        Returns:
            List of TextElement with text content and styling
        """
        self.initialize()
        
        if self.ocr is None:
            logger.warning("No OCR available, returning empty list")
            return []
        
        logger.info("Extracting text from image...")
        
        # Convert RGB to BGR for PaddleOCR
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        if hasattr(self, '_use_easyocr') and self._use_easyocr:
            return self._extract_easyocr(image)
        else:
            return self._extract_paddleocr(image_bgr, image)
    
    def _extract_paddleocr(self, image_bgr: np.ndarray, 
                          image_rgb: np.ndarray) -> List[TextElement]:
        """Extract text using PaddleOCR 3.x CLI (more stable than Python API)"""
        import tempfile
        import subprocess
        import json
        
        text_elements = []
        
        # Save image to temp file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            temp_path = tmp.name
            cv2.imwrite(temp_path, image_bgr)
        
        try:
            # Use PaddleOCR CLI which has stable interface
            cmd = [
                'paddleocr', 'ocr',
                '-i', temp_path,
                '--use_doc_orientation_classify', 'False',
                '--use_doc_unwarping', 'False', 
                '--use_textline_orientation', 'False'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"PaddleOCR CLI failed: {result.stderr}")
                return []
            
            # Parse output - PaddleOCR CLI outputs results line by line
            # Format: [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], ("text", confidence)]
            import re
            for line in result.stdout.split('\n'):
                if not line.strip() or 'INFO' in line:
                    continue
                
                try:
                    # Try to parse as JSON-like structure
                    match = re.search(r'\[\[\[.*?\]\], \(.*?\)\]', line)
                    if not match:
                        continue
                    
                    data = eval(match.group())  # Safe here since we control the input
                    box_points = data[0]
                    text, confidence = data[1]
                    
                    if confidence < 0.5:
                        continue
                    
                    # Convert polygon to bounding box
                    xs = [p[0] for p in box_points]
                    ys = [p[1] for p in box_points]
                    x = int(min(xs))
                    y = int(min(ys))
                    w = int(max(xs) - min(xs))
                    h = int(max(ys) - min(ys))
                    
                    bbox = BoundingBox(x, y, w, h)
                    
                    # Estimate styling
                    region = image_rgb[max(0,y):min(y+h, image_rgb.shape[0]), 
                                       max(0,x):min(x+w, image_rgb.shape[1])]
                    
                    styling = self._estimate_styling(region, text, h)
                    
                    text_elem = TextElement(
                        text=text,
                        bbox=bbox,
                        confidence=float(confidence),
                        **styling
                    )
                    
                    text_elements.append(text_elem)
                    
                except Exception as e:
                    logger.debug(f"Failed to parse line: {line[:100]}... Error: {e}")
                    continue
        
        finally:
            # Clean up temp file
            import os
            try:
                os.unlink(temp_path)
            except:
                pass
        
        logger.info(f"Extracted {len(text_elements)} text elements via CLI")
        return text_elements
    
    def _extract_easyocr(self, image: np.ndarray) -> List[TextElement]:
        """Extract text using EasyOCR as fallback"""
        results = self.ocr.readtext(image)
        
        text_elements = []
        
        for (box, text, confidence) in results:
            if confidence < 0.5:
                continue
            
            # EasyOCR box format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x = int(min(xs))
            y = int(min(ys))
            w = int(max(xs) - min(xs))
            h = int(max(ys) - min(ys))
            
            bbox = BoundingBox(x, y, w, h)
            
            region = image[max(0,y):min(y+h, image.shape[0]), 
                          max(0,x):min(x+w, image.shape[1])]
            
            styling = self._estimate_styling(region, text, h)
            
            text_elem = TextElement(
                text=text,
                bbox=bbox,
                confidence=float(confidence),
                **styling
            )
            
            text_elements.append(text_elem)
        
        return text_elements
    
    def _estimate_styling(self, region: np.ndarray, text: str, 
                         height: int) -> Dict:
        """
        Estimate text styling from the image region.
        
        Returns dict with: font_size, font_weight, font_style, color, alignment
        """
        styling = {
            'font_size': self._estimate_font_size(height),
            'font_weight': 'normal',
            'font_style': 'normal',
            'color': '#000000',
            'alignment': 'left',
        }
        
        if region.size == 0:
            return styling
        
        # Estimate color from text pixels
        styling['color'] = self._extract_text_color(region)
        
        # Estimate weight from stroke width
        styling['font_weight'] = self._estimate_weight(region)
        
        return styling
    
    def _estimate_font_size(self, pixel_height: int) -> int:
        """Estimate font size from pixel height"""
        # Rough approximation: font size ≈ pixel height * 0.75
        return max(8, int(pixel_height * 0.75))
    
    def _extract_text_color(self, region: np.ndarray) -> str:
        """Extract the dominant text color from region"""
        if region.size == 0:
            return '#000000'
        
        gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY) if len(region.shape) == 3 else region
        
        # Threshold to separate text from background
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Determine if text is dark or light
        mean_val = gray.mean()
        
        if mean_val > 127:
            # Light background, text is likely dark pixels
            text_mask = binary < 128
        else:
            # Dark background, text is likely light pixels
            text_mask = binary > 127
        
        # Get color of text pixels
        if len(region.shape) == 3:
            text_pixels = region[text_mask]
            if len(text_pixels) > 0:
                avg_color = text_pixels.mean(axis=0).astype(int)
                return '#{:02x}{:02x}{:02x}'.format(avg_color[0], avg_color[1], avg_color[2])
        
        # Fallback: use mean of darker pixels
        dark_pixels = gray[gray < 128]
        if len(dark_pixels) > 0:
            avg = int(dark_pixels.mean())
            return '#{:02x}{:02x}{:02x}'.format(avg, avg, avg)
        
        return '#000000'
    
    def _estimate_weight(self, region: np.ndarray) -> str:
        """Estimate if text is bold based on stroke analysis"""
        gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY) if len(region.shape) == 3 else region
        
        # Binarize
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Calculate stroke width using distance transform
        dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
        
        if dist.max() > 0:
            avg_stroke = dist[dist > 0].mean()
            # If average stroke width is > 3, likely bold
            if avg_stroke > 3:
                return 'bold'
        
        return 'normal'
    
    def extract_from_element(self, image: np.ndarray, 
                            element: ClassifiedElement) -> List[TextElement]:
        """
        Extract text specifically from a classified element's region.
        
        Args:
            image: Full RGB image
            element: Element to extract text from
            
        Returns:
            List of TextElement with parent_element_id set
        """
        # Crop to element region
        bbox = element.bbox
        region = image[bbox.y:bbox.y2, bbox.x:bbox.x2]
        
        # Apply mask if available
        if element.mask is not None:
            mask_crop = element.mask[bbox.y:bbox.y2, bbox.x:bbox.x2]
            # Could apply mask here to improve OCR accuracy
        
        # Extract text
        text_elements = self.extract(region)
        
        # Adjust coordinates to full image space and set parent
        for te in text_elements:
            te.bbox = BoundingBox(
                x=te.bbox.x + bbox.x,
                y=te.bbox.y + bbox.y,
                width=te.bbox.width,
                height=te.bbox.height
            )
            te.parent_element_id = element.id
        
        return text_elements


def group_text_by_paragraph(text_elements: List[TextElement],
                           line_threshold: float = 1.5) -> List[List[TextElement]]:
    """
    Group text elements into paragraphs based on vertical proximity.
    
    Args:
        text_elements: List of text elements
        line_threshold: Max distance between lines as multiple of line height
        
    Returns:
        List of paragraph groups (each is a list of TextElement)
    """
    if not text_elements:
        return []
    
    # Sort by y position
    sorted_elements = sorted(text_elements, key=lambda t: t.bbox.y)
    
    paragraphs = []
    current_paragraph = [sorted_elements[0]]
    
    for te in sorted_elements[1:]:
        prev = current_paragraph[-1]
        
        # Calculate gap between elements
        gap = te.bbox.y - prev.bbox.y2
        avg_height = (te.bbox.height + prev.bbox.height) / 2
        
        # If gap is small, same paragraph
        if gap < avg_height * line_threshold:
            current_paragraph.append(te)
        else:
            paragraphs.append(current_paragraph)
            current_paragraph = [te]
    
    if current_paragraph:
        paragraphs.append(current_paragraph)
    
    return paragraphs


def classify_text_hierarchy(text_elements: List[TextElement]) -> List[TextElement]:
    """
    Classify text as heading vs body based on font size distribution.
    """
    if len(text_elements) < 2:
        return text_elements
    
    # Calculate font size distribution
    sizes = [te.font_size for te in text_elements]
    avg_size = np.mean(sizes)
    
    for te in text_elements:
        # If font size is significantly larger than average, it's likely a heading
        if te.font_size > avg_size * 1.3:
            te.font_weight = 'bold'  # Assume headings are bold
    
    return text_elements
