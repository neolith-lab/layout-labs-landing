"""
Main Raster to SVG Converter - Updated with proper layering
Orchestrates the entire conversion pipeline with:
1. Logo detection (to exclude text in logos)
2. Container detection (rounded rectangles, cards)
3. Proper layer separation
"""

import cv2
import numpy as np
from typing import Dict, List, Optional
import logging
import os
from pathlib import Path

from text_extractor import TextExtractor, TextElement
from container_detector import ContainerDetector, ContainerElement
from image_detector import ImageDetector, ImageElement
from background_filler import BackgroundFiller
from svg_generator import SVGGenerator
from utils import BoundingBox, save_debug_image
from config import DEBUG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RasterToSVGConverter:
    """
    Complete pipeline for converting raster infographics to editable SVG
    
    Pipeline with text-first removal and infilling:
    
    Phase 1: Text Detection and Removal
        1.1 Detect all text (OCR)
        1.2 Remove text and infill using dominant border color
    
    Phase 2: Detection and Removal on Infilled Image
        2.1 Detect images/icons (on text-removed image)
        2.1.5 Remove images and infill
        2.2 Use filtered containers from image detection
        2.2.5 Clean container interiors (remove specs/artifacts)
        2.3 Remove containers and infill background
    
    Phase 3: SVG Generation
        Layer 1 (Bottom): Background
        Layer 2: Container shapes
        Layer 3: Images inside containers
        Layer 4: Standalone images
        Layer 5 (Top): Text
    """
    
    def __init__(self):
        logger.info("Initializing Raster to SVG Converter...")
        
        self.text_extractor = TextExtractor()
        self.image_detector = ImageDetector()
        self.container_detector = ContainerDetector()
        self.background_filler = BackgroundFiller()
        self.svg_generator = SVGGenerator()
        
        # Create debug output directory if needed
        if DEBUG.get('save_intermediate_steps', False):
            os.makedirs(DEBUG.get('output_dir', './debug_output'), exist_ok=True)
        
        logger.info("Converter initialized successfully")
    
    def convert(self, input_path: str, output_path: str = 'output.svg',
               convert_images_to_svg: bool = False) -> Dict:
        """
        Convert raster infographic to SVG with proper layering
        
        Args:
            input_path: Path to input raster image
            output_path: Path for output SVG file
            convert_images_to_svg: Whether to vectorize embedded images (experimental)
        
        Returns:
            Dictionary with conversion results and statistics
        """
        logger.info(f"Starting conversion: {input_path} -> {output_path}")
        
        # Load image
        image = cv2.imread(input_path)
        if image is None:
            raise ValueError(f"Failed to load image: {input_path}")
        
        height, width = image.shape[:2]
        logger.info(f"Image dimensions: {width}x{height}")
        
        # Keep original for reference
        original_image = image.copy()
        
        # ============================================================
        # PHASE 1: TEXT DETECTION AND REMOVAL (FIRST)
        # ============================================================
        
        # Step 1.1: Detect all text (OCR)
        logger.info("=" * 50)
        logger.info("PHASE 1.1: Text Detection")
        logger.info("=" * 50)
        
        text_elements = self.text_extractor.extract_text_elements(original_image)
        text_bboxes = [elem.bbox for elem in text_elements]
        
        logger.info(f"Text elements detected: {len(text_elements)}")
        
        # Print detailed text summary with font information
        self._print_text_summary(text_elements)
        
        # ============================================================
        # PHASE 1.4: TEXT REMOVAL AND INFILLING
        # ============================================================
        logger.info("=" * 50)
        logger.info("PHASE 1.4: Text Removal and Infilling")
        logger.info("=" * 50)
        
        # Remove text and fill with average border color
        # This creates a clean image for subsequent detection steps
        text_removed_image = self.background_filler.fill_with_border_average(
            original_image, text_bboxes, border_width=5
        )
        
        logger.info(f"Removed and infilled {len(text_bboxes)} text regions")
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(text_removed_image, '01_text_removed_infilled.png',
                           DEBUG.get('output_dir', './debug_output'))
        
        # ============================================================
        # PHASE 2: DETECTION ON INFILLED IMAGE
        # ============================================================
        
        # Step 2.1: Detect images/photos on the text-removed image
        logger.info("=" * 50)
        logger.info("PHASE 2.1: Image Detection (on infilled image)")
        logger.info("=" * 50)
        
        # Detect all images, returns (kept_images, filtered_container_like_images)
        image_elements, filtered_containers = self.image_detector.detect_images(
            text_removed_image, 
            text_bboxes=[]  # Text already removed, no need to exclude
        )
        image_bboxes = [elem.bbox for elem in image_elements]
        
        logger.info(f"Kept {len(image_elements)} images, filtered {len(filtered_containers)} container-like detections")
        
        # Step 2.1.5: Remove detected images using border color fill
        logger.info("=" * 50)
        logger.info("PHASE 2.1.5: Image Removal and Infilling")
        logger.info("=" * 50)
        
        # Remove images (but NOT the filtered containers) and fill with dominant border color
        # Uses the same technique as text removal for consistency
        images_removed_image = self.background_filler.fill_with_border_average(
            text_removed_image, image_bboxes, border_width=5
        )
        
        logger.info(f"Removed and infilled {len(image_bboxes)} image regions")
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(images_removed_image, '04_images_removed_infilled.png',
                           DEBUG.get('output_dir', './debug_output'))
        
        # Step 2.2: Use filtered containers from image detection
        logger.info("=" * 50)
        logger.info("PHASE 2.2: Container Processing (from image detection)")
        logger.info("=" * 50)
        
        # Convert filtered ImageElements to ContainerElements
        # The filtered_containers are already detected during image detection
        from container_detector import ContainerElement, ContainerType
        
        containers = []
        for img_elem in filtered_containers:
            # Create a simple contour from the bounding box
            bbox = img_elem.bbox
            contour = np.array([
                [bbox.x, bbox.y],
                [bbox.x2, bbox.y],
                [bbox.x2, bbox.y2],
                [bbox.x, bbox.y2]
            ], dtype=np.int32)
            
            # Create ContainerElement from ImageElement
            container = ContainerElement(
                container_type=ContainerType.RECTANGLE,
                bbox=bbox,
                contour=contour,
                fill_color="#FFFFFF",  # Default white fill
                stroke_color="#000000",  # Default black stroke
                stroke_width=1,
                corner_radius=0  # Will be estimated later if needed
            )
            containers.append(container)
        
        container_bboxes = [c.bbox for c in containers]
        logger.info(f"Using {len(containers)} containers from image detection filter")
        
        # Save debug visualization showing containers on the images-removed image
        if DEBUG.get('save_intermediate_steps', False):
            logger.info(f"Creating debug visualization for {len(containers)} containers...")
            debug_img = images_removed_image.copy()
            
            # Add summary text at top
            summary = f"Containers detected: {len(containers)} (GREEN boxes)"
            cv2.putText(debug_img, summary, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 3)
            cv2.putText(debug_img, summary, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
            
            # Draw container bounding boxes in GREEN
            for i, container in enumerate(containers):
                bbox = container.bbox
                color = (0, 255, 0)  # GREEN in BGR
                
                # Draw bounding box
                cv2.rectangle(debug_img, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 2)
                
                # Add label
                label = f"Container {i+1}: {bbox.w}x{bbox.h}"
                cv2.rectangle(debug_img, (bbox.x, bbox.y - 25), (bbox.x + 200, bbox.y), color, -1)
                cv2.putText(debug_img, label, (bbox.x + 2, bbox.y - 8),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
            logger.info("Saving container detection debug image...")
            save_debug_image(debug_img, '04b_containers_detected.png',
                           DEBUG.get('output_dir', './debug_output'))
            logger.info("Container detection debug image saved")
        else:
            logger.info("Debug saving is disabled - set DEBUG['save_intermediate_steps'] = True to enable")
        
        # Step 2.2.5: Clean container interiors - remove specs and thin artifacts
        logger.info("=" * 50)
        logger.info("PHASE 2.2.5: Container Interior Cleaning")
        logger.info("=" * 50)
        
        # Clean small specs and thin artifacts left behind after image/text removal
        cleaned_image = self.background_filler.clean_container_interiors(
            images_removed_image, container_bboxes,
            min_artifact_size=100,  # Remove artifacts smaller than 100 pixels
            thin_threshold=5        # Remove artifacts thinner than 5 pixels
        )
        
        logger.info(f"Cleaned interiors of {len(container_bboxes)} containers")
        
        # Separate images into those inside containers and outside
        images_in_containers, images_outside = self.container_detector.get_images_in_containers(
            containers, image_elements
        )
        
        logger.info(f"Images in containers: {len(images_in_containers)}")
        logger.info(f"Standalone images: {len(images_outside)}")
        
        # Step 2.3: Remove containers and infill background
        logger.info("=" * 50)
        logger.info("PHASE 2.3: Container Removal and Background Infilling")
        logger.info("=" * 50)
        
        # Remove containers and fill with dominant border color
        # Uses the same technique as text and image removal
        background_image = self.background_filler.fill_with_border_average(
            cleaned_image, container_bboxes, border_width=5
        )
        
        logger.info(f"Removed and infilled {len(container_bboxes)} container regions")
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(background_image, '05_containers_removed_background.png',
                           DEBUG.get('output_dir', './debug_output'))

        
        # ============================================================
        # PHASE 4: SVG GENERATION WITH PROPER LAYERS
        # ============================================================
        logger.info("=" * 50)
        logger.info("PHASE 4: SVG Generation with Layers")
        logger.info("=" * 50)
        
        # Store image data for elements before generating SVG
        # Extract from original image at their bbox positions
        for elem in images_in_containers + images_outside:
            elem.image_data = original_image[
                elem.bbox.y:elem.bbox.y2, 
                elem.bbox.x:elem.bbox.x2
            ].copy()
        
        # Store container image data from CLEANED image (after text/images removed from inside)
        # This gives us containers with clean interiors
        for container in containers:
            bbox = container.bbox
            container.image_data = cleaned_image[
                bbox.y:bbox.y2,
                bbox.x:bbox.x2
            ].copy()
        
        # Generate SVG with proper layers (no shapes)
        output_svg_path = self.svg_generator.generate_layered_svg(
            width=width,
            height=height,
            background_image=background_image,
            containers=containers,
            images_in_containers=images_in_containers,
            standalone_images=images_outside,
            logos=[],
            shapes=[],  # No shape detection
            text_elements=text_elements,
            output_path=output_path,
            original_image=original_image  # Pass original for debug overlays
        )
        
        # ============================================================
        # COMPILE RESULTS
        # ============================================================
        results = {
            'success': True,
            'output_path': output_svg_path,
            'statistics': {
                'text_elements': len(text_elements),
                'logos': 0,
                'containers': len(containers),
                'images_in_containers': len(images_in_containers),
                'standalone_images': len(images_outside),
                'shapes': 0,  # No shape detection
                'dimensions': (width, height)
            },
            'elements': {
                'text': text_elements,
                'logos': [],
                'containers': containers,
                'images_in_containers': images_in_containers,
                'standalone_images': images_outside,
                'shapes': [],  # No shape detection
                'background': background_image
            }
        }
        
        logger.info("=" * 50)
        logger.info("CONVERSION COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Text elements: {len(text_elements)}")
        logger.info(f"Containers: {len(containers)}")
        logger.info(f"Images in containers: {len(images_in_containers)}")
        logger.info(f"Standalone images: {len(images_outside)}")
        logger.info(f"Output saved to: {output_svg_path}")
        
        return results
    
    def _print_text_summary(self, text_elements: List[TextElement]):
        """Print summary of detected text with font information"""
        if not text_elements:
            logger.info("No text elements detected")
            return
        
        logger.info(f"\n{'='*100}")
        logger.info(f"Text Detection Summary - {len(text_elements)} elements")
        logger.info(f"{'='*100}")
        logger.info(f"{'Text':<40} {'Font':<30} {'Size':<8} {'Lines':<8} {'Confidence':<12}")
        logger.info(f"{'='*100}")
        
        for element in text_elements:
            text_preview = element.text.replace('\n', ' ')[:40]
            
            # Build font display
            if element.classified_font:
                font_display = f"{element.classified_font}"
                if element.classified_font_version:
                    font_display += f" ({element.classified_font_version})"
                confidence_str = f"{element.font_classification_confidence:.3f}"
            else:
                font_display = f"{element.font_family} (fallback)"
                confidence_str = f"{element.confidence:.3f}"
            
            logger.info(f"{text_preview:<40} {font_display:<30} {element.font_size}pt    {element.num_lines}        {confidence_str:<12}")
        
        logger.info(f"{'='*100}\n")
    
    def _bboxes_match(self, bbox1: BoundingBox, bbox2: BoundingBox, tolerance: int = 5) -> bool:
        """Check if two bounding boxes are essentially the same"""
        return (
            abs(bbox1.x - bbox2.x) <= tolerance and
            abs(bbox1.y - bbox2.y) <= tolerance and
            abs(bbox1.w - bbox2.w) <= tolerance and
            abs(bbox1.h - bbox2.h) <= tolerance
        )
    
    def convert_batch(self, input_dir: str, output_dir: str,
                     pattern: str = '*.png') -> Dict:
        """
        Convert multiple images in batch
        """
        logger.info(f"Starting batch conversion from {input_dir}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        input_path = Path(input_dir)
        files = list(input_path.glob(pattern))
        
        logger.info(f"Found {len(files)} files to convert")
        
        results = {
            'total': len(files),
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for i, file_path in enumerate(files, 1):
            logger.info(f"Processing {i}/{len(files)}: {file_path.name}")
            
            output_name = file_path.stem + '.svg'
            output_path = os.path.join(output_dir, output_name)
            
            try:
                result = self.convert(str(file_path), output_path)
                results['successful'] += 1
                results['details'].append({
                    'file': file_path.name,
                    'status': 'success',
                    'output': output_path,
                    'statistics': result['statistics']
                })
            except Exception as e:
                logger.error(f"Failed to convert {file_path.name}: {e}")
                results['failed'] += 1
                results['details'].append({
                    'file': file_path.name,
                    'status': 'failed',
                    'error': str(e)
                })
        
        logger.info(f"Batch conversion complete: {results['successful']}/{len(files)} successful")
        
        return results


def main():
    """Main entry point for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert raster infographics to editable SVG'
    )
    parser.add_argument('input', help='Input image file or directory')
    parser.add_argument('-o', '--output', help='Output SVG file or directory')
    parser.add_argument('-b', '--batch', action='store_true',
                       help='Batch mode for directory processing')
    parser.add_argument('--pattern', default='*.png',
                       help='File pattern for batch mode (default: *.png)')
    parser.add_argument('--convert-images', action='store_true',
                       help='Convert embedded images to SVG (experimental)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    converter = RasterToSVGConverter()
    
    if args.batch:
        output_dir = args.output or 'output_svg'
        results = converter.convert_batch(args.input, output_dir, args.pattern)
        print(f"\nBatch conversion results:")
        print(f"Total: {results['total']}")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
    else:
        output_path = args.output or 'output.svg'
        results = converter.convert(args.input, output_path,
                                   convert_images_to_svg=args.convert_images)
        print(f"\nConversion successful!")
        print(f"Output: {results['output_path']}")
        print(f"Statistics: {results['statistics']}")


if __name__ == '__main__':
    main()
