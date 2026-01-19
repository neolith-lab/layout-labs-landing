"""
SVG generation module
Steps 9, 10, 11: Convert elements to SVG and compose layers
Updated to support containers, logos, and proper layering
"""

import cv2
import svgwrite
from svgwrite import cm, mm
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import logging
import base64
import io
import re
import os
from PIL import Image, ImageDraw, ImageFont

# Optional: for downloading fonts
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from text_extractor import TextElement
from image_detector import ImageElement
from shape_detector import ShapeElement, ShapeType
from utils import rgb_to_hex, BoundingBox, save_debug_image
from config import SVG_OUTPUT, DEBUG

logger = logging.getLogger(__name__)


class SVGGenerator:
    """Generate SVG from detected elements with proper layering"""
    
    def __init__(self, config: Dict = None):
        self.config = config or SVG_OUTPUT
        self.logger = logging.getLogger(__name__)
        self.dwg = None  # Will be set when generating SVG
    
    def generate_layered_svg(self, width: int, height: int,
                            background_image: np.ndarray = None,
                            containers: List = None,
                            images_in_containers: List = None,
                            standalone_images: List = None,
                            logos: List = None,
                            shapes: List = None,
                            text_elements: List = None,
                            output_path: str = 'output.svg',
                            original_image: np.ndarray = None) -> str:
        """
        Generate complete SVG with proper layering
        
        Layer Order (bottom to top) - REVERSE of extraction order:
        1. Background - clean background (extracted last)
        2. Containers - placed first on top of background (extracted 3rd)
        3. Images (in containers and standalone) - placed second (extracted 2nd)
        4. Text - placed last on top (extracted 1st)
        
        Extraction order was: Text → Images → Containers → Background
        Placement order is: Background → Containers → Images → Text
        
        Args:
            width: SVG canvas width
            height: SVG canvas height
            background_image: Clean background image
            containers: Container elements (rounded rectangles, cards)
            images_in_containers: Images that are inside containers
            standalone_images: Images not in containers
            logos: Detected logo elements
            shapes: Decorative shapes (unused)
            text_elements: Text elements
            output_path: Output SVG file path
        
        Returns:
            Path to generated SVG file
        """
        logger.info(f"Generating layered SVG: {output_path}")
        
        containers = containers or []
        images_in_containers = images_in_containers or []
        standalone_images = standalone_images or []
        logos = logos or []
        shapes = shapes or []
        text_elements = text_elements or []
        
        # Create SVG drawing
        dwg = svgwrite.Drawing(output_path, size=(int(width), int(height)), profile='full')
        self.dwg = dwg  # Store reference for use in helper methods
        
        # Add defs for any reusable elements (like rounded rect clips)
        defs = dwg.defs
        
        # Collect unique fonts from text elements and embed them
        if text_elements:
            self._add_google_fonts(dwg, text_elements)
        
        # For debug: we'll build a composite image layer by layer
        if DEBUG.get('save_intermediate_steps', False):
            # Start with background as base for debug visualization
            debug_composite = background_image.copy() if background_image is not None else np.zeros((height, width, 3), dtype=np.uint8)
        
        # Layer 1: Background
        bg_layer = dwg.g(id='layer_background')
        if background_image is not None:
            self._add_background_layer(dwg, bg_layer, background_image, width, height)
        dwg.add(bg_layer)
        
        # Save debug: Layer 1 - Background only
        if DEBUG.get('save_intermediate_steps', False):
            logger.info("Saving debug image: Layer 1 - Background")
            save_debug_image(debug_composite.copy(), '06_layer1_background.png',
                           DEBUG.get('output_dir', './debug_output'))
        
        # Layer 2: Containers (rounded rectangles, cards)
        container_layer = dwg.g(id='layer_containers')
        for i, container in enumerate(containers):
            self._add_container(dwg, container_layer, container, f'container_{i}')
        dwg.add(container_layer)
        
        # Save debug: Layer 2 - Background + Containers
        if DEBUG.get('save_intermediate_steps', False):
            logger.info("Saving debug image: Layer 2 - Background + Containers")
            debug_composite = self._overlay_containers_on_image(debug_composite, containers)
            save_debug_image(debug_composite.copy(), '06_layer2_containers.png',
                           DEBUG.get('output_dir', './debug_output'))
        
        # Layer 3: Images (both in containers and standalone)
        # These go on top of containers
        images_in_container_layer = dwg.g(id='layer_images_in_containers')
        for i, img_elem in enumerate(images_in_containers):
            self._add_image_element(dwg, images_in_container_layer, img_elem, f'img_container_{i}')
        dwg.add(images_in_container_layer)
        
        # Save debug: Layer 3 - Background + Containers + Images in containers
        if DEBUG.get('save_intermediate_steps', False):
            logger.info("Saving debug image: Layer 3 - + Images in containers")
            debug_composite = self._overlay_images_on_image(debug_composite, images_in_containers)
            save_debug_image(debug_composite.copy(), '06_layer3_images_in_containers.png',
                           DEBUG.get('output_dir', './debug_output'))
        
        # Layer 4: Standalone images and logos
        standalone_layer = dwg.g(id='layer_standalone_images')
        
        # Add standalone images
        for i, img_elem in enumerate(standalone_images):
            self._add_image_element(dwg, standalone_layer, img_elem, f'img_standalone_{i}')
        
        # Add logos
        for i, logo in enumerate(logos):
            self._add_logo_element(dwg, standalone_layer, logo, f'logo_{i}')
        
        dwg.add(standalone_layer)
        
        # Save debug: Layer 4 - + Standalone images
        if DEBUG.get('save_intermediate_steps', False):
            logger.info("Saving debug image: Layer 4 - + Standalone images")
            debug_composite = self._overlay_images_on_image(debug_composite, standalone_images)
            save_debug_image(debug_composite.copy(), '06_layer4_standalone_images.png',
                           DEBUG.get('output_dir', './debug_output'))
        
        # Layer 5: Text (topmost layer)
        # Text goes on top of everything - extracted first, placed last
        text_layer = dwg.g(id='layer_text')
        self._add_text_layer(dwg, text_layer, text_elements)
        dwg.add(text_layer)
        
        # Save debug: Layer 5 - + Text (final composite)
        if DEBUG.get('save_intermediate_steps', False):
            logger.info("Saving debug image: Layer 5 - + Text (final)")
            debug_composite = self._overlay_text_on_image(debug_composite, text_elements)
            save_debug_image(debug_composite.copy(), '06_layer5_text_final.png',
                           DEBUG.get('output_dir', './debug_output'))
        
        # Save SVG
        dwg.save()
        logger.info(f"Layered SVG generated successfully: {output_path}")
        
        return output_path
    
    def _add_google_fonts(self, dwg: svgwrite.Drawing, text_elements: List[TextElement]):
        """
        Add fonts to SVG with multiple fallback strategies:
        
        1. Primary: Use web-safe font stack with similar appearance
        2. Alternative: Embed Google Fonts via @import (requires internet)
        3. Best: Embed font files directly as base64 (fully portable)
        4. Fallback: Generic font families
        """
        # Collect unique fonts from all text elements
        unique_fonts = set()
        for text_elem in text_elements:
            if text_elem.classified_font:
                font_name = text_elem.classified_font
                unique_fonts.add(font_name)
        
        if not unique_fonts:
            return
        
        logger.info(f"Processing {len(unique_fonts)} fonts for SVG: {unique_fonts}")
        
        # Get config options
        embed_files = self.config.get('embed_font_files', False)
        font_strategy = self.config.get('font_embedding', 'both')
        
        # Option 1: Map Google Fonts to web-safe alternatives
        font_mapping = self._get_font_fallback_mapping()
        
        css_parts = []
        
        # If embedding is enabled, try to embed font files directly
        if embed_files and REQUESTS_AVAILABLE:
            logger.info("Attempting to embed font files directly...")
            for font_name in sorted(unique_fonts):
                embedded_css = self._embed_google_font(font_name)
                if embedded_css:
                    css_parts.append(embedded_css)
                    logger.info(f"  ✓ Embedded: {font_name}")
                else:
                    logger.info(f"  ✗ Failed to embed: {font_name} (will use fallback)")
        
        # Add Google Fonts import (for when internet is available and embedding failed)
        if font_strategy in ['google_fonts', 'both']:
            font_params = []
            for font_name in sorted(unique_fonts):
                url_safe_name = font_name.replace(' ', '+')
                font_params.append(f"family={url_safe_name}:wght@300;400;600;700")
            
            if font_params:
                fonts_url = "https://fonts.googleapis.com/css2?" + "&".join(font_params)
                css_parts.insert(0, f"@import url('{fonts_url}');")
        
        # Add CSS classes for font fallbacks
        for font_name in sorted(unique_fonts):
            fallback = font_mapping.get(font_name, font_mapping.get('default'))
            css_parts.append(f"""
/* Fallback for {font_name} */
.font-{font_name.lower().replace(' ', '-')} {{
    font-family: '{font_name}', {fallback};
}}""")
        
        style_content = "\n".join(css_parts)
        dwg.defs.add(dwg.style(style_content))
        
        logger.info(f"Added font CSS (strategy: {font_strategy}, embed_files: {embed_files})")
    
    def _get_font_fallback_mapping(self) -> dict:
        """
        Map Google Fonts to web-safe fallback font stacks
        
        Returns a dict mapping font names to CSS font-family fallback strings
        """
        return {
            # Sans-serif fonts
            'Roboto': "Arial, Helvetica, sans-serif",
            'Open Sans': "Arial, Helvetica, sans-serif",
            'Lato': "Arial, Helvetica, sans-serif",
            'Montserrat': "'Trebuchet MS', Arial, sans-serif",
            'Poppins': "Arial, Helvetica, sans-serif",
            'Inter': "Arial, Helvetica, sans-serif",
            'Nunito': "Arial, Helvetica, sans-serif",
            'Raleway': "'Trebuchet MS', Arial, sans-serif",
            'Ubuntu': "Arial, Helvetica, sans-serif",
            'Oswald': "'Arial Narrow', Arial, sans-serif",
            'Source Sans Pro': "Arial, Helvetica, sans-serif",
            'Bebas Neue': "'Arial Narrow', Impact, sans-serif",
            
            # Serif fonts
            'Playfair Display': "Georgia, 'Times New Roman', serif",
            'Merriweather': "Georgia, 'Times New Roman', serif",
            'Lora': "Georgia, 'Times New Roman', serif",
            'PT Serif': "Georgia, 'Times New Roman', serif",
            'Libre Baskerville': "'Book Antiqua', Georgia, serif",
            
            # Display/decorative fonts
            'Pacifico': "'Brush Script MT', cursive",
            'Dancing Script': "'Brush Script MT', cursive",
            'Lobster': "'Brush Script MT', cursive",
            
            # Monospace fonts
            'Roboto Mono': "'Courier New', Courier, monospace",
            'Source Code Pro': "'Courier New', Courier, monospace",
            'Fira Code': "'Courier New', Courier, monospace",
            
            # Default fallback
            'default': "Arial, Helvetica, sans-serif"
        }
    
    def _embed_google_font(self, font_name: str) -> str:
        """
        Download a Google Font and return it as a base64-encoded @font-face CSS
        
        This embeds the actual font file in the SVG for full portability.
        Requires the 'requests' library.
        
        Returns empty string if download fails.
        """
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available for font embedding")
            return ""
        
        try:
            # First, get the CSS from Google Fonts
            url_safe_name = font_name.replace(' ', '+')
            css_url = f"https://fonts.googleapis.com/css2?family={url_safe_name}:wght@400;700"
            
            # Use a browser-like user agent to get woff2 format
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(css_url, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch Google Font CSS for {font_name}")
                return ""
            
            css_content = response.text
            
            # Extract font URLs from the CSS
            # Look for url(...) patterns
            url_pattern = r'url\((https://fonts\.gstatic\.com/[^)]+)\)'
            font_urls = re.findall(url_pattern, css_content)
            
            if not font_urls:
                logger.warning(f"No font URLs found for {font_name}")
                return ""
            
            # Download and embed each font file
            embedded_css_parts = []
            for font_url in font_urls[:2]:  # Limit to 2 variants (regular + bold)
                try:
                    font_response = requests.get(font_url, headers=headers, timeout=10)
                    if font_response.status_code == 200:
                        # Encode font as base64
                        font_base64 = base64.b64encode(font_response.content).decode('utf-8')
                        
                        # Determine format
                        if '.woff2' in font_url:
                            font_format = 'woff2'
                            mime_type = 'font/woff2'
                        elif '.woff' in font_url:
                            font_format = 'woff'
                            mime_type = 'font/woff'
                        else:
                            font_format = 'truetype'
                            mime_type = 'font/ttf'
                        
                        # Create @font-face rule with embedded font
                        weight = '700' if 'bold' in font_url.lower() or '700' in font_url else '400'
                        embedded_css_parts.append(f"""
@font-face {{
    font-family: '{font_name}';
    font-weight: {weight};
    src: url('data:{mime_type};base64,{font_base64}') format('{font_format}');
}}""")
                        logger.debug(f"Embedded font: {font_name} weight {weight}")
                except Exception as e:
                    logger.warning(f"Failed to download font file: {e}")
            
            return "\n".join(embedded_css_parts)
            
        except Exception as e:
            logger.warning(f"Failed to embed Google Font {font_name}: {e}")
            return ""
    
    def _overlay_containers_on_image(self, image: np.ndarray, containers: List) -> np.ndarray:
        """Overlay actual container image data on debug image"""
        result = image.copy()
        for container in containers:
            bbox = container.bbox
            container_data = getattr(container, 'image_data', None)
            
            if container_data is not None and container_data.size > 0:
                # Ensure dimensions match
                target_h = bbox.y2 - bbox.y
                target_w = bbox.x2 - bbox.x
                
                if container_data.shape[0] != target_h or container_data.shape[1] != target_w:
                    container_data = cv2.resize(container_data, (target_w, target_h))
                
                # Paste container image data at bbox position
                try:
                    result[bbox.y:bbox.y2, bbox.x:bbox.x2] = container_data
                except ValueError:
                    # Handle edge cases where dimensions don't match exactly
                    h = min(container_data.shape[0], result.shape[0] - bbox.y)
                    w = min(container_data.shape[1], result.shape[1] - bbox.x)
                    result[bbox.y:bbox.y+h, bbox.x:bbox.x+w] = container_data[:h, :w]
            else:
                # Fallback: draw rectangle with fill color if no image data
                fill_color = getattr(container, 'fill_color', '#ffffff')
                if fill_color.startswith('#'):
                    r = int(fill_color[1:3], 16)
                    g = int(fill_color[3:5], 16)
                    b = int(fill_color[5:7], 16)
                    bgr_color = (b, g, r)
                else:
                    bgr_color = (255, 255, 255)
                
                # Draw filled rectangle
                cv2.rectangle(result, (bbox.x, bbox.y), (bbox.x2, bbox.y2), bgr_color, -1)
                
                # Draw border
                stroke_color = getattr(container, 'stroke_color', '#000000')
                if stroke_color.startswith('#'):
                    r = int(stroke_color[1:3], 16)
                    g = int(stroke_color[3:5], 16)
                    b = int(stroke_color[5:7], 16)
                    border_bgr = (b, g, r)
                else:
                    border_bgr = (0, 0, 0)
                cv2.rectangle(result, (bbox.x, bbox.y), (bbox.x2, bbox.y2), border_bgr, 2)
        
        return result
    
    def _overlay_images_on_image(self, image: np.ndarray, image_elements: List) -> np.ndarray:
        """Overlay image elements on debug image"""
        result = image.copy()
        for img_elem in image_elements:
            bbox = img_elem.bbox
            img_data = getattr(img_elem, 'image_data', None)
            
            if img_data is not None and img_data.size > 0:
                # Ensure dimensions match
                target_h = bbox.y2 - bbox.y
                target_w = bbox.x2 - bbox.x
                
                if img_data.shape[0] != target_h or img_data.shape[1] != target_w:
                    img_data = cv2.resize(img_data, (target_w, target_h))
                
                # Paste image data at bbox position
                try:
                    result[bbox.y:bbox.y2, bbox.x:bbox.x2] = img_data
                except ValueError:
                    # Handle edge cases where dimensions don't match exactly
                    h = min(img_data.shape[0], result.shape[0] - bbox.y)
                    w = min(img_data.shape[1], result.shape[1] - bbox.x)
                    result[bbox.y:bbox.y+h, bbox.x:bbox.x+w] = img_data[:h, :w]
            else:
                # No image data, draw placeholder rectangle
                cv2.rectangle(result, (bbox.x, bbox.y), (bbox.x2, bbox.y2), (128, 128, 128), -1)
                cv2.putText(result, "IMG", (bbox.x + 5, bbox.y + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return result
    
    def _overlay_text_on_image(self, image: np.ndarray, text_elements: List) -> np.ndarray:
        """Overlay text elements on debug image using actual rendered text images"""
        result = image.copy()
        
        # Check if we're using text-as-image rendering
        text_rendering = SVG_OUTPUT.get('text_rendering', 'svg')
        
        if text_rendering == 'image':
            # Use actual rendered text images for accurate preview
            for i, text_elem in enumerate(text_elements):
                bbox = text_elem.bbox
                
                # Get font info
                font_family = text_elem.classified_font or text_elem.font_family or 'Roboto'
                font_size = text_elem.font_size or 16
                font_weight = text_elem.font_weight or 'normal'
                is_bold = font_weight.lower() in ['bold', '700', '800', '900']
                
                # Get color
                if text_elem.color:
                    if isinstance(text_elem.color, str) and text_elem.color.startswith('#'):
                        hex_color = text_elem.color.lstrip('#')
                        color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                    elif isinstance(text_elem.color, (list, tuple)) and len(text_elem.color) >= 3:
                        color = tuple(text_elem.color[:3])
                    else:
                        color = (0, 0, 0)
                else:
                    color = (0, 0, 0)
                
                # Render the text image
                text_img = self._render_text_as_image(
                    text=text_elem.text,
                    font_family=font_family,
                    font_size=font_size,
                    color=color,
                    is_bold=is_bold
                )
                
                if text_img is not None:
                    # Convert RGBA to BGR for OpenCV
                    text_img_bgr = cv2.cvtColor(text_img, cv2.COLOR_RGBA2BGRA)
                    
                    # Get alpha channel
                    alpha = text_img[:, :, 3] / 255.0
                    
                    # Get dimensions
                    text_h, text_w = text_img.shape[:2]
                    x, y = bbox.x, bbox.y
                    
                    # Ensure we don't go out of bounds
                    if y + text_h > result.shape[0]:
                        text_h = result.shape[0] - y
                        text_img_bgr = text_img_bgr[:text_h, :]
                        alpha = alpha[:text_h, :]
                    if x + text_w > result.shape[1]:
                        text_w = result.shape[1] - x
                        text_img_bgr = text_img_bgr[:, :text_w]
                        alpha = alpha[:, :text_w]
                    
                    # Alpha blend the text onto the result
                    for c in range(3):  # BGR channels
                        result[y:y+text_h, x:x+text_w, c] = (
                            alpha * text_img_bgr[:, :, c] +
                            (1 - alpha) * result[y:y+text_h, x:x+text_w, c]
                        )
                else:
                    # Fallback to OpenCV text rendering
                    self._overlay_text_opencv(result, text_elem)
        else:
            # Use original OpenCV text rendering
            for text_elem in text_elements:
                self._overlay_text_opencv(result, text_elem)
        
        return result
    
    def _overlay_text_opencv(self, image: np.ndarray, text_elem: TextElement):
        """Helper method to overlay text using OpenCV (fallback)"""
        bbox = text_elem.bbox
        text = getattr(text_elem, 'text', '')
        color = getattr(text_elem, 'color', '#000000')
        
        # Convert hex color to BGR
        if isinstance(color, str) and color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            bgr_color = (b, g, r)
        else:
            bgr_color = (0, 0, 0)
        
        # Get text properties
        font_size = getattr(text_elem, 'font_size', 12)
        font_weight = getattr(text_elem, 'font_weight', 'normal')
        
        # Calculate proper scale and thickness
        scale = max(0.3, min(2.0, font_size / 30.0))
        
        # Bold text should be thicker
        if font_weight == 'bold':
            thickness = max(2, int(scale * 3))
        else:
            thickness = max(1, int(scale * 1.5))
        
        # Handle multi-line text
        lines = text.split('\n') if '\n' in text else [text]
        
        if len(lines) > 1:
            # Multi-line text
            line_height = int(font_size * 1.2)
            total_height = len(lines) * line_height
            y_start = bbox.y + (bbox.h - total_height) // 2 + int(font_size * 0.75)
            
            for line_idx, line in enumerate(lines):
                if line.strip():
                    y_pos = y_start + (line_idx * line_height)
                    cv2.putText(image, line[:50], (bbox.x + 2, y_pos),
                               cv2.FONT_HERSHEY_SIMPLEX, scale, bgr_color, thickness, cv2.LINE_AA)
        else:
            # Single line - vertically centered
            y_center = bbox.y + (bbox.h // 2)
            y_baseline = y_center + int(font_size * 0.35)
            
            cv2.putText(image, text[:50], (bbox.x + 2, y_baseline),
                       cv2.FONT_HERSHEY_SIMPLEX, scale, bgr_color, thickness, cv2.LINE_AA)
    
    def _add_container(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                      container, container_id: str):
        """Add a container element (usually rounded rectangle)"""
        bbox = container.bbox
        
        # Get container properties
        corner_radius = getattr(container, 'corner_radius', 0)
        fill_color = getattr(container, 'fill_color', '#ffffff')
        stroke_color = getattr(container, 'stroke_color', '#cccccc')
        stroke_width = getattr(container, 'stroke_width', 1)
        has_shadow = getattr(container, 'has_shadow', False)
        
        # Ensure numeric values are Python native types
        x = int(bbox.x)
        y = int(bbox.y)
        w = int(bbox.w)
        h = int(bbox.h)
        rx = float(corner_radius) if corner_radius else 0
        sw = int(stroke_width)
        
        # Add shadow if present
        if has_shadow:
            shadow_offset = 3
            shadow = dwg.rect(
                insert=(x + shadow_offset, y + shadow_offset),
                size=(w, h),
                rx=rx, ry=rx,
                fill='rgba(0,0,0,0.1)',
                id=f'{container_id}_shadow'
            )
            layer.add(shadow)
        
        # Add rounded rectangle
        rect = dwg.rect(
            insert=(x, y),
            size=(w, h),
            rx=rx, ry=rx,
            fill=fill_color,
            stroke=stroke_color,
            stroke_width=sw,
            id=container_id
        )
        layer.add(rect)
    
    def _add_logo_element(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                         logo, logo_id: str):
        """Add a logo as an embedded image"""
        bbox = logo.bbox
        
        # Get logo image data if available
        if hasattr(logo, 'image_data') and logo.image_data is not None:
            img_data = self._numpy_to_base64(logo.image_data)
            
            layer.add(dwg.image(
                href=f'data:image/png;base64,{img_data}',
                insert=(int(bbox.x), int(bbox.y)),
                size=(int(bbox.w), int(bbox.h)),
                id=logo_id
            ))
        else:
            # Placeholder rectangle for logo
            layer.add(dwg.rect(
                insert=(int(bbox.x), int(bbox.y)),
                size=(int(bbox.w), int(bbox.h)),
                fill='#f0f0f0',
                stroke='#ccc',
                stroke_width=1,
                id=logo_id
            ))
    
    def _add_image_element(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                          img_elem, img_id: str):
        """Add an image element"""
        bbox = img_elem.bbox
        
        if hasattr(img_elem, 'image_data') and img_elem.image_data is not None:
            img_data = self._numpy_to_base64(img_elem.image_data)
            
            layer.add(dwg.image(
                href=f'data:image/png;base64,{img_data}',
                insert=(int(bbox.x), int(bbox.y)),
                size=(int(bbox.w), int(bbox.h)),
                id=img_id
            ))
    
    def _add_shape_element(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                          shape: ShapeElement, shape_id: str):
        """Add a shape element based on its type"""
        if shape.shape_type == ShapeType.RECTANGLE:
            self._add_rectangle(dwg, layer, shape, shape_id)
        elif shape.shape_type == ShapeType.CIRCLE:
            self._add_circle(dwg, layer, shape, shape_id)
        elif shape.shape_type == ShapeType.ELLIPSE:
            self._add_ellipse(dwg, layer, shape, shape_id)
        elif shape.shape_type == ShapeType.LINE:
            self._add_line(dwg, layer, shape, shape_id)
        elif shape.shape_type == ShapeType.ARROW:
            self._add_arrow(dwg, layer, shape, shape_id)
        elif shape.shape_type == ShapeType.POLYGON:
            self._add_polygon(dwg, layer, shape, shape_id)
    
    # ... keep existing generate_svg method for backward compatibility ...
    def generate_svg(self, width: int, height: int,
                    background_image: np.ndarray = None,
                    text_elements: List[TextElement] = None,
                    image_elements: List[ImageElement] = None,
                    shape_elements: List[ShapeElement] = None,
                    output_path: str = 'output.svg') -> str:
        """
        Generate complete SVG from all elements (original method for compatibility)
        """
        logger.info(f"Generating SVG: {output_path}")
        
        # Create SVG drawing
        dwg = svgwrite.Drawing(output_path, size=(int(width), int(height)), profile='full')
        self.dwg = dwg  # Store reference for use in helper methods
        
        # Add layers in order
        layer_order = self.config.get('layer_order', 
                                     ['background', 'shapes', 'images', 'text'])
        
        for layer_name in layer_order:
            layer = dwg.g(id=f'layer_{layer_name}')
            
            if layer_name == 'background' and background_image is not None:
                self._add_background_layer(dwg, layer, background_image, width, height)
            elif layer_name == 'shapes' and shape_elements:
                self._add_shapes_layer(dwg, layer, shape_elements)
            elif layer_name == 'images' and image_elements:
                self._add_images_layer(dwg, layer, image_elements)
            elif layer_name == 'text' and text_elements:
                self._add_text_layer(dwg, layer, text_elements)
            
            dwg.add(layer)
        
        dwg.save()
        logger.info(f"SVG generated successfully: {output_path}")
        
        return output_path
    
    def _add_background_layer(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                             background: np.ndarray, width: int, height: int):
        """Add background image as layer"""
        logger.info("Adding background layer...")
        
        background_data = self._numpy_to_base64(background)
        
        layer.add(dwg.image(href=f'data:image/png;base64,{background_data}',
                           insert=(0, 0),
                           size=(int(width), int(height))))
    
    def _add_shapes_layer(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                         shapes: List[ShapeElement]):
        """Add shapes to layer"""
        logger.info(f"Adding {len(shapes)} shapes to layer...")
        
        for i, shape in enumerate(shapes):
            shape_id = f'shape_{i}'
            self._add_shape_element(dwg, layer, shape, shape_id)
    
    def _add_rectangle(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                      shape: ShapeElement, shape_id: str):
        """Add rectangle to SVG"""
        bbox = shape.bbox
        
        if 'rect' in shape.properties:
            # Use rotated rectangle if available
            rect = shape.properties['rect']
            center, size, angle = rect
            
            # For rotated rectangles, use polygon
            box = cv2.boxPoints(rect)
            box = np.int0(box)
            points = [(float(pt[0]), float(pt[1])) for pt in box]
            
            layer.add(dwg.polygon(points=points,
                                 fill=shape.fill_color,
                                 stroke=shape.stroke_color,
                                 stroke_width=int(shape.stroke_width),
                                 id=shape_id))
        else:
            # Regular rectangle
            layer.add(dwg.rect(insert=(int(bbox.x), int(bbox.y)),
                              size=(int(bbox.w), int(bbox.h)),
                              fill=shape.fill_color,
                              stroke=shape.stroke_color,
                              stroke_width=int(shape.stroke_width),
                              id=shape_id))
    
    def _add_circle(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                   shape: ShapeElement, shape_id: str):
        """Add circle to SVG"""
        center = shape.properties.get('center', (0, 0))
        radius = shape.properties.get('radius', 10)
        
        layer.add(dwg.circle(center=(float(center[0]), float(center[1])),
                            r=float(radius),
                            fill=shape.fill_color,
                            stroke=shape.stroke_color,
                            stroke_width=int(shape.stroke_width),
                            id=shape_id))
    
    def _add_ellipse(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                    shape: ShapeElement, shape_id: str):
        """Add ellipse to SVG"""
        ellipse_data = shape.properties.get('ellipse')
        if ellipse_data:
            (center, axes, angle) = ellipse_data
            rx, ry = axes[0] / 2, axes[1] / 2
            
            # Create ellipse
            el = dwg.ellipse(center=(float(center[0]), float(center[1])),
                            r=(float(rx), float(ry)),
                            fill=shape.fill_color,
                            stroke=shape.stroke_color,
                            stroke_width=int(shape.stroke_width),
                            id=shape_id)
            
            # Apply rotation if needed
            if angle != 0:
                el.rotate(float(angle), center=(float(center[0]), float(center[1])))
            
            layer.add(el)
    
    def _add_line(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                 shape: ShapeElement, shape_id: str):
        """Add line to SVG"""
        # Get line endpoints from contour
        contour = shape.contour.squeeze()
        if len(contour) >= 2:
            start = (float(contour[0][0]), float(contour[0][1]))
            end = (float(contour[-1][0]), float(contour[-1][1]))
            
            layer.add(dwg.line(start=start,
                              end=end,
                              stroke=shape.stroke_color,
                              stroke_width=int(shape.stroke_width),
                              id=shape_id))
    
    def _add_arrow(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                  shape: ShapeElement, shape_id: str):
        """Add arrow to SVG"""
        # Simplified arrow rendering as polygon
        points = shape.properties.get('points', [])
        if len(points) > 0:
            points = [(float(pt[0][0]), float(pt[0][1])) for pt in points]
            layer.add(dwg.polygon(points=points,
                                 fill=shape.fill_color,
                                 stroke=shape.stroke_color,
                                 stroke_width=int(shape.stroke_width),
                                 id=shape_id))
    
    def _add_polygon(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                    shape: ShapeElement, shape_id: str):
        """Add polygon to SVG"""
        points = shape.properties.get('points', [])
        if len(points) > 0:
            points = [(float(pt[0][0]), float(pt[0][1])) for pt in points]
            layer.add(dwg.polygon(points=points,
                                 fill=shape.fill_color,
                                 stroke=shape.stroke_color,
                                 stroke_width=int(shape.stroke_width),
                                 id=shape_id))
    
    def _add_images_layer(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                         images: List[ImageElement]):
        """Add embedded images to layer"""
        logger.info(f"Adding {len(images)} images to layer...")
        
        for i, img_elem in enumerate(images):
            self._add_image_element(dwg, layer, img_elem, f'image_{i}')
    
    def _add_text_layer(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                       texts: List[TextElement]):
        """Add text elements to layer with proper positioning and multi-line support"""
        logger.info(f"Adding {len(texts)} text elements to layer...")
        
        # Check if we should render text as images
        text_rendering = SVG_OUTPUT.get('text_rendering', 'svg')
        
        if text_rendering == 'image':
            # Render all text as images for guaranteed font appearance
            for i, text_elem in enumerate(texts):
                self._add_text_as_image(layer, text_elem, index=i)
                # Log metadata
                if text_elem.classified_font:
                    logger.debug(f"Text #{i} (as image): '{text_elem.text[:30]}...' | Font: {text_elem.classified_font} | "
                               f"Size: {text_elem.font_size}px")
            return
        
        # Original SVG text rendering
        # Get font fallback mapping
        font_mapping = self._get_font_fallback_mapping()
        
        for i, text_elem in enumerate(texts):
            bbox = text_elem.bbox
            
            # Build font family with proper fallback chain
            if text_elem.classified_font:
                classified = text_elem.classified_font
                fallback = font_mapping.get(classified, font_mapping.get('default'))
                # Quote the primary font name, then add fallbacks
                font_family = f"'{classified}', {fallback}"
            else:
                font_family = font_mapping.get('default')
            
            # Handle multi-line text
            lines = text_elem.text.split('\n') if '\n' in text_elem.text else [text_elem.text]
            
            if len(lines) > 1 or text_elem.num_lines > 1:
                # Multi-line text using tspan elements
                self._add_multiline_text(dwg, layer, text_elem, lines, font_family, i)
            else:
                # Single line text - center vertically in bbox
                self._add_single_line_text(dwg, layer, text_elem, font_family, i)
            
            # Log metadata
            if text_elem.classified_font:
                logger.debug(f"Text #{i}: '{text_elem.text[:30]}...' | Font: {text_elem.classified_font} | "
                           f"Size: {text_elem.font_size}px | Lines: {text_elem.num_lines}")
    
    def _add_single_line_text(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                             text_elem: TextElement, font_family: str, index: int):
        """Add single-line text centered in its bounding box"""
        bbox = text_elem.bbox
        
        # Calculate vertical center position
        # In SVG, text y-position is at the baseline, not top
        # For vertical centering: middle of bbox + some offset for baseline
        # Approximate baseline offset is ~0.75 of font size from center
        y_center = bbox.y + (bbox.h / 2.0)
        y_baseline = y_center + (text_elem.font_size * 0.35)  # Adjust baseline
        
        # Horizontal start (left-aligned for now)
        x = float(bbox.x)
        
        # Create text element
        text = dwg.text(text_elem.text,
                       insert=(x, y_baseline),
                       fill=text_elem.color,
                       font_family=font_family,
                       font_size=f'{int(text_elem.font_size)}px',
                       font_weight=text_elem.font_weight,
                       font_style=text_elem.font_style,
                       id=f'text_{index}')
        
        layer.add(text)
    
    def _add_multiline_text(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                           text_elem: TextElement, lines: List[str], font_family: str, index: int):
        """Add multi-line text with proper line spacing"""
        bbox = text_elem.bbox
        
        # Calculate line height (typically 1.2x font size)
        line_height = text_elem.font_size * 1.2
        
        # Calculate total text block height
        total_text_height = len(lines) * line_height
        
        # Start position - center the text block vertically
        y_start = bbox.y + (bbox.h - total_text_height) / 2.0 + text_elem.font_size * 0.75
        
        # Horizontal start
        x = float(bbox.x)
        
        # Create text element with tspan for each line
        text = dwg.text('',
                       insert=(x, y_start),
                       fill=text_elem.color,
                       font_family=font_family,
                       font_size=f'{int(text_elem.font_size)}px',
                       font_weight=text_elem.font_weight,
                       font_style=text_elem.font_style,
                       id=f'text_{index}')
        
        # Add each line as a tspan
        for line_idx, line in enumerate(lines):
            if line.strip():  # Skip empty lines
                tspan = dwg.tspan(line,
                                 x=[x],
                                 dy=[f'{line_height}px' if line_idx > 0 else '0'])
                text.add(tspan)
        
        layer.add(text)
    
    def _numpy_to_base64(self, image: np.ndarray) -> str:
        """Convert numpy array to base64 encoded PNG"""
        # Convert BGR to RGB
        if len(image.shape) == 3:
            image = image[:, :, ::-1]
        
        # Convert to PIL Image
        pil_img = Image.fromarray(image)
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        pil_img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Encode to base64
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        return img_base64
    
    def _get_font_path(self, font_family: str, is_bold: bool = False) -> Optional[str]:
        """
        Get the path to a font file, downloading Google Fonts if needed.
        Returns None if font cannot be found/downloaded.
        """
        # Create fonts cache directory
        fonts_dir = os.path.join(os.path.dirname(__file__), '.font_cache')
        os.makedirs(fonts_dir, exist_ok=True)
        
        # Normalize font name for filename
        font_name_normalized = font_family.replace(' ', '')
        weight = 'Bold' if is_bold else 'Regular'
        font_filename = f"{font_name_normalized}-{weight}.ttf"
        font_path = os.path.join(fonts_dir, font_filename)
        
        # Check if font is already cached
        if os.path.exists(font_path):
            return font_path
        
        # Try to download from Google Fonts
        if REQUESTS_AVAILABLE:
            try:
                # Google Fonts API URL
                font_url_name = font_family.replace(' ', '+')
                weight_num = '700' if is_bold else '400'
                
                # Use the Google Fonts CSS API to get the actual font URL
                css_url = f"https://fonts.googleapis.com/css2?family={font_url_name}:wght@{weight_num}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = requests.get(css_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    # Extract TTF/WOFF2 URL from CSS
                    css_content = response.text
                    # Look for url() in the CSS
                    url_match = re.search(r'url\((https://fonts\.gstatic\.com/[^)]+)\)', css_content)
                    if url_match:
                        font_url = url_match.group(1)
                        
                        # Download the font file
                        font_response = requests.get(font_url, headers=headers, timeout=30)
                        if font_response.status_code == 200:
                            # Determine extension from URL or content-type
                            if '.woff2' in font_url:
                                # Convert WOFF2 to TTF or use as-is with PIL
                                font_path = os.path.join(fonts_dir, f"{font_name_normalized}-{weight}.woff2")
                            else:
                                font_path = os.path.join(fonts_dir, font_filename)
                            
                            with open(font_path, 'wb') as f:
                                f.write(font_response.content)
                            
                            self.logger.info(f"Downloaded font: {font_family} ({weight})")
                            return font_path
                            
            except Exception as e:
                self.logger.warning(f"Failed to download font {font_family}: {e}")
        
        # Fallback to system fonts
        system_font_paths = [
            # macOS
            f"/Library/Fonts/{font_family}.ttf",
            f"/Library/Fonts/{font_family.replace(' ', '')}.ttf",
            f"/System/Library/Fonts/{font_family}.ttf",
            os.path.expanduser(f"~/Library/Fonts/{font_family}.ttf"),
            # Linux
            f"/usr/share/fonts/truetype/{font_family.lower()}/{font_family.replace(' ', '')}-{weight}.ttf",
            # Windows
            f"C:/Windows/Fonts/{font_family.replace(' ', '')}.ttf",
        ]
        
        for path in system_font_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _render_text_as_image(self, text: str, font_family: str, font_size: int, 
                               color: Tuple[int, int, int], is_bold: bool = False,
                               width: Optional[int] = None, height: Optional[int] = None) -> Optional[np.ndarray]:
        """
        Render text as an image using PIL with the specified font.
        Returns a numpy array (RGBA) of the rendered text.
        
        Args:
            text: The text to render
            font_family: Google Font family name
            font_size: Font size in pixels
            color: RGB color tuple
            is_bold: Whether to use bold weight
            width: Optional width constraint
            height: Optional height constraint
            
        Returns:
            RGBA numpy array of rendered text, or None if rendering fails
        """
        try:
            # Get font file
            font_path = self._get_font_path(font_family, is_bold)
            
            if font_path and os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                except Exception as e:
                    self.logger.warning(f"Failed to load font from {font_path}: {e}")
                    font = ImageFont.load_default()
            else:
                self.logger.warning(f"Font not found: {font_family}, using default")
                font = ImageFont.load_default()
            
            # Create a temporary image to measure text size
            temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            
            # Get text bounding box
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Add some padding
            padding = 4
            img_width = text_width + padding * 2
            img_height = text_height + padding * 2
            
            # Use provided dimensions if given
            if width:
                img_width = max(img_width, width)
            if height:
                img_height = max(img_height, height)
            
            # Create final image with transparent background
            img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Calculate position to center text
            x = padding - bbox[0]  # Adjust for any negative offset
            y = padding - bbox[1]
            
            # Draw text
            draw.text((x, y), text, font=font, fill=(*color, 255))
            
            # Convert to numpy array
            return np.array(img)
            
        except Exception as e:
            self.logger.error(f"Error rendering text as image: {e}")
            return None
    
    def _pil_to_base64(self, pil_img: Image.Image) -> str:
        """Convert PIL Image to base64 encoded PNG"""
        buffer = io.BytesIO()
        pil_img.save(buffer, format='PNG')
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    def _add_text_as_image(self, layer, text_elem: TextElement, index: int = 0):
        """
        Add a text element as a rasterized image instead of SVG text.
        This ensures the font renders exactly as intended.
        """
        # Get font info - prefer classified_font over font_family
        font_family = text_elem.classified_font or text_elem.font_family or 'Roboto'
        font_size = text_elem.font_size or 16
        font_weight = text_elem.font_weight or 'normal'
        is_bold = font_weight.lower() in ['bold', '700', '800', '900']
        
        # Get color - parse hex string or use tuple
        if text_elem.color:
            if isinstance(text_elem.color, str) and text_elem.color.startswith('#'):
                # Convert hex to RGB tuple
                hex_color = text_elem.color.lstrip('#')
                color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            elif isinstance(text_elem.color, (list, tuple)) and len(text_elem.color) >= 3:
                color = tuple(text_elem.color[:3])
            else:
                color = (0, 0, 0)
        else:
            color = (0, 0, 0)
        
        # Render text as image
        text_img = self._render_text_as_image(
            text=text_elem.text,
            font_family=font_family,
            font_size=font_size,
            color=color,
            is_bold=is_bold
        )
        
        if text_img is not None:
            # Save rendered text image to debug folder if debug mode is enabled
            if DEBUG.get('save_intermediate_steps', False):
                debug_dir = DEBUG.get('output_dir', './debug_output')
                text_images_dir = os.path.join(debug_dir, 'rendered_text')
                os.makedirs(text_images_dir, exist_ok=True)
                
                # Sanitize text for filename
                safe_text = ''.join(c if c.isalnum() else '_' for c in text_elem.text[:30])
                debug_filename = f"text_{index:03d}_{safe_text}_{font_family.replace(' ', '_')}_{font_size}px.png"
                debug_path = os.path.join(text_images_dir, debug_filename)
                
                # Save the rendered text image
                pil_img_debug = Image.fromarray(text_img, 'RGBA')
                pil_img_debug.save(debug_path)
                self.logger.debug(f"Saved rendered text image: {debug_path}")
            
            # Convert RGBA numpy array to base64
            pil_img = Image.fromarray(text_img, 'RGBA')
            img_data = self._pil_to_base64(pil_img)
            
            # Get bbox - use w/h not width/height
            bbox = text_elem.bbox
            x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
            
            # Add image to SVG
            img_elem = layer.add(
                self.dwg.image(
                    href=f"data:image/png;base64,{img_data}",
                    insert=(x, y),
                    size=(text_img.shape[1], text_img.shape[0])  # Use actual rendered size
                )
            )
        else:
            # Fallback to regular SVG text
            self.logger.warning(f"Failed to render text as image, using SVG text: {text_elem.text[:30]}...")
            self._add_text_element_svg(layer, text_elem)
    
    def _add_text_element_svg(self, layer, text_elem: TextElement):
        """Fallback method to add text as SVG text element"""
        font_mapping = self._get_font_fallback_mapping()
        
        # Build font family with proper fallback chain
        if text_elem.classified_font:
            classified = text_elem.classified_font
            fallback = font_mapping.get(classified, font_mapping.get('default'))
            font_family = f"'{classified}', {fallback}"
        else:
            font_family = font_mapping.get('default')
        
        bbox = text_elem.bbox
        y_center = bbox.y + (bbox.h / 2.0)
        y_baseline = y_center + (text_elem.font_size * 0.35)
        x = float(bbox.x)
        
        text = self.dwg.text(text_elem.text,
                           insert=(x, y_baseline),
                           fill=text_elem.color,
                           font_family=font_family,
                           font_size=f'{int(text_elem.font_size)}px',
                           font_weight=text_elem.font_weight,
                           font_style=text_elem.font_style)
        
        layer.add(text)


def create_layered_svg(elements: Dict, output_path: str = 'output.svg') -> str:
    """
    Convenience function to create layered SVG from element dictionary
    
    Args:
        elements: Dictionary with keys: 'background', 'text', 'images', 'shapes', 'width', 'height'
        output_path: Output SVG file path
    
    Returns:
        Path to generated SVG
    """
    generator = SVGGenerator()
    
    return generator.generate_svg(
        width=elements.get('width', 800),
        height=elements.get('height', 600),
        background_image=elements.get('background'),
        text_elements=elements.get('text', []),
        image_elements=elements.get('images', []),
        shape_elements=elements.get('shapes', []),
        output_path=output_path
    )
