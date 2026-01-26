#!/usr/bin/env python3
"""
Standalone script to visualize image detection on a single image

Usage:
    python visualize_image_detection.py <input_image> [-o output_image]

Examples:
    # Display in window
    python visualize_image_detection.py input.png
    
    # Save to file
    python visualize_image_detection.py input.png -o detection_results.png
"""

import cv2
import numpy as np
import argparse
from pathlib import Path
import logging

from image_detector import ImageDetector, ImageElement
from config import IMAGE_PROCESSING, DEBUG

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def visualize_detections(image_path: str, output_path: str = None, show_details: bool = False):
    """
    Load an image, detect images/icons, and visualize the bounding boxes
    
    Args:
        image_path: Path to input image
        output_path: Path to save visualization (optional, if None will display)
        show_details: Show detailed metrics for each detection
    """
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        logger.error(f"Failed to load image: {image_path}")
        return
    
    logger.info(f"Loaded image: {image.shape[1]}x{image.shape[0]} pixels")
    
    # Create detector
    detector = ImageDetector()
    
    # Detect images (no text/shape exclusions for standalone test)
    logger.info("Running image detection...")
    kept_images, filtered_images = detector.detect_images(image)
    
    logger.info(f"Detection complete: {len(kept_images)} kept, {len(filtered_images)} filtered")
    
    # Create visualization
    vis_image = image.copy()
    
    # Add summary header
    summary = f"Image Detection Results: {len(kept_images)} Images (RED) | {len(filtered_images)} Containers (GREEN)"
    cv2.putText(vis_image, summary, (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 3)
    cv2.putText(vis_image, summary, (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    
    # Draw kept images in RED (these are actual images/icons)
    for i, element in enumerate(kept_images):
        bbox = element.bbox
        color = (0, 0, 255)  # RED in BGR
        
        # Draw bounding box (thick for visibility)
        cv2.rectangle(vis_image, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 3)
        
        # Add label with index and size
        if show_details:
            debug_info = getattr(element, 'debug_info', {})
            score = bbox.label.split(':')[1] if ':' in bbox.label else '?'
            label = f"IMG_{i} {bbox.w}x{bbox.h} (score:{score})"
        else:
            label = f"IMG_{i} {bbox.w}x{bbox.h}"
        
        # Position label above bbox
        label_y = max(bbox.y - 10, 50)
        cv2.putText(vis_image, label, (bbox.x, label_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        logger.info(f"  Image {i}: {bbox.w}x{bbox.h} at ({bbox.x}, {bbox.y})")
    
    # Draw filtered images in GREEN (likely containers)
    for i, element in enumerate(filtered_images):
        bbox = element.bbox
        color = (0, 255, 0)  # GREEN in BGR
        
        # Draw bounding box (thick for visibility)
        cv2.rectangle(vis_image, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 3)
        
        # Add label with index and size
        if show_details:
            debug_info = getattr(element, 'debug_info', {})
            score = bbox.label.split(':')[1] if ':' in bbox.label else '?'
            label = f"CONT_{i} {bbox.w}x{bbox.h} (score:{score})"
        else:
            label = f"CONT_{i} {bbox.w}x{bbox.h}"
        
        # Position label above bbox
        label_y = max(bbox.y - 10, 50)
        cv2.putText(vis_image, label, (bbox.x, label_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        logger.info(f"  Container {i}: {bbox.w}x{bbox.h} at ({bbox.x}, {bbox.y})")
    
    # Add legend at bottom
    legend_y = vis_image.shape[0] - 20
    legend = "RED = Detected Images/Icons | GREEN = Filtered Containers"
    cv2.putText(vis_image, legend, (10, legend_y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(vis_image, legend, (10, legend_y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    
    # Save or display
    if output_path:
        cv2.imwrite(output_path, vis_image)
        logger.info(f"✓ Saved visualization to: {output_path}")
    else:
        # Display in window
        window_name = 'Image Detection Visualization'
        cv2.imshow(window_name, vis_image)
        logger.info("Press any key to close the visualization window...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description='Visualize image detection on an image',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Display in window
  python visualize_image_detection.py input.png
  
  # Save to file
  python visualize_image_detection.py input.png -o output_detection.png
  
  # Show detailed scores
  python visualize_image_detection.py input.png -d
        """
    )
    parser.add_argument('image', type=str, help='Path to input image')
    parser.add_argument('-o', '--output', type=str, help='Path to save visualization (optional)')
    parser.add_argument('-d', '--details', action='store_true', 
                       help='Show detailed detection scores in labels')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not Path(args.image).exists():
        logger.error(f"Input image not found: {args.image}")
        return 1
    
    visualize_detections(args.image, args.output, args.details)
    return 0


if __name__ == '__main__':
    exit(main())
