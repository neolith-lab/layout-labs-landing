"""
SVG Output Generator
Creates layered SVG files from processed infographics
"""

import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import base64
import io

import numpy as np
from PIL import Image
import svgwrite

from .data_structures import (
    ProcessedInfographic, LayerElement, TextElement, BoundingBox
)
from .config import OutputConfig

logger = logging.getLogger(__name__)


class SVGGenerator:
    """
    Generate layered SVG files from processed infographics.
    
    Creates SVGs with:
    - Proper layer groups
    - Embedded or external images
    - Editable text elements
    - Vector shapes where possible
    """
    
    def __init__(self, config: OutputConfig = None):
        self.config = config or OutputConfig()
    
    def generate(self, infographic: ProcessedInfographic, 
                output_path: str) -> str:
        """
        Generate SVG file from processed infographic.
        
        Args:
            infographic: Processed infographic data
            output_path: Path for output SVG file
            
        Returns:
            Path to generated SVG
        """
        logger.info(f"Generating SVG: {output_path}")
        
        # Create SVG document
        dwg = svgwrite.Drawing(
            output_path, 
            size=(infographic.width, infographic.height),
            profile='full'
        )
        
        # Add defs for reusable elements (clips, filters, etc.)
        self._add_defs(dwg)
        
        # Add background layer
        if infographic.background is not None:
            self._add_background(dwg, infographic.background, 
                               infographic.width, infographic.height)
        
        # Add element layers (sorted by layer_index)
        sorted_layers = sorted(infographic.layers, key=lambda l: l.layer_index)
        
        for layer in sorted_layers:
            self._add_layer(dwg, layer)
        
        # Add text layer (on top)
        if infographic.text_elements:
            self._add_text_layer(dwg, infographic.text_elements)
        
        # Save
        dwg.save()
        logger.info(f"SVG saved: {output_path}")
        
        return output_path
    
    def _add_defs(self, dwg: svgwrite.Drawing):
        """Add reusable definitions to SVG"""
        # Add drop shadow filter using svgwrite.filters module
        from svgwrite.filters import Filter
        
        shadow_filter = dwg.defs.add(Filter(id='shadow'))
        shadow_filter.feGaussianBlur(in_='SourceAlpha', stdDeviation=3, result='blur')
        shadow_filter.feOffset(in_='blur', dx=2, dy=2, result='offsetBlur')
        
        # feMerge needs to be created using the attribs parameter
        # Since svgwrite doesn't have feMerge helper, we'll skip the complex filter
        # The shadow effect isn't critical for the output
        pass
    
    def _add_background(self, dwg: svgwrite.Drawing, 
                       background: np.ndarray,
                       width: int, height: int):
        """Add background image as base layer"""
        bg_group = dwg.g(id='layer_background')
        
        # Convert to base64
        img_data = self._numpy_to_base64(background)
        
        bg_group.add(dwg.image(
            href=f'data:image/png;base64,{img_data}',
            insert=(0, 0),
            size=(width, height)
        ))
        
        dwg.add(bg_group)
    
    def _add_layer(self, dwg: svgwrite.Drawing, layer: LayerElement):
        """Add a single layer element to SVG"""
        # Use class attribute instead of data- attributes for better compatibility
        layer_group = dwg.g(
            id=f'{self.config.layer_prefix}{layer.id}',
            class_=f'layer-{layer.category}'
        )
        
        bbox = layer.bbox
        
        # If we have SVG path data (vectorized), use that
        if layer.svg_path:
            path = dwg.path(d=layer.svg_path, id=layer.id)
            # Could add fill/stroke based on properties
            layer_group.add(path)
        
        # Otherwise embed as image
        elif layer.image_rgba is not None:
            img_data = self._numpy_to_base64(layer.image_rgba)
            
            layer_group.add(dwg.image(
                href=f'data:image/png;base64,{img_data}',
                insert=(int(bbox.x), int(bbox.y)),
                size=(int(bbox.width), int(bbox.height)),
                id=layer.id
            ))
        
        dwg.add(layer_group)
    
    def _add_text_layer(self, dwg: svgwrite.Drawing, 
                       text_elements: List[TextElement]):
        """Add text elements as editable SVG text"""
        text_group = dwg.g(id='layer_text')
        
        for i, te in enumerate(text_elements):
            bbox = te.bbox
            
            # Calculate baseline position (SVG text y is baseline, not top)
            baseline_y = bbox.y + bbox.height * 0.8
            
            text = dwg.text(
                te.text,
                insert=(bbox.x, baseline_y),
                id=f'text_{i}',
                fill=te.color,
                font_size=f'{te.font_size}px',
                font_weight=te.font_weight,
                font_style=te.font_style,
                font_family='sans-serif',  # Generic, will be overridden in editing tool
            )
            
            text_group.add(text)
        
        dwg.add(text_group)
    
    def _numpy_to_base64(self, image: np.ndarray) -> str:
        """Convert numpy array to base64 PNG"""
        # Handle RGBA
        if image.shape[2] == 4:
            mode = 'RGBA'
        else:
            mode = 'RGB'
            # Ensure RGB, not BGR
            if len(image.shape) == 3 and image.shape[2] == 3:
                # Check if it looks like BGR (OpenCV style) - heuristic
                pass  # Assume RGB for now
        
        pil_img = Image.fromarray(image, mode=mode)
        
        buffer = io.BytesIO()
        pil_img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.read()).decode('utf-8')


class FigmaExporter:
    """
    Export to Figma-compatible format.
    
    Options:
    1. Create SVG that Figma can import with layers
    2. Use Figma Plugin API (requires Figma plugin)
    3. Generate .fig file (reverse-engineered format - experimental)
    """
    
    def __init__(self):
        pass
    
    def export_for_figma(self, infographic: ProcessedInfographic,
                        output_path: str) -> str:
        """
        Export as Figma-friendly SVG.
        
        Figma-friendly SVG features:
        - Named groups become Figma layers/frames
        - Proper id attributes for element naming
        - Fonts as text (not paths) for editability
        """
        generator = SVGGenerator()
        
        # Generate with Figma-optimized settings
        return generator.generate(infographic, output_path)
    
    def create_figma_plugin_data(self, infographic: ProcessedInfographic) -> Dict:
        """
        Create JSON data for Figma plugin import.
        
        Can be used with a custom Figma plugin to recreate the design.
        """
        data = {
            'version': '1.0',
            'width': infographic.width,
            'height': infographic.height,
            'layers': [],
            'texts': []
        }
        
        for layer in sorted(infographic.layers, key=lambda l: l.layer_index):
            layer_data = {
                'id': layer.id,
                'name': f"{layer.category}_{layer.id}",
                'type': self._map_category_to_figma_type(layer.category),
                'x': layer.bbox.x,
                'y': layer.bbox.y,
                'width': layer.bbox.width,
                'height': layer.bbox.height,
                'category': layer.category,
            }
            
            # Include image data as base64
            if layer.image_rgba is not None:
                from PIL import Image
                pil_img = Image.fromarray(layer.image_rgba, 'RGBA')
                buffer = io.BytesIO()
                pil_img.save(buffer, format='PNG')
                buffer.seek(0)
                layer_data['imageData'] = base64.b64encode(buffer.read()).decode('utf-8')
            
            data['layers'].append(layer_data)
        
        for i, te in enumerate(infographic.text_elements):
            text_data = {
                'id': f'text_{i}',
                'content': te.text,
                'x': te.bbox.x,
                'y': te.bbox.y,
                'width': te.bbox.width,
                'height': te.bbox.height,
                'fontSize': te.font_size,
                'fontWeight': te.font_weight,
                'fontStyle': te.font_style,
                'color': te.color,
            }
            data['texts'].append(text_data)
        
        return data
    
    def _map_category_to_figma_type(self, category: str) -> str:
        """Map our categories to Figma node types"""
        mapping = {
            'photo': 'IMAGE',
            'illustration': 'IMAGE',
            'icon': 'IMAGE',  # Could be VECTOR if we vectorize
            'logo': 'IMAGE',
            'shape': 'RECTANGLE',  # Or VECTOR
            'container': 'FRAME',
            'chart': 'IMAGE',
            'text_heading': 'TEXT',
            'text_body': 'TEXT',
        }
        return mapping.get(category, 'IMAGE')


class PSDExporter:
    """
    Export to PSD format with layers.
    """
    
    def export(self, infographic: ProcessedInfographic, output_path: str) -> str:
        """
        Export as PSD with layers.
        
        Requires psd-tools or pytoshop.
        """
        try:
            from psd_tools import PSDImage
            from psd_tools.api.layers import PixelLayer
            logger.info("Using psd-tools for PSD export")
            return self._export_with_psd_tools(infographic, output_path)
        except ImportError:
            pass
        
        try:
            import pytoshop
            from pytoshop import layers
            logger.info("Using pytoshop for PSD export")
            return self._export_with_pytoshop(infographic, output_path)
        except ImportError:
            pass
        
        logger.error("No PSD library available. Install psd-tools or pytoshop.")
        raise ImportError("PSD export requires psd-tools or pytoshop")
    
    def _export_with_pytoshop(self, infographic: ProcessedInfographic, 
                             output_path: str) -> str:
        """Export using pytoshop library"""
        import pytoshop
        from pytoshop import layers
        from pytoshop.enums import ColorMode
        
        # Create PSD
        psd = pytoshop.core.PsdFile(
            num_channels=4,  # RGBA
            height=infographic.height,
            width=infographic.width,
            depth=8,
            color_mode=ColorMode.rgb
        )
        
        # Add background
        if infographic.background is not None:
            bg_rgba = self._ensure_rgba(infographic.background)
            bg_layer = layers.ChannelImageData(
                image=bg_rgba, 
                name='Background'
            )
            psd.layer_and_mask_info.layer_info.layer_records.append(bg_layer)
        
        # Add element layers
        for layer in sorted(infographic.layers, key=lambda l: l.layer_index):
            if layer.image_rgba is not None:
                layer_data = layers.ChannelImageData(
                    image=layer.image_rgba,
                    name=f'{layer.category}_{layer.id}',
                    top=layer.bbox.y,
                    left=layer.bbox.x
                )
                psd.layer_and_mask_info.layer_info.layer_records.append(layer_data)
        
        # Save
        with open(output_path, 'wb') as f:
            psd.write(f)
        
        logger.info(f"PSD saved: {output_path}")
        return output_path
    
    def _ensure_rgba(self, image: np.ndarray) -> np.ndarray:
        """Ensure image is RGBA"""
        if len(image.shape) == 2:
            # Grayscale to RGBA
            rgba = np.zeros((*image.shape, 4), dtype=np.uint8)
            rgba[:, :, :3] = image[:, :, np.newaxis]
            rgba[:, :, 3] = 255
            return rgba
        elif image.shape[2] == 3:
            # RGB to RGBA
            rgba = np.zeros((*image.shape[:2], 4), dtype=np.uint8)
            rgba[:, :, :3] = image
            rgba[:, :, 3] = 255
            return rgba
        return image
