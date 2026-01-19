"""
SVG generation module
Steps 9, 10, 11: Convert elements to SVG and compose layers
Updated to support containers, logos, and proper layering
"""

import cv2
import svgwrite
from svgwrite import cm, mm
import numpy as np
from typing import List, Tuple, Dict, Any
import logging
import base64
import io
from PIL import Image

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
        
        # Add defs for any reusable elements (like rounded rect clips)
        defs = dwg.defs
        
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
        """Overlay text elements on debug image"""
        result = image.copy()
        for text_elem in text_elements:
            bbox = text_elem.bbox
            text = getattr(text_elem, 'text', '')
            color = getattr(text_elem, 'color', '#000000')
            
            # Convert hex color to BGR
            if color.startswith('#'):
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                bgr_color = (b, g, r)
            else:
                bgr_color = (0, 0, 0)
            
            # Draw text (simplified - actual font rendering would be more complex)
            font_size = getattr(text_elem, 'font_size', 12)
            scale = font_size / 30.0  # Approximate scaling
            
            # Draw text at bbox position
            cv2.putText(result, text[:50], (bbox.x, bbox.y + bbox.h - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, scale, bgr_color, 1, cv2.LINE_AA)
        
        return result
    
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
        """Add text elements to layer"""
        logger.info(f"Adding {len(texts)} text elements to layer...")
        
        for i, text_elem in enumerate(texts):
            bbox = text_elem.bbox
            
            # Position text at baseline (approximate)
            x = float(bbox.x)
            y = float(bbox.y + bbox.h * 0.8)  # Rough baseline estimation
            
            # Create text element
            text = dwg.text(text_elem.text,
                           insert=(x, y),
                           fill=text_elem.color,
                           font_family=text_elem.font_family,
                           font_size=f'{int(text_elem.font_size)}px',
                           font_weight=text_elem.font_weight,
                           font_style=text_elem.font_style,
                           id=f'text_{i}')
            
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
