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
    # Style group harmonization
    style_group_id: int = -1
    

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
        
        # Harmonize font styles within groups of visually-similar text
        text_elements = self._harmonize_style_groups(text_elements)
        
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
    
    # Fonts that only render uppercase glyphs.  If the OCR text contains
    # any lowercase letters, these fonts must NOT be assigned — they would
    # silently convert the text to all-caps in the output.
    # Maintained as a class-level set so it's easy to extend.
    CAPS_ONLY_FONTS = frozenset({
        # Display / titling fonts that lack lowercase glyphs
        'Bebas Neue',
        'Montserrat Subrayada',
        'Alfa Slab One',
        'Bowlby One',
        'Bowlby One SC',
        'Black Ops One',
        'Bungee Shade',
        'Bungee Spice',
        'Bungee Tint',
        'Monoton',
        'Koulen',
        'Stint Ultra Condensed',
        'Passion One',
        'Squada One',
        'Freshman',
        'Big Shoulders Stencil',
        'Big Shoulders Inline',
        'Alumni Sans Collegiate One',
        'Alumni Sans Inline One',
        'Alumni Sans Pinstripe',
    })
    
    # The fallback font used when a caps-only font is rejected or when
    # no valid classification exists for a group.
    DEFAULT_FALLBACK_FONT = 'Open Sans'
    
    @staticmethod
    def _text_has_lowercase(text: str) -> bool:
        """Return True if *text* contains at least one lowercase letter."""
        return any(c.islower() for c in text)
    
    @classmethod
    def _is_caps_only_font(cls, font_name: str) -> bool:
        """Check whether *font_name* is known to lack lowercase glyphs."""
        return font_name in cls.CAPS_ONLY_FONTS
    
    @classmethod
    def _is_valid_classified_font(cls, font_name: str) -> bool:
        """
        Return True if *font_name* is a real, usable classification result.
        
        Filters out:
          - empty / None values
          - the literal string 'NONE' produced by the TSV mapping for fonts
            that have no Google Fonts equivalent (Arial, BIZ UD*, etc.)
        """
        return bool(font_name) and font_name.upper() != 'NONE'
    
    def _harmonize_style_groups(self, text_elements: List[TextElement]) -> List[TextElement]:
        """
        Harmonize font classification across groups of visually-similar text.
        
        Text at the same visual hierarchy level should share the same font family.
        Individual font classification on small crops is noisy, so we group
        elements by the two most reliable signals and apply weighted majority-vote.
        
        Grouping strategy — proximity-based clustering:
          1. Partition elements by normalized font size (already clustered).
          2. Within each font-size partition, cluster elements whose vertical
             centres (Y midpoints) are within a configurable tolerance of each
             other.  Unlike a rigid grid, this avoids splitting rows that
             straddle a band boundary.
             
        Color and font_weight are intentionally NOT part of the group key because:
          - Color extraction from small crops is noisy (background bleed, 
            anti-aliasing, colored backgrounds).
          - Font weight detection (dark pixel ratio) is unreliable and splits
            groups that should be unified.
        
        Within each group we run a weighted majority vote: sum each font's
        classification confidence across all members.  The font with the
        highest total score wins and is applied to every member.
        
        Additional safeguards:
          - 'NONE' classifications (unmapped fonts in the TSV) are treated as
            unclassified and excluded from the vote.
          - Caps-only fonts are rejected when the group contains mixed-case
            text; the next-best candidate is used, or a safe fallback.
        
        Args:
            text_elements: Text elements with individually-classified fonts
            
        Returns:
            Text elements with harmonized font families within style groups
        """
        if not text_elements:
            return text_elements
        
        if not self.config.get('harmonize_font_styles', True):
            logger.info("Font style harmonization disabled in config")
            return text_elements
        
        logger.info("Harmonizing font styles across visual groups...")
        
        # --- Step 1: Build style groups by (font_size, y_cluster) ---
        # y_band_pct controls the max vertical distance (as fraction of image
        # height) for two elements to be considered "same row".
        y_band_pct = self.config.get('style_y_band_pct', 0.10)
        image_height = self.image_height or 1
        y_tolerance = max(1, int(image_height * y_band_pct))
        
        # Partition by font_size first
        size_partitions: Dict[int, List[int]] = {}
        for idx, elem in enumerate(text_elements):
            fs = elem.font_size
            if fs not in size_partitions:
                size_partitions[fs] = []
            size_partitions[fs].append(idx)
        
        # Within each font-size partition, cluster by Y-proximity
        groups: List[List[int]] = []
        
        for font_size, indices in size_partitions.items():
            # Sort by vertical centre
            indices_sorted = sorted(indices, key=lambda i: text_elements[i].bbox.y + text_elements[i].bbox.h // 2)
            
            # Greedy merge: walk sorted list, start a new cluster whenever
            # the gap to the *cluster average* exceeds y_tolerance
            current_cluster: List[int] = [indices_sorted[0]]
            current_y_sum = text_elements[indices_sorted[0]].bbox.y + text_elements[indices_sorted[0]].bbox.h // 2
            
            for i in range(1, len(indices_sorted)):
                idx = indices_sorted[i]
                y_center = text_elements[idx].bbox.y + text_elements[idx].bbox.h // 2
                cluster_avg_y = current_y_sum / len(current_cluster)
                
                if abs(y_center - cluster_avg_y) <= y_tolerance:
                    current_cluster.append(idx)
                    current_y_sum += y_center
                else:
                    groups.append(current_cluster)
                    current_cluster = [idx]
                    current_y_sum = y_center
            
            groups.append(current_cluster)
        
        logger.info(f"Identified {len(groups)} style groups from {len(text_elements)} elements "
                    f"(y_tolerance={y_tolerance}px, {y_band_pct*100:.0f}% of image height)")
        
        # --- Step 2: Harmonize font family within each group ---
        harmonized_count = 0
        fallback_font = self.config.get('fallback_font', self.DEFAULT_FALLBACK_FONT)
        
        for group_id, member_indices in enumerate(groups):
            # Assign group ID for traceability
            for idx in member_indices:
                text_elements[idx].style_group_id = group_id
            
            # Filter to members with a *valid* classification
            # (excludes empty strings AND the literal 'NONE')
            classified_members = [
                idx for idx in member_indices
                if self._is_valid_classified_font(text_elements[idx].classified_font)
            ]
            
            if len(classified_members) < 2:
                # If 0 or 1 valid classifications, check if the single one is
                # usable; if not, assign fallback to the whole group.
                if len(classified_members) == 1:
                    # Single classified member — just keep it, but check caps safety
                    single = text_elements[classified_members[0]]
                    group_has_lowercase = any(
                        self._text_has_lowercase(text_elements[i].text)
                        for i in member_indices
                    )
                    if group_has_lowercase and self._is_caps_only_font(single.classified_font):
                        logger.info(
                            f"  Group {group_id}: sole classification '{single.classified_font}' "
                            f"is caps-only but group has lowercase text → fallback to '{fallback_font}'"
                        )
                        for idx in member_indices:
                            elem = text_elements[idx]
                            elem.classified_font = fallback_font
                            elem.font_family = fallback_font
                            elem.classified_font_version = ''
                            harmonized_count += 1
                elif len(classified_members) == 0 and len(member_indices) > 0:
                    # No valid classifications at all (all NONE or empty)
                    # Assign a safe fallback so we don't output "NONE"
                    logger.info(
                        f"  Group {group_id}: no valid classifications "
                        f"({len(member_indices)} members) → fallback to '{fallback_font}'"
                    )
                    for idx in member_indices:
                        elem = text_elements[idx]
                        elem.classified_font = fallback_font
                        elem.font_family = fallback_font
                        elem.classified_font_version = ''
                        harmonized_count += 1
                continue
            
            # Weighted majority vote: sum confidence per font name
            font_votes: Dict[str, float] = {}     # font_name -> total confidence
            font_versions: Dict[str, str] = {}     # font_name -> version (from best conf)
            font_best_conf: Dict[str, float] = {}  # font_name -> best single confidence
            
            for idx in classified_members:
                elem = text_elements[idx]
                font = elem.classified_font
                conf = elem.font_classification_confidence
                
                font_votes[font] = font_votes.get(font, 0.0) + conf
                
                if font not in font_best_conf or conf > font_best_conf[font]:
                    font_best_conf[font] = conf
                    font_versions[font] = elem.classified_font_version
            
            # --- Caps-only font guard ---
            # Check if any member text contains lowercase characters
            group_has_lowercase = any(
                self._text_has_lowercase(text_elements[i].text)
                for i in member_indices
            )
            
            # Sort candidates by total weighted vote (descending)
            sorted_candidates = sorted(font_votes.items(), key=lambda x: -x[1])
            
            # Pick the best candidate that is safe for this group
            winning_font = None
            winning_version = ''
            winning_total_conf = 0.0
            
            for candidate_font, candidate_conf in sorted_candidates:
                if group_has_lowercase and self._is_caps_only_font(candidate_font):
                    logger.info(
                        f"  Group {group_id}: skipping caps-only font '{candidate_font}' "
                        f"(score={candidate_conf:.3f}) — group has lowercase text"
                    )
                    continue
                winning_font = candidate_font
                winning_version = font_versions.get(candidate_font, '')
                winning_total_conf = candidate_conf
                break
            
            # If all candidates were caps-only, fall back to safe default
            if winning_font is None:
                winning_font = fallback_font
                winning_version = ''
                winning_total_conf = 0.0
                logger.info(
                    f"  Group {group_id}: all candidates are caps-only → "
                    f"fallback to '{fallback_font}'"
                )
            
            # Log the vote breakdown
            font_size = text_elements[member_indices[0]].font_size
            y_centers = [text_elements[i].bbox.y + text_elements[i].bbox.h // 2 for i in member_indices]
            avg_y = int(np.mean(y_centers))
            member_texts = [text_elements[i].text[:20] for i in member_indices]
            logger.info(
                f"  Group {group_id} (size={font_size}pt, avg_y={avg_y}, "
                f"members={len(member_indices)}): "
                f"votes={dict(sorted(font_votes.items(), key=lambda x: -x[1]))}"
            )
            logger.info(f"    Winner: '{winning_font}' (weighted score: {winning_total_conf:.3f})")
            logger.info(f"    Members: {member_texts}")
            
            # Apply winning font to ALL members (including unclassified ones)
            for idx in member_indices:
                elem = text_elements[idx]
                old_font = elem.classified_font or elem.font_family
                
                if old_font != winning_font:
                    harmonized_count += 1
                    logger.debug(
                        f"    Harmonized '{elem.text[:25]}': "
                        f"'{old_font}' -> '{winning_font}'"
                    )
                
                elem.classified_font = winning_font
                elem.classified_font_version = winning_version
                elem.font_family = winning_font
                
                if elem.font_classification_confidence == 0.0:
                    # Unclassified element — give it the group's average confidence
                    avg_conf = winning_total_conf / max(len(classified_members), 1)
                    elem.font_classification_confidence = avg_conf
        
        logger.info(
            f"Font harmonization complete: {harmonized_count} elements updated "
            f"across {len(groups)} groups"
        )
        
        # Log final font distribution
        font_dist: Dict[str, int] = {}
        for elem in text_elements:
            font = elem.classified_font or elem.font_family
            font_dist[font] = font_dist.get(font, 0) + 1
        logger.info(f"Final font distribution: {dict(sorted(font_dist.items(), key=lambda x: -x[1]))}")
        
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
        
        print("\n" + "="*120)
        print(f"{'Text Content':<40} {'Font':<20} {'Size':<6} {'Lines':<6} {'Group':<6} {'Confidence':<10}")
        print("="*120)
        
        for element in text_elements:
            bbox = element.bbox
            
            # Draw bounding box
            cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), (0, 255, 0), 2)
            
            # Prepare label with font info and group
            font_info = element.classified_font if element.classified_font else element.font_family
            group_label = f"G{element.style_group_id}" if element.style_group_id >= 0 else ""
            label = f"{element.text[:15]}.. | {font_info} {element.font_size}pt {group_label}"
            
            # Add label
            cv2.putText(debug_img, label, (bbox.x, bbox.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Print detailed info to console
            text_preview = element.text.replace('\n', ' ')[:40]
            font_display = f"{element.classified_font} {element.classified_font_version}".strip() if element.classified_font else element.font_family
            confidence_display = f"{element.font_classification_confidence:.3f}" if element.classified_font else f"{element.confidence:.3f}"
            group_display = str(element.style_group_id) if element.style_group_id >= 0 else "-"
            
            print(f"{text_preview:<40} {font_display:<20} {element.font_size:<6} {element.num_lines:<6} {group_display:<6} {confidence_display:<10}")
        
        print("="*120 + "\n")
        
        save_debug_image(debug_img, '01_text_detection.png', DEBUG.get('output_dir', './debug_output'))
