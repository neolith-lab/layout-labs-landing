"""
Main ML Pipeline for Infographic Layerization

Orchestrates SAM segmentation, CLIP classification, LaMa inpainting,
and output generation.
"""

import logging
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import numpy as np
import cv2
from PIL import Image

from .config import PipelineConfig, get_default_config
from .data_structures import (
    SegmentedElement, ClassifiedElement, LayerElement, 
    TextElement, ProcessedInfographic, BoundingBox, calculate_iou
)
from .segmentation import SAMSegmenter, filter_overlapping_segments
from .classification import CLIPClassifier, reclassify_by_context
from .inpainting import LamaInpainter, create_inpaint_mask_from_elements
from .ocr import TextExtractor, group_text_by_paragraph, classify_text_hierarchy
from .output import SVGGenerator, FigmaExporter, PSDExporter

logger = logging.getLogger(__name__)


class InfographicLayerizer:
    """
    Main pipeline for converting raster infographics to layered formats.
    
    Pipeline stages:
    1. Segmentation (SAM) - Find all distinct visual elements
    2. Classification (CLIP) - Categorize elements (logo, icon, text, etc.)
    3. Layer Ordering - Determine z-order of elements
    4. Text Extraction (PaddleOCR) - Extract editable text
    5. Background Reconstruction (LaMa) - Generate clean background
    6. Output Generation - Create layered SVG/PSD
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or get_default_config()
        
        # Initialize components (lazy loading)
        self.segmenter = SAMSegmenter(self.config.sam)
        self.classifier = CLIPClassifier(self.config.clip)
        self.inpainter = LamaInpainter(self.config.lama)
        self.text_extractor = TextExtractor(self.config.ocr)
        
        # Output generators
        self.svg_generator = SVGGenerator(self.config.output)
        
        logger.info("InfographicLayerizer initialized")
    
    def process(self, image_path: str, 
               output_path: str = None,
               output_format: str = 'svg') -> ProcessedInfographic:
        """
        Process an infographic image into layered format.
        
        Args:
            image_path: Path to input image
            output_path: Path for output file (optional)
            output_format: Output format ('svg', 'psd', 'json')
            
        Returns:
            ProcessedInfographic with all layers and metadata
        """
        start_time = time.time()
        
        logger.info(f"Processing: {image_path}")
        
        # Load image
        image = self._load_image(image_path)
        h, w = image.shape[:2]
        
        logger.info(f"Image size: {w}x{h}")
        
        # Save input image for debugging
        logger.info(f"DEBUG: save_debug = {self.config.output.save_debug}")
        if self.config.output.save_debug:
            try:
                debug_dir = Path('./debug_output')
                debug_dir.mkdir(exist_ok=True)
                input_path = str(debug_dir / '00_input.png')
                cv2.imwrite(input_path, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                logger.info(f"Saved input image to {input_path}")
            except Exception as e:
                logger.error(f"Failed to save input image: {e}", exc_info=True)
        
        # ========================================
        # Stage 1: Segmentation
        # ========================================
        logger.info("=" * 50)
        logger.info("STAGE 1: Segmentation (SAM)")
        logger.info("=" * 50)
        
        segments = self.segmenter.segment(image)
        
        # Filter overlapping segments
        segments = filter_overlapping_segments(
            segments, 
            iou_threshold=self.config.merge_overlap_threshold
        )
        
        # Filter small segments
        segments = [
            s for s in segments 
            if s.bbox.width >= self.config.min_element_size 
            and s.bbox.height >= self.config.min_element_size
        ]
        
        logger.info(f"Retained {len(segments)} segments after filtering")
        
        # Save debug visualization
        if self.config.output.save_debug:
            self._save_stage_debug(image, segments, "01_segmentation")
        
        # ========================================
        # Stage 2: Classification
        # ========================================
        logger.info("=" * 50)
        logger.info("STAGE 2: Classification (CLIP)")
        logger.info("=" * 50)
        
        classified = self.classifier.classify(segments, image)
        
        # Refine with context
        classified = reclassify_by_context(classified, image)
        
        # Save debug visualization
        if self.config.output.save_debug:
            self._save_stage_debug(image, classified, "02_classification")
        
        # ========================================
        # Stage 3: Layer Ordering
        # ========================================
        logger.info("=" * 50)
        logger.info("STAGE 3: Layer Ordering")
        logger.info("=" * 50)
        
        ordered_elements = self._determine_layer_order(classified)
        
        # Save debug visualization
        if self.config.output.save_debug:
            self._save_stage_debug(image, ordered_elements, "03_layer_ordering")
        
        # ========================================
        # Stage 4: Text Extraction
        # ========================================
        logger.info("=" * 50)
        logger.info("STAGE 4: Text Extraction (OCR)")
        logger.info("=" * 50)
        
        text_elements = self.text_extractor.extract(image)
        text_elements = classify_text_hierarchy(text_elements)
        
        # Associate text with parent elements
        text_elements = self._associate_text_with_elements(
            text_elements, ordered_elements
        )
        
        logger.info(f"Extracted {len(text_elements)} text elements")
        
        # Save debug visualization
        if self.config.output.save_debug:
            self._save_ocr_debug(image, text_elements, "04_ocr")
        
        # ========================================
        # Stage 5: Background Reconstruction
        # ========================================
        logger.info("=" * 50)
        logger.info("STAGE 5: Background Reconstruction (LaMa)")
        logger.info("=" * 50)
        
        background = self.inpainter.reconstruct_background(
            image, 
            ordered_elements,
            exclude_categories=['background']
        )
        
        # Save debug visualization
        if self.config.output.save_debug:
            self._save_background_debug(background, "05_inpainting")
        
        # ========================================
        # Stage 6: Create Final Layers
        # ========================================
        logger.info("=" * 50)
        logger.info("STAGE 6: Creating Final Layers")
        logger.info("=" * 50)
        
        layers = self._create_final_layers(ordered_elements, image)
        
        # Save debug visualization
        if self.config.output.save_debug:
            self._save_layers_debug(layers, image, "06_final_layers")
        
        # ========================================
        # Build Result
        # ========================================
        result = ProcessedInfographic(
            original_path=image_path,
            width=w,
            height=h,
            layers=layers,
            background=background,
            text_elements=text_elements,
            processing_time=time.time() - start_time,
            model_versions={
                'sam': self.config.sam.model_type,
                'clip': self.config.clip.model_name,
            }
        )
        
        # ========================================
        # Stage 7: Output Generation
        # ========================================
        if output_path:
            logger.info("=" * 50)
            logger.info("STAGE 7: Output Generation")
            logger.info("=" * 50)
            
            self._generate_output(result, output_path, output_format)
        
        # ========================================
        # Debug Output
        # ========================================
        if self.config.output.save_debug:
            self._save_debug_outputs(image, result)
        
        logger.info("=" * 50)
        logger.info("PROCESSING COMPLETE")
        logger.info(f"Total time: {result.processing_time:.2f}s")
        logger.info(f"Layers: {len(result.layers)}")
        logger.info(f"Text elements: {len(result.text_elements)}")
        logger.info("=" * 50)
        
        return result
    
    def _load_image(self, path: str) -> np.ndarray:
        """Load image and convert to RGB"""
        image = cv2.imread(path)
        if image is None:
            raise ValueError(f"Could not load image: {path}")
        
        # Convert BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Resize if needed
        h, w = image.shape[:2]
        max_size = self.config.max_image_size
        
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.info(f"Resized image from {w}x{h} to {new_w}x{new_h}")
        
        return image
    
    def _determine_layer_order(self, elements: List[ClassifiedElement]) -> List[ClassifiedElement]:
        """
        Determine z-order of elements.
        
        Uses:
        1. Category-based ordering (containers below icons, text on top)
        2. Containment relationships (parent below child)
        3. Area heuristics (larger elements typically behind)
        """
        # Get layer order from config
        layer_order = self.config.layer_order
        
        # Create priority map
        priority_map = {cat: i for i, cat in enumerate(layer_order)}
        default_priority = len(layer_order) // 2
        
        # Sort by category priority, then by area (larger first = behind)
        def sort_key(elem):
            category_priority = priority_map.get(elem.category, default_priority)
            # Negative area so larger elements come first (lower layer index)
            return (category_priority, -elem.area)
        
        sorted_elements = sorted(elements, key=sort_key)
        
        # Adjust for containment (if element A contains element B, A should be below B)
        sorted_elements = self._adjust_for_containment(sorted_elements)
        
        logger.info(f"Layer order determined for {len(sorted_elements)} elements")
        
        return sorted_elements
    
    def _adjust_for_containment(self, elements: List[ClassifiedElement]) -> List[ClassifiedElement]:
        """Adjust layer order based on containment relationships"""
        # Check each pair for containment
        n = len(elements)
        
        for i in range(n):
            for j in range(i + 1, n):
                elem_i = elements[i]
                elem_j = elements[j]
                
                # Check if j is contained in i
                iou = calculate_iou(elem_i.mask, elem_j.mask)
                if iou > 0:
                    # Check containment direction
                    i_in_j = np.logical_and(elem_i.mask, elem_j.mask).sum() / elem_i.area
                    j_in_i = np.logical_and(elem_i.mask, elem_j.mask).sum() / elem_j.area
                    
                    # If j is mostly in i, i should be below j
                    if j_in_i > 0.8 and j_in_i > i_in_j:
                        # i should stay below j (already in order)
                        pass
                    elif i_in_j > 0.8 and i_in_j > j_in_i:
                        # j should be below i - swap
                        elements[i], elements[j] = elements[j], elements[i]
        
        return elements
    
    def _associate_text_with_elements(self, text_elements: List[TextElement],
                                     classified_elements: List[ClassifiedElement]) -> List[TextElement]:
        """Associate text elements with their parent elements"""
        for text in text_elements:
            text_center = text.bbox.center
            
            # Find which element contains this text
            for elem in classified_elements:
                if elem.mask[text_center[1], text_center[0]]:
                    text.parent_element_id = elem.id
                    break
        
        return text_elements
    
    def _create_final_layers(self, elements: List[ClassifiedElement],
                            image: np.ndarray) -> List[LayerElement]:
        """Convert classified elements to final layer elements"""
        layers = []
        
        for i, elem in enumerate(elements):
            # Extract RGBA image for this element
            rgba = self._extract_element_rgba(image, elem)
            
            layer = LayerElement(
                id=elem.id,
                category=elem.category,
                layer_index=i,
                bbox=elem.bbox,
                mask=elem.mask,
                image_rgba=rgba,
                confidence=elem.category_confidence,
                properties={
                    'stability_score': elem.stability_score,
                    'contains_text': elem.contains_text,
                    'is_complex': elem.is_complex,
                    'all_scores': elem.all_scores,
                }
            )
            
            layers.append(layer)
        
        return layers
    
    def _extract_element_rgba(self, image: np.ndarray, 
                             element: ClassifiedElement) -> np.ndarray:
        """Extract element as RGBA with mask as alpha"""
        if element.image_rgba is not None:
            return element.image_rgba
        
        bbox = element.bbox
        
        # Crop image and mask
        cropped = image[bbox.y:bbox.y2, bbox.x:bbox.x2].copy()
        cropped_mask = element.mask[bbox.y:bbox.y2, bbox.x:bbox.x2]
        
        # Create RGBA
        rgba = np.zeros((*cropped.shape[:2], 4), dtype=np.uint8)
        rgba[:, :, :3] = cropped
        rgba[:, :, 3] = (cropped_mask * 255).astype(np.uint8)
        
        return rgba
    
    def _generate_output(self, result: ProcessedInfographic, 
                        output_path: str, output_format: str):
        """Generate output file(s)"""
        output_format = output_format.lower()
        
        if output_format == 'svg':
            self.svg_generator.generate(result, output_path)
        
        elif output_format == 'psd':
            exporter = PSDExporter()
            exporter.export(result, output_path)
        
        elif output_format == 'figma':
            exporter = FigmaExporter()
            exporter.export_for_figma(result, output_path)
        
        elif output_format == 'json':
            import json
            exporter = FigmaExporter()
            data = exporter.create_figma_plugin_data(result)
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
        
        else:
            logger.warning(f"Unknown format: {output_format}, defaulting to SVG")
            self.svg_generator.generate(result, output_path)
    
    def _save_debug_outputs(self, image: np.ndarray, result: ProcessedInfographic):
        """Save debug visualizations"""
        debug_dir = Path(self.config.output.debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Segmentation visualization
        seg_vis = image.copy()
        colors = np.random.randint(0, 255, (len(result.layers), 3))
        
        for i, layer in enumerate(result.layers):
            mask = layer.mask
            color = colors[i]
            seg_vis[mask] = seg_vis[mask] * 0.5 + color * 0.5
        
        cv2.imwrite(str(debug_dir / '01_segmentation.png'), 
                   cv2.cvtColor(seg_vis.astype(np.uint8), cv2.COLOR_RGB2BGR))
        
        # 2. Classification visualization
        class_vis = image.copy()
        
        category_colors = {
            'logo': (255, 165, 0),
            'icon': (0, 255, 0),
            'photo': (0, 0, 255),
            'illustration': (255, 0, 255),
            'text_heading': (255, 255, 0),
            'text_body': (255, 255, 128),
            'shape': (128, 128, 128),
            'container': (0, 255, 255),
            'chart': (128, 0, 128),
        }
        
        for layer in result.layers:
            color = category_colors.get(layer.category, (200, 200, 200))
            bbox = layer.bbox
            cv2.rectangle(class_vis, 
                         (bbox.x, bbox.y), (bbox.x2, bbox.y2),
                         color, 2)
            cv2.putText(class_vis, layer.category,
                       (bbox.x, bbox.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        cv2.imwrite(str(debug_dir / '02_classification.png'),
                   cv2.cvtColor(class_vis, cv2.COLOR_RGB2BGR))
        
        # 3. Background
        if result.background is not None:
            cv2.imwrite(str(debug_dir / '03_background.png'),
                       cv2.cvtColor(result.background, cv2.COLOR_RGB2BGR))
        
        # 4. Text detection
        text_vis = image.copy()
        for te in result.text_elements:
            bbox = te.bbox
            cv2.rectangle(text_vis,
                         (bbox.x, bbox.y), (bbox.x2, bbox.y2),
                         (0, 255, 0), 1)
        
        cv2.imwrite(str(debug_dir / '04_text.png'),
                   cv2.cvtColor(text_vis, cv2.COLOR_RGB2BGR))
        
        logger.info(f"Debug outputs saved to {debug_dir}")
    
    def _save_stage_debug(self, image: np.ndarray, elements: List, stage_name: str):
        """Save debug visualization for segmentation/classification/ordering stages"""
        try:
            debug_dir = Path('./debug_output')
            debug_dir.mkdir(exist_ok=True)
            
            logger.info(f"Saving debug for {stage_name} with {len(elements)} elements")
            
            vis = image.copy()
            
            # Generate random colors for each element
            np.random.seed(42)
            colors = np.random.randint(50, 255, size=(len(elements), 3))
            
            category_colors = {
                'logo': (255, 165, 0),
                'icon': (0, 255, 0),
                'photo': (0, 0, 255),
                'illustration': (255, 0, 255),
                'text_heading': (255, 255, 0),
                'text_body': (255, 255, 128),
                'button': (255, 100, 100),
                'shape': (128, 128, 128),
                'container': (0, 255, 255),
                'chart': (128, 0, 128),
                'screenshot': (200, 100, 50),
                'connector': (100, 200, 100),
            }
            
            for i, elem in enumerate(elements):
                # Get color based on category if available
                if hasattr(elem, 'category'):
                    color = category_colors.get(elem.category, tuple(map(int, colors[i])))
                    conf = getattr(elem, 'confidence', getattr(elem, 'category_confidence', 0))
                    label = f"{elem.category} ({conf:.2f})"
                else:
                    color = tuple(map(int, colors[i]))
                    label = f"seg_{i}"
                
                # Ensure color is tuple of ints for OpenCV
                color = tuple(int(c) for c in color)
                
                # Draw bounding box
                bbox = elem.bbox
                cv2.rectangle(vis, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 2)
                
                # Draw label
                cv2.putText(vis, label, (bbox.x, bbox.y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                
                # Draw mask overlay if available
                if hasattr(elem, 'mask') and elem.mask is not None:
                    try:
                        mask_overlay = vis.copy()
                        mask_overlay[elem.mask] = color
                        vis = cv2.addWeighted(vis, 0.7, mask_overlay, 0.3, 0)
                    except Exception as mask_err:
                        logger.debug(f"Could not draw mask overlay: {mask_err}")
            
            output_path = debug_dir / f"{stage_name}.png"
            cv2.imwrite(str(output_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
            logger.info(f"Saved debug visualization: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save debug for {stage_name}: {e}", exc_info=True)
    
    def _save_ocr_debug(self, image: np.ndarray, text_elements: List[TextElement], stage_name: str):
        """Save debug visualization for OCR stage"""
        try:
            debug_dir = Path('./debug_output')
            debug_dir.mkdir(exist_ok=True)
            
            logger.info(f"Saving OCR debug for {stage_name} with {len(text_elements)} text elements")
            
            vis = image.copy()
            
            for te in text_elements:
                bbox = te.bbox
                # Draw green boxes for text
                cv2.rectangle(vis, (bbox.x, bbox.y), (bbox.x2, bbox.y2), (0, 255, 0), 2)
                # Draw text content
                text_preview = te.text[:20] if te.text else ""
                cv2.putText(vis, text_preview, (bbox.x, bbox.y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            output_path = debug_dir / f"{stage_name}.png"
            cv2.imwrite(str(output_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
            logger.info(f"Saved OCR debug visualization: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save OCR debug for {stage_name}: {e}", exc_info=True)
    
    def _save_background_debug(self, background: np.ndarray, stage_name: str):
        """Save debug visualization for inpainting stage"""
        try:
            debug_dir = Path('./debug_output')
            debug_dir.mkdir(exist_ok=True)
            
            logger.info(f"Saving background debug for {stage_name}")
            
            output_path = debug_dir / f"{stage_name}.png"
            cv2.imwrite(str(output_path), cv2.cvtColor(background, cv2.COLOR_RGB2BGR))
            logger.info(f"Saved inpainting debug visualization: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save background debug for {stage_name}: {e}", exc_info=True)
    
    def _save_layers_debug(self, layers: List[LayerElement], image: np.ndarray, stage_name: str):
        """Save debug visualization for final layers"""
        try:
            debug_dir = Path('./debug_output')
            debug_dir.mkdir(exist_ok=True)
            
            logger.info(f"Saving layers debug for {stage_name} with {len(layers)} layers")
            
            # Create composite visualization
            vis = np.zeros_like(image)
            
            # Draw layers in order
            for layer in sorted(layers, key=lambda l: l.layer_index):
                if layer.mask is not None:
                    vis[layer.mask] = image[layer.mask]
            
            output_path = debug_dir / f"{stage_name}.png"
            cv2.imwrite(str(output_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
            logger.info(f"Saved layers debug visualization: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save layers debug for {stage_name}: {e}", exc_info=True)

def process_infographic(image_path: str, 
                       output_path: str = None,
                       output_format: str = 'svg',
                       config: PipelineConfig = None) -> ProcessedInfographic:
    """
    Convenience function to process an infographic.
    
    Args:
        image_path: Path to input image
        output_path: Path for output (optional)
        output_format: 'svg', 'psd', 'figma', or 'json'
        config: Pipeline configuration (optional)
        
    Returns:
        ProcessedInfographic with all layers
    """
    pipeline = InfographicLayerizer(config)
    return pipeline.process(image_path, output_path, output_format)
