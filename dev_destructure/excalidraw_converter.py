"""
Convert extracted image elements to Excalidraw JSON format
"""

import uuid
import time
import base64
import requests
from typing import Dict, List, Any, Optional
import random


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
        """Convert an image to Excalidraw image element"""
        bbox = self._get_value(image, 'bbox', [0, 0, 100, 100])
        s3_url = self._get_value(image, 's3_url', self._get_value(image, 'url'))
        
        if not s3_url:
            print("Warning: Image missing s3_url, skipping")
            return None
        
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
        
        # Download and encode image
        img_base64, mime_type = self._download_and_encode_image(s3_url)
        
        if not img_base64:
            print(f"Warning: Failed to encode image from {s3_url}, skipping")
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
        font_size = self._get_value(text_data, 'font_size', 16)
        color = self._get_value(text_data, 'color', '#1e1e1e')
        
        # Map font family (if provided)
        font_family_map = {
            'virgil': 1,
            'helvetica': 2,
            'cascadia': 3,
        }
        font_family_name = self._get_value(text_data, 'font_family', 'virgil')
        if isinstance(font_family_name, str):
            font_family_name = font_family_name.lower()
        font_family = font_family_map.get(font_family_name, 1)
        
        # Determine text alignment
        text_align = self._get_value(text_data, 'text_align', 'left')
        if text_align not in ['left', 'center', 'right']:
            text_align = 'left'
        
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
            extraction_data: The extraction data from RasterToSVGConverter
            statistics: Statistics from the extraction
            download_images: Whether to download images from S3 URLs (default: True)
        
        Returns:
            Complete Excalidraw JSON structure
        """
        elements = []
        files = {}
        self.index_counter = 0  # Reset counter
        
        print("Converting to Excalidraw format...")
        
        # Layer 1: Containers (background rectangles)
        containers = extraction_data.get('containers', [])
        print(f"  Processing {len(containers)} containers...")
        for container in containers:
            try:
                element = self._create_container_element(container)
                elements.append(element)
            except Exception as e:
                print(f"    Warning: Failed to convert container: {e}")
        
        # Layer 2: Shapes
        shapes = extraction_data.get('shapes', [])
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
            # Support both formats: 'images' or 'images_in_containers'+'standalone_images'
            images = extraction_data.get('images', [])
            if not images:
                # Use the split format from raster_to_svg
                images = extraction_data.get('images_in_containers', []) + extraction_data.get('standalone_images', [])
            
            logos = extraction_data.get('logos', [])
            all_images = images + logos
            
            print(f"  Processing {len(all_images)} images (downloading and encoding)...")
            for idx, image in enumerate(all_images, 1):
                try:
                    print(f"    [{idx}/{len(all_images)}] Downloading image...")
                    element = self._create_image_element(image, files)
                    if element:
                        elements.append(element)
                except Exception as e:
                    print(f"    Warning: Failed to convert image: {e}")
        else:
            print("  Skipping image download (download_images=False)")
        
        # Layer 4: Text elements (foreground)
        # Support both 'text_elements' and 'text' keys
        text_elements = extraction_data.get('text_elements', extraction_data.get('text', []))
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
