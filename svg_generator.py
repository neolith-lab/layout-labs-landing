"""
SVG generation module
Steps 9, 10, 11: Convert elements to SVG and compose layers
"""

import cv2
import svgwrite
from svgwrite import cm, mm
import numpy as np
from typing import List, Tuple, Dict
import logging
import base64
import io
from PIL import Image

from text_extractor import TextElement
from image_detector import ImageElement
from shape_detector import ShapeElement, ShapeType
from utils import rgb_to_hex
from config import SVG_OUTPUT

logger = logging.getLogger(__name__)


class SVGGenerator:
    """Generate SVG from detected elements"""
    
    def __init__(self, config: Dict = None):
        self.config = config or SVG_OUTPUT
    
    def generate_svg(self, width: int, height: int,
                    background_image: np.ndarray = None,
                    text_elements: List[TextElement] = None,
                    image_elements: List[ImageElement] = None,
                    shape_elements: List[ShapeElement] = None,
                    output_path: str = 'output.svg') -> str:
        """
        Generate complete SVG from all elements
        
        Args:
            width: SVG canvas width
            height: SVG canvas height
            background_image: Background image (optional)
            text_elements: Detected text elements
            image_elements: Detected image elements
            shape_elements: Detected shape elements
            output_path: Output SVG file path
        
        Returns:
            Path to generated SVG file
        """
        logger.info(f"Generating SVG: {output_path}")
        
        # Create SVG drawing
        dwg = svgwrite.Drawing(output_path, size=(width, height),
                              profile='full')
        
        # Add layers in order
        layer_order = self.config.get('layer_order', 
                                     ['background', 'shapes', 'images', 'text'])
        
        for layer_name in layer_order:
            # Create layer group
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
        
        # Save SVG
        dwg.save()
        logger.info(f"SVG generated successfully: {output_path}")
        
        return output_path
    
    def _add_background_layer(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                             background: np.ndarray, width: int, height: int):
        """Add background image as layer"""
        logger.info("Adding background layer...")
        
        # Convert background to base64
        background_data = self._numpy_to_base64(background)
        
        # Add as image element
        layer.add(dwg.image(href=f'data:image/png;base64,{background_data}',
                           insert=(0, 0),
                           size=(width, height)))
    
    def _add_shapes_layer(self, dwg: svgwrite.Drawing, layer: svgwrite.container.Group,
                         shapes: List[ShapeElement]):
        """Add shapes to layer"""
        logger.info(f"Adding {len(shapes)} shapes to layer...")
        
        for i, shape in enumerate(shapes):
            shape_id = f'shape_{i}'
            
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
            bbox = img_elem.bbox
            
            # Convert image to base64
            img_data = self._numpy_to_base64(img_elem.image_data)
            
            # Add image
            layer.add(dwg.image(href=f'data:image/png;base64,{img_data}',
                               insert=(int(bbox.x), int(bbox.y)),
                               size=(int(bbox.w), int(bbox.h)),
                               id=f'image_{i}'))
    
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
