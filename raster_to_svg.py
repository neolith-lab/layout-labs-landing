"""
Main Raster to SVG Converter
Orchestrates the entire conversion pipeline
"""

import cv2
import numpy as np
from typing import Dict, Optional
import logging
import os
from pathlib import Path

from text_extractor import TextExtractor
from image_detector import ImageDetector
from shape_detector import ShapeDetector
from background_filler import BackgroundFiller
from svg_generator import SVGGenerator, create_layered_svg
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
    
    Pipeline Steps:
    1. Text OCR with font identification
    2. Bounding box removal & background filling
    3. Image bounding box detection
    4. Image removal and background filling
    5. Optional conversion of images to SVG
    6. Shape identification & bounding boxes
    7. Shape removal & background filling
    8. Reconstruction of shapes
    9. Background to SVG
    10. Layerwise placement
    11. Final SVG output
    """
    
    def __init__(self):
        logger.info("Initializing Raster to SVG Converter...")
        
        self.text_extractor = TextExtractor()
        self.image_detector = ImageDetector()
        self.shape_detector = ShapeDetector()
        self.background_filler = BackgroundFiller()
        self.svg_generator = SVGGenerator()
        
        # Create debug output directory if needed
        if DEBUG.get('save_intermediate_steps', False):
            os.makedirs(DEBUG.get('output_dir', './debug_output'), exist_ok=True)
        
        logger.info("Converter initialized successfully")
    
    def convert(self, input_path: str, output_path: str = 'output.svg',
               convert_images_to_svg: bool = False) -> Dict:
        """
        Convert raster infographic to SVG
        
        Args:
            input_path: Path to input raster image
            output_path: Path for output SVG file
            convert_images_to_svg: Whether to convert embedded images to SVG (experimental)
        
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
        current_image = image.copy()
        
        # Step 1: Extract text with OCR
        logger.info("=" * 50)
        logger.info("STEP 1: Text OCR")
        logger.info("=" * 50)
        text_elements = self.text_extractor.extract_text_elements(current_image)
        text_bboxes = [elem.bbox for elem in text_elements]
        
        # Step 2: Remove text and fill background
        logger.info("=" * 50)
        logger.info("STEP 2: Remove text and fill background")
        logger.info("=" * 50)
        current_image = self.background_filler.remove_and_fill(current_image, text_bboxes)
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(current_image, '02_text_removed.png', DEBUG.get('output_dir'))
        
        # Step 3-4: Detect images
        logger.info("=" * 50)
        logger.info("STEP 3-4: Image detection and removal")
        logger.info("=" * 50)
        image_elements = self.image_detector.detect_images(current_image)
        image_bboxes = [elem.bbox for elem in image_elements]
        
        # Store image data before removal
        for elem in image_elements:
            elem.image_data = original_image[elem.bbox.y:elem.bbox.y2, 
                                            elem.bbox.x:elem.bbox.x2].copy()
        
        # Remove images and fill background
        current_image = self.background_filler.remove_and_fill(current_image, image_bboxes)
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(current_image, '04_images_removed.png', DEBUG.get('output_dir'))
        
        # Step 5: Optional image to SVG conversion (placeholder)
        if convert_images_to_svg:
            logger.info("=" * 50)
            logger.info("STEP 5: Converting images to SVG (experimental)")
            logger.info("=" * 50)
            # This would require additional vectorization libraries
            logger.warning("Image to SVG conversion not fully implemented yet")
        
        # Step 6-7: Detect shapes
        logger.info("=" * 50)
        logger.info("STEP 6-7: Shape detection and removal")
        logger.info("=" * 50)
        shape_elements = self.shape_detector.detect_shapes(current_image, 
                                                          text_bboxes=text_bboxes,
                                                          image_bboxes=image_bboxes)
        shape_bboxes = [elem.bbox for elem in shape_elements]
        
        # Remove shapes and fill background (this gives us clean background)
        background_image = self.background_filler.remove_and_fill(current_image, shape_bboxes)
        
        if DEBUG.get('save_intermediate_steps', False):
            save_debug_image(background_image, '07_shapes_removed_background.png', 
                           DEBUG.get('output_dir'))
        
        # Step 8: Shape reconstruction is implicit in shape detection
        # Shapes are already represented as structured data in shape_elements
        
        # Step 9-11: Generate SVG with layers
        logger.info("=" * 50)
        logger.info("STEP 9-11: Generate layered SVG")
        logger.info("=" * 50)
        
        elements = {
            'width': width,
            'height': height,
            'background': background_image,
            'shapes': shape_elements,
            'images': image_elements,
            'text': text_elements
        }
        
        output_svg_path = self.svg_generator.generate_svg(
            width=width,
            height=height,
            background_image=background_image,
            text_elements=text_elements,
            image_elements=image_elements,
            shape_elements=shape_elements,
            output_path=output_path
        )
        
        # Compile results
        results = {
            'success': True,
            'output_path': output_svg_path,
            'statistics': {
                'text_elements': len(text_elements),
                'image_elements': len(image_elements),
                'shape_elements': len(shape_elements),
                'dimensions': (width, height)
            },
            'elements': elements
        }
        
        logger.info("=" * 50)
        logger.info("CONVERSION COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Text elements: {len(text_elements)}")
        logger.info(f"Image elements: {len(image_elements)}")
        logger.info(f"Shape elements: {len(shape_elements)}")
        logger.info(f"Output saved to: {output_svg_path}")
        
        return results
    
    def convert_batch(self, input_dir: str, output_dir: str,
                     pattern: str = '*.png') -> Dict:
        """
        Convert multiple images in batch
        
        Args:
            input_dir: Directory containing input images
            output_dir: Directory for output SVG files
            pattern: File pattern to match (default: *.png)
        
        Returns:
            Dictionary with batch conversion results
        """
        logger.info(f"Starting batch conversion from {input_dir}")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Find all matching files
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
    
    # Create converter
    converter = RasterToSVGConverter()
    
    if args.batch:
        # Batch mode
        output_dir = args.output or 'output_svg'
        results = converter.convert_batch(args.input, output_dir, args.pattern)
        print(f"\nBatch conversion results:")
        print(f"Total: {results['total']}")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
    else:
        # Single file mode
        output_path = args.output or 'output.svg'
        results = converter.convert(args.input, output_path, 
                                   convert_images_to_svg=args.convert_images)
        print(f"\nConversion successful!")
        print(f"Output: {results['output_path']}")
        print(f"Statistics: {results['statistics']}")


if __name__ == '__main__':
    main()
