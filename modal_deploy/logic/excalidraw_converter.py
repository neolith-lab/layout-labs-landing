"""
Convert extracted image elements to Excalidraw JSON format
"""

import uuid
import time
import base64
import requests
import cv2
import json
import os
from typing import Dict, List, Any, Optional
import random


# Excalidraw FONT_FAMILY numeric IDs (mirrors constants.ts in excalidraw)
EXCALIDRAW_FONT_FAMILY = {
    "Excalifont": 5,
    "Nunito": 6,
    "Lilita One": 7,
    "Comic Shanns": 8,
    "Liberation Sans": 9,
    "Assistant": 10,
    "Avenir": 11,
    # Professional Sans Serif
    "Roboto": 12,
    "Open Sans": 13,
    "Lato": 14,
    "Montserrat": 15,
    "Inter": 16,
    "Poppins": 17,
    "Raleway": 18,
    "Work Sans": 19,
    "Source Sans 3": 20,
    "Ubuntu": 21,
    "Mulish": 22,
    "Heebo": 23,
    "DM Sans": 24,
    "Karla": 25,
    # Elegant Serif
    "Playfair Display": 26,
    "Merriweather": 27,
    "Lora": 28,
    "Crimson Text": 29,
    "Libre Baskerville": 30,
    "EB Garamond": 31,
    "Cormorant Garamond": 32,
    "Spectral": 33,
    "PT Serif": 34,
    "Cardo": 35,
    "Domine": 36,
    "Vollkorn": 37,
    "Prata": 38,
    "Cinzel": 39,
    "Fraunces": 40,
    # Slab Serif
    "Roboto Slab": 41,
    "Oswald": 42,
    "Arvo": 43,
    "Zilla Slab": 44,
    "Bitter": 45,
    # Display & Stylized
    "Abril Fatface": 46,
    "Lobster": 47,
    "Bebas Neue": 48,
    "Anton": 49,
    "Righteous": 50,
    "Orbitron": 51,
    # Handwriting & Script
    "Pacifico": 52,
    "Indie Flower": 53,
    "Caveat": 54,
    "Shadows Into Light": 55,
    "Great Vibes": 56,
    # Monospace
    "Roboto Mono": 57,
    "Inconsolata": 58,
    "Source Code Pro": 59,
    "Space Mono": 60,
}

# Default font ID when no mapping is found
DEFAULT_FONT_ID = EXCALIDRAW_FONT_FAMILY["Excalifont"]  # 5


def _load_font_to_anchor_mapping() -> Dict[str, str]:
    """
    Load the font_to_anchor_mapping.json which maps any Google Font name
    to one of the 50 anchor fonts used in Excalidraw.
    """
    # Try multiple possible locations for the mapping file
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "font_to_anchor_mapping.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "font_coalesce", "google_fonts", "font_to_anchor_mapping.json"),
        "/root/dev_destructure/font_to_anchor_mapping.json",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    
    print("Warning: font_to_anchor_mapping.json not found, font mapping will fall back to defaults")
    return {}


# Load mapping once at module level
FONT_TO_ANCHOR_MAPPING = _load_font_to_anchor_mapping()


def map_classified_font_to_excalidraw_id(classified_font: str) -> int:
    """
    Map a classified font name to its Excalidraw numeric font family ID.
    
    Flow: classified_font → (anchor mapping) → anchor font → (FONT_FAMILY) → numeric ID
    
    Args:
        classified_font: The font name from the font classification model
        
    Returns:
        Excalidraw numeric font family ID
    """
    if not classified_font:
        return DEFAULT_FONT_ID
    
    # 1. Check if the classified font is already one of our anchor fonts
    if classified_font in EXCALIDRAW_FONT_FAMILY:
        return EXCALIDRAW_FONT_FAMILY[classified_font]
    
    # 2. Look up in the font_to_anchor_mapping
    anchor_font = FONT_TO_ANCHOR_MAPPING.get(classified_font)
    if anchor_font and anchor_font in EXCALIDRAW_FONT_FAMILY:
        return EXCALIDRAW_FONT_FAMILY[anchor_font]
    
    # 3. Try case-insensitive match against anchor fonts
    classified_lower = classified_font.lower()
    for font_name, font_id in EXCALIDRAW_FONT_FAMILY.items():
        if font_name.lower() == classified_lower:
            return font_id
    
    # 4. Fallback to default
    return DEFAULT_FONT_ID


class ExcalidrawConverter:
    """Convert image extraction data to Excalidraw JSON format"""
    
    def __init__(self):
        self.index_counter = 0
        
    def _get_index(self) -> str:
        """Generate fractional index for z-ordering"""
        idx = f"a{self.index_counter}"
        self.index_counter += 1
        return idx
    
    def _get_value(self, obj: Any, key: str, default: Any = None) -> Any:
        """
        Get value from either a dict or an object attribute
        Supports both JSON dict format and Python object format
        """
        if isinstance(obj, dict):
            return obj.get(key, default)
        else:
            return getattr(obj, key, default)
    
    def _calculate_font_size_for_box(self, text: str, box_width: float, box_height: float, 
                                      original_font_size: int) -> int:
        """
        Calculate an appropriate font size that fits within the bounding box.
        
        Uses heuristic estimation based on:
        - Average character width: ~0.6 * font_size for most fonts
        - Line height: ~1.25 * font_size (Excalidraw's default line height)
        - Number of lines and characters
        
        Args:
            text: The text content
            box_width: Available width in pixels
            box_height: Available height in pixels
            original_font_size: The original detected font size
            
        Returns:
            Adjusted font size that should fit within the box
        """
        if not text or box_width <= 0 or box_height <= 0:
            return max(10, min(original_font_size, 20))
        
        # Split text into lines
        lines = text.split('\n') if '\n' in text else [text]
        num_lines = len(lines)
        
        # Get the longest line
        max_line_length = max(len(line) for line in lines) if lines else 1
        
        # Excalidraw uses line height of 1.25
        line_height_multiplier = 1.25
        
        # Average character width is approximately 0.6 * font_size for proportional fonts
        # (This is a heuristic; actual width depends on font and specific characters)
        avg_char_width_multiplier = 0.6
        
        # Calculate font size based on height constraint
        # Available height / (number of lines * line height multiplier)
        font_size_from_height = box_height / (num_lines * line_height_multiplier)
        
        # Calculate font size based on width constraint
        # Available width / (max line length * avg char width multiplier)
        font_size_from_width = box_width / (max_line_length * avg_char_width_multiplier)
        
        # Use the smaller of the two constraints (most restrictive)
        calculated_font_size = min(font_size_from_height, font_size_from_width)
        
        # Apply some sensible bounds
        # Don't go too small (minimum 8px) or too large (cap at 120% of original or 72px)
        min_font_size = 8
        max_font_size = min(int(original_font_size * 1.2), 72)
        
        # Prefer to stay close to original if it fits reasonably
        if original_font_size <= calculated_font_size * 1.1:
            # Original size fits (with 10% tolerance)
            final_font_size = original_font_size
        else:
            # Need to scale down, use calculated size
            final_font_size = int(calculated_font_size * 0.9)  # 90% to add safety margin
        
        # Clamp to bounds
        final_font_size = max(min_font_size, min(final_font_size, max_font_size))
        
        return final_font_size
    
    def _create_base_element(self) -> Dict[str, Any]:
        """Create base properties that all Excalidraw elements need"""
        return {
            "seed": random.randint(1, 2**31 - 1),
            "version": 1,
            "versionNonce": random.randint(1, 2**31 - 1),
            "isDeleted": False,
            "groupIds": [],
            "frameId": None,
            "boundElements": None,
            "updated": int(time.time() * 1000),
            "link": None,
            "locked": False,
            "angle": 0,
            "strokeStyle": "solid",
            "roughness": 0,
            "opacity": 100,
        }
    
    def _download_and_encode_image(self, url: str) -> tuple[str, str]:
        """
        Download image from URL and convert to base64
        Returns: (base64_data, mime_type)
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Get mime type from headers or guess from URL
            mime_type = response.headers.get('content-type', 'image/png')
            if 'image' not in mime_type:
                # Try to infer from URL
                if url.lower().endswith('.jpg') or url.lower().endswith('.jpeg'):
                    mime_type = 'image/jpeg'
                elif url.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif url.lower().endswith('.gif'):
                    mime_type = 'image/gif'
                else:
                    mime_type = 'image/png'  # default
            
            # Encode to base64
            img_base64 = base64.b64encode(response.content).decode('utf-8')
            return img_base64, mime_type
            
        except Exception as e:
            print(f"Warning: Failed to download image from {url}: {e}")
            return None, None
    
    def _create_container_element(self, container: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a container to Excalidraw rectangle"""
        bbox = self._get_value(container, 'bbox', [0, 0, 100, 100])
        
        # Handle BoundingBox object
        if hasattr(bbox, 'x'):
            x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
        # Handle different bbox formats: [x, y, w, h] or dict
        elif isinstance(bbox, dict):
            x = bbox.get('x', 0)
            y = bbox.get('y', 0)
            w = bbox.get('width', bbox.get('w', 100))
            h = bbox.get('height', bbox.get('h', 100))
        elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x, y, w, h = bbox
            # Check if it's [x1, y1, x2, y2] format (w and h would be large)
            if w > 10000 or h > 10000:  # likely coordinates not dimensions
                x, y, x2, y2 = bbox
                w, h = x2 - x, y2 - y
        else:
            x, y, w, h = 0, 0, 100, 100
        
        element = {
            **self._create_base_element(),
            "id": str(uuid.uuid4()),
            "type": "rectangle",
            "x": float(x),
            "y": float(y),
            "width": float(w),
            "height": float(h),
            "strokeColor": self._get_value(container, 'stroke_color', self._get_value(container, 'border_color', '#e9ecef')),
            "backgroundColor": self._get_value(container, 'fill_color', self._get_value(container, 'background_color', '#f8f9fa')),
            "fillStyle": "solid",
            "strokeWidth": 1,
            "index": self._get_index(),
            "roundness": {"type": 3},  # Rounded corners
        }
        
        return element
    
    def _create_image_element(
        self, 
        image: Dict[str, Any], 
        files: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Convert an image to Excalidraw image element using pre-encoded base64 data"""
        bbox = self._get_value(image, 'bbox', [0, 0, 100, 100])
        
        # Prefer base64_data (already encoded during extraction)
        base64_data = self._get_value(image, 'base64_data')
        mime_type = self._get_value(image, 'mime_type', 'image/png')
        
        # Fallback to s3_url if no base64 (for backwards compatibility)
        s3_url = self._get_value(image, 's3_url', self._get_value(image, 'url'))
        
        # Fallback to image_data numpy array
        image_data = self._get_value(image, 'image_data')
        
        # Handle BoundingBox object
        if hasattr(bbox, 'x'):
            x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
        # Handle dict format
        elif isinstance(bbox, dict):
            x = bbox.get('x', 0)
            y = bbox.get('y', 0)
            w = bbox.get('width', bbox.get('w', 100))
            h = bbox.get('height', bbox.get('h', 100))
        # Handle list format
        elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x, y, w, h = bbox
            if w > 10000 or h > 10000:
                x, y, x2, y2 = bbox
                w, h = x2 - x, y2 - y
        else:
            x, y, w, h = 0, 0, 100, 100
        
        # Get base64 data from the best available source
        img_base64 = None
        
        if base64_data:
            # Use pre-encoded base64 directly (preferred - no network call needed)
            img_base64 = base64_data
        elif s3_url:
            # Fallback: Download and encode image from S3 URL
            print(f"    Downloading from S3 (no base64_data available)...")
            img_base64, mime_type = self._download_and_encode_image(s3_url)
            if not img_base64:
                print(f"Warning: Failed to encode image from {s3_url}, skipping")
                return None
        elif image_data is not None:
            # Fallback: Encode local image_data (numpy array)
            try:
                success, buffer = cv2.imencode('.png', image_data)
                if not success:
                    print("Warning: Failed to encode local image data, skipping")
                    return None
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                mime_type = 'image/png'
            except Exception as e:
                print(f"Warning: Failed to encode local image data: {e}")
                return None
        else:
            print("Warning: Image missing base64_data, s3_url, and image_data, skipping")
            return None
        
        # Create file entry
        file_id = str(uuid.uuid4())
        files[file_id] = {
            "mimeType": mime_type,
            "id": file_id,
            "dataURL": f"data:{mime_type};base64,{img_base64}",
            "created": int(time.time() * 1000),
        }
        
        # Create image element
        element = {
            **self._create_base_element(),
            "id": str(uuid.uuid4()),
            "type": "image",
            "x": float(x),
            "y": float(y),
            "width": float(w),
            "height": float(h),
            "strokeColor": "transparent",
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 0,
            "index": self._get_index(),
            "roundness": None,
            "fileId": file_id,
            "status": "saved",
            "scale": [1, 1],
            "crop": None,
        }
        
        return element
    
    def _create_text_element(self, text_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert text data to Excalidraw text element"""
        bbox = self._get_value(text_data, 'bbox', [0, 0, 100, 25])
        
        # Handle BoundingBox object
        if hasattr(bbox, 'x'):
            x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
        # Handle dict format
        elif isinstance(bbox, dict):
            x = bbox.get('x', 0)
            y = bbox.get('y', 0)
            w = bbox.get('width', bbox.get('w', 100))
            h = bbox.get('height', bbox.get('h', 25))
        # Handle list format
        elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x, y, w, h = bbox
            if w > 10000 or h > 10000:
                x, y, x2, y2 = bbox
                w, h = x2 - x, y2 - y
        else:
            x, y, w, h = 0, 0, 100, 25
        
        text = self._get_value(text_data, 'text', '')
        color = self._get_value(text_data, 'color', '#1e1e1e')
        
        # Handle both flat and nested font properties
        # JSON format has font as nested object: {"font": {"size": 16, "family": "helvetica", "classified_font": "Roboto"}}
        # Python object format has flat: {"font_size": 16, "font_family": "helvetica", "classified_font": "Roboto"}
        font_data = self._get_value(text_data, 'font', {})
        if font_data and isinstance(font_data, dict):
            # Nested format (from JSON)
            original_font_size = font_data.get('size', 16)
            classified_font = font_data.get('classified_font', '')
        else:
            # Flat format (from Python objects)
            original_font_size = self._get_value(text_data, 'font_size', 16)
            classified_font = self._get_value(text_data, 'classified_font', '')
        
        # Map classified font → anchor font → Excalidraw numeric font family ID
        font_family = map_classified_font_to_excalidraw_id(classified_font)
        
        # Determine text alignment
        text_align = self._get_value(text_data, 'text_align', 'left')
        if text_align not in ['left', 'center', 'right']:
            text_align = 'left'
        
        # Calculate appropriate font size to fit within bounding box
        font_size = self._calculate_font_size_for_box(text, w, h, original_font_size)
        
        element = {
            **self._create_base_element(),
            "id": str(uuid.uuid4()),
            "type": "text",
            "x": float(x),
            "y": float(y),
            "width": float(w),
            "height": float(h),
            "strokeColor": color,
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 1,
            "index": self._get_index(),
            "roundness": None,
            "text": text,
            "fontSize": int(font_size),
            "fontFamily": font_family,
            "textAlign": text_align,
            "verticalAlign": "top",
            "containerId": None,
            "originalText": text,
            "autoResize": True,
            "lineHeight": 1.25,
        }
        
        return element
    
    def _create_shape_element(self, shape: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert a detected shape to Excalidraw element"""
        bbox = self._get_value(shape, 'bbox', [0, 0, 100, 100])
        shape_type = self._get_value(shape, 'type', 'rectangle')
        
        # Handle BoundingBox object
        if hasattr(bbox, 'x'):
            x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
        # Handle dict format
        elif isinstance(bbox, dict):
            x = bbox.get('x', 0)
            y = bbox.get('y', 0)
            w = bbox.get('width', bbox.get('w', 100))
            h = bbox.get('height', bbox.get('h', 100))
        # Handle list format
        elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x, y, w, h = bbox
            if w > 10000 or h > 10000:
                x, y, x2, y2 = bbox
                w, h = x2 - x, y2 - y
        else:
            x, y, w, h = 0, 0, 100, 100
        
        # Map shape types to Excalidraw types
        shape_type_map = {
            'rectangle': 'rectangle',
            'circle': 'ellipse',
            'ellipse': 'ellipse',
            'diamond': 'diamond',
        }
        
        if isinstance(shape_type, str):
            excalidraw_type = shape_type_map.get(shape_type.lower(), 'rectangle')
        else:
            excalidraw_type = 'rectangle'
        
        element = {
            **self._create_base_element(),
            "id": str(uuid.uuid4()),
            "type": excalidraw_type,
            "x": float(x),
            "y": float(y),
            "width": float(w),
            "height": float(h),
            "strokeColor": self._get_value(shape, 'stroke_color', '#1e1e1e'),
            "backgroundColor": self._get_value(shape, 'fill_color', 'transparent'),
            "fillStyle": self._get_value(shape, 'fill_style', 'solid'),
            "strokeWidth": self._get_value(shape, 'stroke_width', 2),
            "index": self._get_index(),
            "roundness": {"type": 2} if excalidraw_type == 'rectangle' else None,
        }
        
        return element
    
    def convert(
        self, 
        extraction_data: Dict[str, Any], 
        statistics: Dict[str, Any],
        download_images: bool = True
    ) -> Dict[str, Any]:
        """
        Convert extraction data to Excalidraw JSON format
        
        Args:
            extraction_data: The extraction data from RasterToSVGConverter.
                           Can be either:
                           - Direct format: {'text_elements': [...], 'containers': [...], ...}
                           - Nested format: {'stages': {'text_detection': {...}, ...}, ...}
            statistics: Statistics from the extraction
            download_images: Whether to download images from S3 URLs (default: True)
        
        Returns:
            Complete Excalidraw JSON structure
        """
        elements = []
        files = {}
        self.index_counter = 0  # Reset counter
        
        print("Converting to Excalidraw format...")
        
        # Handle both nested (JSON from S3) and direct (Python object) formats
        if 'stages' in extraction_data:
            # Nested format from S3 JSON
            print("  Detected nested JSON format, restructuring...")
            stages = extraction_data.get('stages', {})
            
            # Safely get elements from each stage
            text_stage = stages.get('text_detection', {})
            container_stage = stages.get('container_detection', {})
            image_stage = stages.get('image_detection', {})
            background_data = stages.get('background_extraction', {})
            
            text_elements = text_stage.get('elements', []) if text_stage else []
            containers = container_stage.get('elements', []) if container_stage else []
            images = image_stage.get('elements', []) if image_stage else []
            
            print(f"    Text elements from JSON: {len(text_elements)}")
            print(f"    Containers from JSON: {len(containers)}")
            print(f"    Images from JSON: {len(images)}")
            
            logos = []
            shapes = []
            
            # For images, we don't have the split in JSON, so use all images
            images_in_containers = images  # Will be rendered
            standalone_images = []
        else:
            # Direct format from Python objects
            text_elements = extraction_data.get('text_elements', extraction_data.get('text', []))
            containers = extraction_data.get('containers', [])
            images_in_containers = extraction_data.get('images_in_containers', [])
            standalone_images = extraction_data.get('standalone_images', [])
            logos = extraction_data.get('logos', [])
            shapes = extraction_data.get('shapes', [])
            background_data = extraction_data.get('background_element')
        
        # Layer 0: Background image with border (if available)
        background_element = background_data
        if background_element and download_images:
            print(f"  Processing background image...")
            try:
                # Create the background image element
                bg_img_element = self._create_image_element(background_element, files)
                if bg_img_element:
                    elements.append(bg_img_element)
                    
                    # Add a border rectangle around the background
                    bbox = self._get_value(background_element, 'bbox')
                    if hasattr(bbox, 'x'):
                        x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
                    else:
                        x, y, w, h = 0, 0, statistics.get('dimensions', (800, 600))[0], statistics.get('dimensions', (800, 600))[1]
                    
                    border_element = {
                        **self._create_base_element(),
                        "id": str(uuid.uuid4()),
                        "type": "rectangle",
                        "x": float(x),
                        "y": float(y),
                        "width": float(w),
                        "height": float(h),
                        "strokeColor": "#000000",  # Black border
                        "backgroundColor": "transparent",
                        "fillStyle": "solid",
                        "strokeWidth": 2,
                        "index": self._get_index(),
                        "roundness": None,  # Square corners for background border
                    }
                    elements.append(border_element)
                    print(f"    ✓ Added background with border ({w}x{h})")
            except Exception as e:
                print(f"    Warning: Failed to add background: {e}")
        
        # Layer 1: Containers (background rectangles)
        print(f"  Processing {len(containers)} containers...")
        for container in containers:
            try:
                element = self._create_container_element(container)
                elements.append(element)
            except Exception as e:
                print(f"    Warning: Failed to convert container: {e}")
        
        # Layer 2: Shapes
        print(f"  Processing {len(shapes)} shapes...")
        for shape in shapes:
            try:
                element = self._create_shape_element(shape)
                if element:
                    elements.append(element)
            except Exception as e:
                print(f"    Warning: Failed to convert shape: {e}")
        
        # Layer 3: Images (if download_images is True)
        if download_images:
            all_images = images_in_containers + standalone_images + logos
            
            print(f"  Processing {len(all_images)} images (using embedded base64)...")
            for idx, image in enumerate(all_images, 1):
                try:
                    element = self._create_image_element(image, files)
                    if element:
                        elements.append(element)
                except Exception as e:
                    print(f"    Warning: Failed to convert image {idx}: {e}")
        else:
            print("  Skipping image download (download_images=False)")
        
        # Layer 4: Text elements (foreground)
        print(f"  Processing {len(text_elements)} text elements...")
        for text_data in text_elements:
            try:
                element = self._create_text_element(text_data)
                elements.append(element)
            except Exception as e:
                print(f"    Warning: Failed to convert text: {e}")
        
        # Create complete Excalidraw structure
        excalidraw_json = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://layoutlabs.com",
            "elements": elements,
            "appState": {
                "viewBackgroundColor": "#ffffff",
                "currentItemStrokeColor": "#000000",
                "currentItemBackgroundColor": "transparent",
                "currentItemFillStyle": "solid",
                "currentItemStrokeWidth": 2,
                "currentItemStrokeStyle": "solid",
                "currentItemRoughness": 0,
                "currentItemOpacity": 100,
                "scrollX": 0,
                "scrollY": 0,
                "zoom": {"value": 1},
                "gridSize": None,
            },
            "files": files,
        }
        
        print(f"\n✓ Conversion complete:")
        print(f"  Total elements:  {len(elements)}")
        print(f"  Embedded files:  {len(files)}")
        
        return excalidraw_json
    
    def convert_to_file(
        self, 
        extraction_data: Dict[str, Any], 
        statistics: Dict[str, Any],
        output_path: str,
        download_images: bool = True
    ) -> str:
        """
        Convert extraction data to Excalidraw JSON and save to file
        
        Args:
            extraction_data: The extraction data from RasterToSVGConverter
            statistics: Statistics from the extraction
            output_path: Path where to save the .excalidraw file
            download_images: Whether to download images from S3 URLs
        
        Returns:
            Path to the saved file
        """
        import json
        from pathlib import Path
        
        # Convert to Excalidraw format
        excalidraw_json = self.convert(extraction_data, statistics, download_images)
        
        # Ensure .excalidraw extension
        output_path = Path(output_path)
        if output_path.suffix not in ['.excalidraw', '.json']:
            output_path = output_path.with_suffix('.excalidraw')
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(excalidraw_json, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved Excalidraw file: {output_path}")
        
        return str(output_path)
