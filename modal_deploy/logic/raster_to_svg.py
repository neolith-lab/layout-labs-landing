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
import json
from pathlib import Path
from datetime import datetime
import uuid

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
    
    def __init__(self, s3_bucket: str = "layoutlabs-temp", s3_prefix: str = None):
        logger.info("Initializing Raster to SVG Converter...")
        
        self.text_extractor = TextExtractor()
        self.image_detector = ImageDetector()
        self.container_detector = ContainerDetector()
        self.background_filler = BackgroundFiller()
        self.svg_generator = SVGGenerator()
        
        # S3 configuration for storing extracted elements
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix or f"extractions/{uuid.uuid4().hex}"
        self.use_s3 = s3_bucket is not None
        
        if self.use_s3:
            try:
                import boto3
                import os
                
                # Check for required AWS credentials
                aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
                aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
                aws_region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
                
                missing_vars = []
                if not aws_access_key:
                    missing_vars.append('AWS_ACCESS_KEY_ID')
                if not aws_secret_key:
                    missing_vars.append('AWS_SECRET_ACCESS_KEY')
                if not aws_region:
                    missing_vars.append('AWS_REGION (or AWS_DEFAULT_REGION)')
                
                if missing_vars:
                    error_msg = (
                        f"Missing required AWS credentials: {', '.join(missing_vars)}\n"
                        f"Please set these environment variables:\n"
                        f"  export AWS_ACCESS_KEY_ID=your-access-key\n"
                        f"  export AWS_SECRET_ACCESS_KEY=your-secret-key\n"
                        f"  export AWS_REGION=ap-south-1  # Your bucket region"
                    )
                    raise ValueError(error_msg)
                
                # Initialize S3 client with explicit region
                self.s3_client = boto3.client(
                    's3',
                    region_name=aws_region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key
                )
                
                # Verify bucket access
                try:
                    self.s3_client.head_bucket(Bucket=self.s3_bucket)
                    logger.info(f"S3 storage enabled: s3://{self.s3_bucket}/{self.s3_prefix}")
                except Exception as bucket_error:
                    raise ValueError(
                        f"Cannot access S3 bucket '{self.s3_bucket}': {bucket_error}\n"
                        f"Please verify:\n"
                        f"  1. Bucket exists in region {aws_region}\n"
                        f"  2. Your credentials have s3:PutObject permission\n"
                        f"  3. Bucket name is correct: {self.s3_bucket}"
                    )
                    
            except ImportError:
                raise ImportError(
                    "boto3 is required for S3 uploads. Install it with:\n"
                    "  pip install boto3"
                )
            except ValueError:
                # Re-raise our custom errors with helpful messages
                raise
            except Exception as e:
                raise RuntimeError(f"Failed to initialize S3 client: {e}")
        
        # Create debug output directory if needed
        if DEBUG.get('save_intermediate_steps', False):
            os.makedirs(DEBUG.get('output_dir', './debug_output'), exist_ok=True)
        
        # Initialize debug data collector for combined JSON
        self._debug_data = {}
        
        logger.info("Converter initialized successfully")
    
    def convert(self, input_path: str, output_path: str = None,
               convert_images_to_svg: bool = False, 
               generate_svg: bool = True) -> Dict:
        """
        Convert raster infographic and extract elements (optionally generate SVG)
        
        Args:
            input_path: Path to input raster image
            output_path: Path for output SVG file (optional if generate_svg=False)
            convert_images_to_svg: Whether to vectorize embedded images (experimental)
            generate_svg: Whether to generate SVG file (False for JSON-only extraction)
        
        Returns:
            Dictionary with conversion results, statistics, and extraction_data
        """
        logger.info(f"Starting conversion: {input_path}")
        if generate_svg and output_path:
            logger.info(f"SVG output: {output_path}")
        else:
            logger.info("JSON-only mode (no SVG generation)")

        
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
        
        # Save text elements debug data (Stage 1: Text Detection)
        text_debug_data = self._save_text_elements_debug(original_image, text_elements)
        
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
        
        # Save image elements debug data (Stage 2: Image Detection)
        image_debug_data = self._save_image_elements_debug(text_removed_image, image_elements)
        
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
            # Extract colors from the ORIGINAL image (before infilling)
            fill_color = self._extract_container_fill_color(original_image, bbox)
            stroke_color = self._extract_container_stroke_color(original_image, contour)
            
            container = ContainerElement(
                container_type=ContainerType.RECTANGLE,
                bbox=bbox,
                contour=contour,
                fill_color=fill_color,
                stroke_color=stroke_color,
                stroke_width=1,
                corner_radius=self._estimate_corner_radius_from_image(original_image, bbox)
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
        
        # Save container elements debug data (Stage 3: Container Detection)
        container_debug_data = self._save_container_elements_debug(cleaned_image, containers)
        
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
        
        # Save background debug data (Stage 4: Background Extraction)
        background_debug_data = self._save_background_debug(background_image, width, height)

        
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
        
        # Generate SVG with proper layers (only if requested)
        output_svg_path = None
        if generate_svg:
            if not output_path:
                raise ValueError("output_path is required when generate_svg=True")
            
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
            logger.info(f"SVG generated: {output_svg_path}")
        else:
            logger.info("Skipping SVG generation (JSON-only mode)")
        
        # ============================================================
        # COMPILE RESULTS
        # ============================================================
        
        # Create combined extraction data
        extraction_data = self._save_combined_debug_json(
            input_path=input_path,
            output_path=output_svg_path,
            text_data=text_debug_data,
            image_data=image_debug_data,
            container_data=container_debug_data,
            background_data=background_debug_data,
            statistics={
                'text_elements': len(text_elements),
                'logos': 0,
                'containers': len(containers),
                'images_in_containers': len(images_in_containers),
                'standalone_images': len(images_outside),
                'shapes': 0,
                'dimensions': (width, height)
            }
        )
        
        results = {
            'success': True,
            'output_path': output_svg_path,
            'statistics': extraction_data['statistics'],
            'extraction_data': extraction_data,
            'elements': {
                'text': text_elements,
                'logos': [],
                'containers': containers,
                'images_in_containers': images_in_containers,
                'standalone_images': images_outside,
                'shapes': [],
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
        if output_svg_path:
            logger.info(f"SVG saved to: {output_svg_path}")
        
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
    
    def _get_debug_dir(self) -> str:
        """Get the debug output directory path"""
        return DEBUG.get('output_dir', './debug_output')
    
    def _ensure_debug_subdir(self, subdir: str) -> str:
        """Ensure a subdirectory exists in the debug output folder"""
        path = os.path.join(self._get_debug_dir(), subdir)
        os.makedirs(path, exist_ok=True)
        return path
    
    def _upload_bytes_to_s3(self, data: bytes, s3_key: str, content_type: str = 'application/octet-stream') -> Optional[str]:
        """
        Upload bytes directly to S3 and return the URL.
        
        Args:
            data: Bytes to upload
            s3_key: S3 object key (path in bucket)
            content_type: MIME type of the content
            
        Returns:
            Public URL to the uploaded file, or None if upload failed
        """
        if not self.use_s3:
            return None
        
        try:
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=data,
                ContentType=content_type
            )
            # Use region-specific URL format
            region = self.s3_client.meta.region_name
            if region == 'us-east-1':
                url = f"https://{self.s3_bucket}.s3.amazonaws.com/{s3_key}"
            else:
                url = f"https://{self.s3_bucket}.s3.{region}.amazonaws.com/{s3_key}"
            logger.debug(f"Uploaded to S3: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to upload {s3_key} to S3: {e}")
            raise  # Propagate error instead of silently returning None
    
    def _upload_image_to_s3(self, image: np.ndarray, s3_key: str) -> Optional[str]:
        """
        Upload a numpy image array directly to S3 and return the URL.
        
        Args:
            image: NumPy image array
            s3_key: S3 object key (path in bucket)
            
        Returns:
            Public URL to the uploaded image, or None if upload failed
        """
        if not self.use_s3:
            return None
        
        try:
            # Encode image to PNG bytes
            success, buffer = cv2.imencode('.png', image)
            if not success:
                raise ValueError("Failed to encode image to PNG")
            
            # Upload directly to S3
            return self._upload_bytes_to_s3(buffer.tobytes(), s3_key, 'image/png')
        except Exception as e:
            logger.error(f"Failed to upload image to S3: {e}")
            raise  # Propagate error instead of silently returning None
    
    def _save_text_elements_debug(self, original_image: np.ndarray, 
                                   text_elements: List[TextElement]) -> Dict:
        """
        Save text elements metadata (no image cropping - text is defined by metadata only).
        
        Args:
            original_image: The original input image (not used, kept for API compatibility)
            text_elements: List of detected TextElement objects
            
        Returns:
            Dictionary with text elements metadata for combined JSON
        """
        logger.info("Processing text elements metadata...")
        
        text_data = {
            'stage': 'text_detection',
            'count': int(len(text_elements)),
            'elements': []
        }
        
        for i, elem in enumerate(text_elements):
            bbox = elem.bbox
            
            # Build element metadata (no image cropping - text is defined by metadata)
            element_data = {
                'id': int(i),
                'text': str(elem.text),
                'bbox': {
                    'x': int(bbox.x),
                    'y': int(bbox.y),
                    'width': int(bbox.w),
                    'height': int(bbox.h),
                    'x2': int(bbox.x2),
                    'y2': int(bbox.y2)
                },
                'font': {
                    'family': str(elem.font_family),
                    'size': int(elem.font_size),
                    'weight': str(elem.font_weight),
                    'style': str(elem.font_style),
                    'classified_font': str(elem.classified_font) if elem.classified_font else '',
                    'classified_font_version': str(elem.classified_font_version) if elem.classified_font_version else '',
                    'classification_confidence': float(elem.font_classification_confidence),
                    'fallback_fonts': [str(f) for f in elem.fallback_fonts],
                    'line_height': float(elem.line_height),
                    'letter_spacing': float(elem.letter_spacing)
                },
                'color': str(elem.color),
                'confidence': float(elem.confidence),
                'num_lines': int(elem.num_lines)
            }
            text_data['elements'].append(element_data)
        
        logger.info(f"Processed {len(text_elements)} text elements metadata")
        return text_data
    
    def _save_image_elements_debug(self, original_image: np.ndarray,
                                    image_elements: List[ImageElement],
                                    stage_name: str = 'images') -> Dict:
        """
        Upload image elements to S3 and encode as base64 for direct Excalidraw use.
        
        Args:
            original_image: The image to crop from (text-removed image for accurate crops)
            image_elements: List of detected ImageElement objects
            stage_name: Name for the output subfolder
            
        Returns:
            Dictionary with image elements metadata including base64 data for combined JSON
        """
        import base64
        
        logger.info(f"Processing image elements ({stage_name})...")
        
        image_data = {
            'stage': 'image_detection',
            'count': int(len(image_elements)),
            'elements': []
        }
        
        for i, elem in enumerate(image_elements):
            bbox = elem.bbox
            
            # Crop the image region
            cropped = original_image[bbox.y:bbox.y2, bbox.x:bbox.x2].copy()
            
            # Encode to PNG bytes and base64
            success, buffer = cv2.imencode('.png', cropped)
            if not success:
                logger.warning(f"Failed to encode image {i}, skipping")
                continue
            
            png_bytes = buffer.tobytes()
            img_base64 = base64.b64encode(png_bytes).decode('utf-8')
            
            # Upload to S3 if enabled
            s3_url = None
            if self.use_s3:
                crop_filename = f"image_{i:03d}.png"
                s3_key = f"{self.s3_prefix}/image_elements/{crop_filename}"
                s3_url = self._upload_bytes_to_s3(png_bytes, s3_key, 'image/png')
            
            # Build element metadata with base64 for direct Excalidraw use
            element_data = {
                'id': int(i),
                'bbox': {
                    'x': int(bbox.x),
                    'y': int(bbox.y),
                    'width': int(bbox.w),
                    'height': int(bbox.h),
                    'x2': int(bbox.x2),
                    'y2': int(bbox.y2)
                },
                'is_photo': bool(elem.is_photo),
                'dominant_colors': [[int(c) for c in color] for color in elem.dominant_colors] if elem.dominant_colors else [],
                'area': int(bbox.w * bbox.h),
                'aspect_ratio': float(round(bbox.w / bbox.h, 3)) if bbox.h > 0 else 0.0,
                'base64_data': img_base64,  # Base64 for direct Excalidraw embedding
                'mime_type': 'image/png',
                's3_url': s3_url
            }
            image_data['elements'].append(element_data)
        
        logger.info(f"Processed {len(image_data['elements'])} image elements" + 
                   (f" (uploaded to S3)" if self.use_s3 else ""))
        return image_data
    
    def _save_container_elements_debug(self, cleaned_image: np.ndarray,
                                        containers: List[ContainerElement]) -> Dict:
        """
        Upload container elements directly to S3: JSON metadata and cropped container images.
        
        Args:
            cleaned_image: The cleaned image (after text/image removal) to crop from
            containers: List of detected ContainerElement objects
            
        Returns:
            Dictionary with container elements metadata for combined JSON
        """
        if not self.use_s3:
            return {}
        
        logger.info("Uploading container elements to S3...")
        
        container_data = {
            'stage': 'container_detection',
            'count': int(len(containers)),
            'elements': []
        }
        
        for i, container in enumerate(containers):
            bbox = container.bbox
            
            # Crop the container region
            cropped = cleaned_image[bbox.y:bbox.y2, bbox.x:bbox.x2].copy()
            
            # Upload cropped image directly to S3
            crop_filename = f"container_{i:03d}.png"
            s3_key = f"{self.s3_prefix}/container_elements/{crop_filename}"
            s3_url = self._upload_image_to_s3(cropped, s3_key)
            
            # Build element metadata
            element_data = {
                'id': int(i),
                'container_type': str(container.container_type.value) if hasattr(container.container_type, 'value') else str(container.container_type),
                'bbox': {
                    'x': int(bbox.x),
                    'y': int(bbox.y),
                    'width': int(bbox.w),
                    'height': int(bbox.h),
                    'x2': int(bbox.x2),
                    'y2': int(bbox.y2)
                },
                'fill_color': str(container.fill_color),
                'stroke_color': str(container.stroke_color),
                'stroke_width': int(container.stroke_width),
                'corner_radius': int(container.corner_radius),
                'contains_image': bool(container.contains_image),
                'contains_text': bool(container.contains_text),
                'area': int(bbox.w * bbox.h),
                'aspect_ratio': float(round(bbox.w / bbox.h, 3)) if bbox.h > 0 else 0.0,
                'cropped_image': str(crop_filename),
                's3_url': s3_url
            }
            container_data['elements'].append(element_data)
        
        logger.info(f"Uploaded {len(containers)} container elements to S3")
        return container_data
    
    def _save_background_debug(self, background_image: np.ndarray,
                                original_width: int, original_height: int) -> Dict:
        """
        Process background: encode as base64 and optionally upload to S3.
        
        Args:
            background_image: The extracted background image (all elements removed)
            original_width: Original image width
            original_height: Original image height
            
        Returns:
            Dictionary with background metadata including base64 for combined JSON
        """
        import base64
        
        logger.info("Processing background...")
        
        # Encode to PNG bytes and base64
        success, buffer = cv2.imencode('.png', background_image)
        if not success:
            logger.warning("Failed to encode background image")
            return {}
        
        png_bytes = buffer.tobytes()
        img_base64 = base64.b64encode(png_bytes).decode('utf-8')
        
        # Upload to S3 if enabled
        s3_url = None
        if self.use_s3:
            bg_filename = 'background.png'
            s3_key = f"{self.s3_prefix}/background/{bg_filename}"
            s3_url = self._upload_bytes_to_s3(png_bytes, s3_key, 'image/png')
            logger.info("Uploaded background to S3")
        
        # Calculate dominant colors in background
        # Sample from center region to avoid edge artifacts
        h, w = background_image.shape[:2]
        sample_region = background_image[h//4:3*h//4, w//4:3*w//4]
        avg_color = np.mean(sample_region, axis=(0, 1)).astype(int)
        avg_color_hex = '#{:02x}{:02x}{:02x}'.format(avg_color[2], avg_color[1], avg_color[0])  # BGR to RGB
        
        background_data = {
            'stage': 'background_extraction',
            'dimensions': {
                'width': int(original_width),
                'height': int(original_height)
            },
            'bbox': {
                'x': 0,
                'y': 0,
                'width': int(original_width),
                'height': int(original_height)
            },
            'average_color': {
                'rgb': [int(avg_color[2]), int(avg_color[1]), int(avg_color[0])],  # BGR to RGB
                'hex': str(avg_color_hex)
            },
            'base64_data': img_base64,  # Base64 for direct Excalidraw embedding
            'mime_type': 'image/png',
            's3_url': s3_url
        }
        
        logger.info("Processed background" + (f" (uploaded to S3)" if self.use_s3 else ""))
        return background_data
    
    def _save_combined_debug_json(self, input_path: str, output_path: str,
                                   text_data: Dict, image_data: Dict,
                                   container_data: Dict, background_data: Dict,
                                   statistics: Dict) -> Dict:
        """
        Create combined debug data from all stages and upload to S3. Returns the JSON dict.
        
        Args:
            input_path: Path to the input image
            output_path: Path to the output SVG (if generated)
            text_data: Text elements debug data
            image_data: Image elements debug data
            container_data: Container elements debug data
            background_data: Background debug data
            statistics: Conversion statistics
            
        Returns:
            Combined extraction data as dictionary with S3 URL if uploaded
        """
        logger.info("Creating combined extraction JSON...")
        
        combined_data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'input_file': input_path,
                'output_file': output_path if output_path else None,
                's3_bucket': self.s3_bucket if self.use_s3 else None,
                's3_prefix': self.s3_prefix if self.use_s3 else None
            },
            'statistics': statistics,
            'stages': {
                'text_detection': text_data,
                'image_detection': image_data,
                'container_detection': container_data,
                'background_extraction': background_data
            }
        }
        
        # Upload JSON to S3 if enabled
        if self.use_s3:
            logger.info("Uploading extraction JSON to S3...")
            json_filename = 'extraction_data.json'
            s3_key = f"{self.s3_prefix}/{json_filename}"
            json_bytes = json.dumps(combined_data, indent=2).encode('utf-8')
            s3_url = self._upload_bytes_to_s3(json_bytes, s3_key, 'application/json')
            
            # Add S3 URL to metadata
            combined_data['metadata']['json_s3_url'] = s3_url
            logger.info(f"Extraction JSON uploaded to S3: {s3_url}")
        
        logger.info("Combined extraction JSON created")
        return combined_data
    
    def _extract_container_fill_color(self, image: np.ndarray, bbox: BoundingBox) -> str:
        """Extract the dominant fill color from a container region"""
        try:
            # Get the interior region (avoiding edges)
            margin = 10
            x1 = max(bbox.x + margin, 0)
            y1 = max(bbox.y + margin, 0)
            x2 = min(bbox.x2 - margin, image.shape[1])
            y2 = min(bbox.y2 - margin, image.shape[0])
            
            if x2 <= x1 or y2 <= y1:
                return '#FFFFFF'
            
            region = image[y1:y2, x1:x2]
            
            if region.size == 0:
                return '#FFFFFF'
            
            # Get median color
            from utils import rgb_to_hex
            median_color = np.median(region.reshape(-1, 3), axis=0).astype(int)
            return rgb_to_hex(tuple(median_color[::-1]))  # BGR to RGB
        except:
            return '#FFFFFF'
    
    def _estimate_corner_radius_from_image(self, image: np.ndarray, bbox: BoundingBox) -> int:
        """
        Estimate corner radius of a container by analyzing the corner regions
        of the actual image. Looks for curved transitions in the corners.
        
        Strategy: In each corner, find the edge pixels and measure how far 
        the edge curves away from the sharp corner point.
        """
        try:
            h_img, w_img = image.shape[:2]
            x1 = max(0, bbox.x)
            y1 = max(0, bbox.y)
            x2 = min(w_img, bbox.x2)
            y2 = min(h_img, bbox.y2)
            
            if x2 - x1 < 20 or y2 - y1 < 20:
                return 0
            
            region = image[y1:y2, x1:x2]
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            rh, rw = edges.shape
            # Sample corner region size: 15% of smaller dimension, capped at 30px
            corner_size = min(30, max(5, min(rh, rw) // 7))
            
            radii = []
            # Check each corner
            corners = [
                edges[:corner_size, :corner_size],            # top-left
                edges[:corner_size, -corner_size:],           # top-right
                edges[-corner_size:, :corner_size],           # bottom-left
                edges[-corner_size:, -corner_size:],          # bottom-right
            ]
            corner_points = [
                (0, 0),                                        # top-left origin
                (0, corner_size - 1),                          # top-right origin
                (corner_size - 1, 0),                          # bottom-left origin
                (corner_size - 1, corner_size - 1),            # bottom-right origin
            ]
            
            for corner_edges, (cy, cx) in zip(corners, corner_points):
                edge_coords = np.argwhere(corner_edges > 0)
                if len(edge_coords) < 3:
                    radii.append(0)
                    continue
                
                # Measure average distance of edge pixels from the sharp corner
                distances = np.sqrt((edge_coords[:, 0] - cy) ** 2 + (edge_coords[:, 1] - cx) ** 2)
                avg_dist = np.mean(distances)
                
                # If edge pixels are clustered near the corner, radius is small
                # If they arc away, radius is larger
                if avg_dist > 3:
                    radii.append(int(avg_dist * 0.7))
                else:
                    radii.append(0)
            
            # Use median of the 4 corners
            median_radius = int(np.median(radii))
            return max(0, min(median_radius, min(bbox.w, bbox.h) // 4))
            
        except Exception:
            return 0
    
    def _extract_container_stroke_color(self, image: np.ndarray, contour: np.ndarray) -> str:
        """Extract the stroke/border color from a container.
        
        Strategy: Compare the median color of the outer edge ring (3px band 
        just inside the bbox boundary) with the interior fill. If they differ
        significantly, the outer ring IS the border color. Otherwise, the 
        container has no visible border and we return the fill color (making
        the stroke invisible in practice).
        """
        try:
            from utils import rgb_to_hex
            
            bbox_x, bbox_y, bbox_w, bbox_h = cv2.boundingRect(contour)
            
            # Clamp to image bounds
            h_img, w_img = image.shape[:2]
            x1 = max(0, bbox_x)
            y1 = max(0, bbox_y)
            x2 = min(w_img, bbox_x + bbox_w)
            y2 = min(h_img, bbox_y + bbox_h)
            
            if x2 - x1 < 10 or y2 - y1 < 10:
                return '#000000'
            
            region = image[y1:y2, x1:x2]
            rh, rw = region.shape[:2]
            
            # Create edge mask (3px band along the boundary)
            edge_width = 3
            edge_mask = np.zeros((rh, rw), dtype=np.uint8)
            edge_mask[:edge_width, :] = 255   # top
            edge_mask[-edge_width:, :] = 255  # bottom
            edge_mask[:, :edge_width] = 255   # left
            edge_mask[:, -edge_width:] = 255  # right
            
            # Create interior mask (exclude outer 8px band)
            interior_margin = max(8, min(rh, rw) // 8)
            interior_mask = np.zeros((rh, rw), dtype=np.uint8)
            if rh > 2 * interior_margin and rw > 2 * interior_margin:
                interior_mask[interior_margin:-interior_margin, interior_margin:-interior_margin] = 255
            else:
                # Too small for interior, just return edge color
                edge_pixels = region[edge_mask > 0]
                if len(edge_pixels) > 0:
                    median_edge = np.median(edge_pixels, axis=0).astype(int)
                    return rgb_to_hex(tuple(median_edge[::-1]))
                return '#000000'
            
            edge_pixels = region[edge_mask > 0]
            interior_pixels = region[interior_mask > 0]
            
            if len(edge_pixels) == 0 or len(interior_pixels) == 0:
                return '#000000'
            
            median_edge = np.median(edge_pixels, axis=0).astype(int)
            median_interior = np.median(interior_pixels, axis=0).astype(int)
            
            # Check if there's a visible border (color difference > 25)
            color_diff = np.sqrt(np.sum((median_edge.astype(float) - median_interior.astype(float)) ** 2))
            
            if color_diff > 25:
                # There's a real border — return edge color
                return rgb_to_hex(tuple(median_edge[::-1]))
            else:
                # No visible border — return fill color so stroke is invisible
                return rgb_to_hex(tuple(median_interior[::-1]))
                
        except Exception:
            return '#000000'


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
