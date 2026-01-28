"""
Modal deployment for Raster to SVG converter
Converts infographic images to editable SVG files in the cloud
"""

import modal
import io
from pathlib import Path

# Create Modal app
app = modal.App("raster-to-svg-converter")

# Define the image with all required dependencies
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install(
        "tesseract-ocr",
        "tesseract-ocr-eng",
        "libgl1-mesa-glx",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libxrender-dev",
        "libgomp1",
        "libglib2.0-0",
    )
    .pip_install(
        "opencv-python-headless>=4.8.0",
        "numpy>=1.24.0",
        "pillow>=10.0.0",
        "pytesseract>=0.3.10",
        "svgwrite>=1.4.3",
        "scikit-image>=0.21.0",
        "scipy>=1.11.0",
        "fontTools>=4.42.0",
        "shapely>=2.0.0",
        "easyocr>=1.7.0",
        "requests>=2.31.0",
    ).add_local_dir("../dev_destructure", remote_path="/root/dev_destructure")
)

# # Mount the source code
# code_mount = modal.Mount.from_local_dir(
#     "../dev_destructure",
#     remote_path="/root/dev_destructure",
# )


@app.function(
    image=image,
    # mounts=[code_mount],
    timeout=600,  # 10 minutes timeout
    cpu=4,  # Use 4 CPUs for faster processing
    memory=8192,  # 8GB RAM for image processing
    gpu="L40S"
)
def convert_image_to_svg(
    image_url: str = None,
    image_bytes: bytes = None,
    output_filename: str = "output.svg",
    debug: bool = False,
    ocr_confidence: int = 60,
    convert_images: bool = False,
) -> dict:
    """
    Convert a raster infographic image to SVG
    
    Args:
        image_url: URL of the input image (preferred method)
        image_bytes: Input image as bytes (alternative to image_url)
        output_filename: Name for output SVG file
        debug: Enable debug mode (saves intermediate steps)
        ocr_confidence: Minimum OCR confidence threshold (0-100)
        convert_images: Convert embedded images to SVG (experimental)
    
    Returns:
        Dictionary with SVG content, statistics, and debug images
    """
    import sys
    import tempfile
    import cv2
    import numpy as np
    import requests
    
    # Add the dev_destructure directory to Python path
    sys.path.insert(0, "/root/dev_destructure")
    
    from raster_to_svg import RasterToSVGConverter
    from config import DEBUG, OCR_CONFIG
    
    # Configure settings
    if debug:
        DEBUG['save_intermediate_steps'] = True
        DEBUG['output_dir'] = '/tmp/debug_output'
    
    OCR_CONFIG['min_confidence'] = ocr_confidence
    
    print(f"Starting conversion with debug={debug}, ocr_confidence={ocr_confidence}")
    
    # Get image bytes from URL if provided
    if image_url:
        print(f"Downloading image from: {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
        print(f"Downloaded {len(image_bytes)} bytes")
    elif image_bytes is None:
        raise ValueError("Either image_url or image_bytes must be provided")
    
    # Decode image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("Failed to decode image")
    
    print(f"Image loaded: {image.shape[1]}x{image.shape[0]} pixels")
    
    # Create temporary files for input and output
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_input:
        cv2.imwrite(tmp_input.name, image)
        tmp_input_path = tmp_input.name
    
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as tmp_output:
        tmp_output_path = tmp_output.name
    
    try:
        # Create converter and process
        converter = RasterToSVGConverter()
        result = converter.convert(
            tmp_input_path,
            tmp_output_path,
            convert_images_to_svg=convert_images
        )
        
        # Read the SVG output
        with open(tmp_output_path, 'r') as f:
            svg_content = f.read()
        
        # Prepare result
        response = {
            'svg_content': svg_content,
            'statistics': result['statistics'],
            'debug_images': {}
        }
        
        # Include debug images if available
        if debug and DEBUG.get('save_intermediate_steps', False):
            import os
            debug_dir = DEBUG.get('output_dir', '/tmp/debug_output')
            if os.path.exists(debug_dir):
                for filename in os.listdir(debug_dir):
                    if filename.endswith(('.png', '.jpg')):
                        filepath = os.path.join(debug_dir, filename)
                        with open(filepath, 'rb') as f:
                            response['debug_images'][filename] = f.read()
        
        print(f"Conversion complete: {result['statistics']}")
        return response
        
    finally:
        # Cleanup
        import os
        if os.path.exists(tmp_input_path):
            os.unlink(tmp_input_path)
        if os.path.exists(tmp_output_path):
            os.unlink(tmp_output_path)


@app.function(
    image=image,
    timeout=1800,  # 30 minutes for batch
    cpu=4,
    memory=8192,
)
def convert_batch_images(
    image_files: dict[str, bytes],
    debug: bool = False,
    ocr_confidence: int = 60,
    convert_images: bool = False,
) -> dict:
    """
    Convert multiple images to SVG in batch
    
    Args:
        image_files: Dictionary mapping filenames to image bytes
        debug: Enable debug mode
        ocr_confidence: Minimum OCR confidence threshold
        convert_images: Convert embedded images to SVG
    
    Returns:
        Dictionary with results for each file
    """
    results = {
        'total': len(image_files),
        'successful': 0,
        'failed': 0,
        'details': []
    }
    
    for filename, image_bytes in image_files.items():
        print(f"\nProcessing {filename}...")
        try:
            result = convert_image_to_svg.local(
                image_bytes=image_bytes,
                output_filename=filename.replace('.png', '.svg').replace('.jpg', '.svg'),
                debug=debug,
                ocr_confidence=ocr_confidence,
                convert_images=convert_images,
            )
            results['successful'] += 1
            results['details'].append({
                'file': filename,
                'status': 'success',
                'statistics': result['statistics']
            })
            print(f"✓ {filename} converted successfully")
            
        except Exception as e:
            results['failed'] += 1
            results['details'].append({
                'file': filename,
                'status': 'failed',
                'error': str(e)
            })
            print(f"✗ {filename} failed: {e}")
    
    return results


@app.local_entrypoint()
def main(
    input_path: str = None,
    input_url: str = None,
    output_path: str = "output.svg",
    batch: bool = False,
    pattern: str = "*.png",
    debug: bool = False,
    ocr_confidence: int = 60,
    convert_images: bool = False,
):
    """
    Local entrypoint for Modal CLI usage
    
    Usage:
        # Single file from local path
        modal run main.py --input-path input.png --output-path output.svg
        
        # Single file from URL
        modal run main.py --input-url https://example.com/image.png --output-path output.svg
        
        # Batch mode
        modal run main.py --input-path ./images --output-path ./output --batch --pattern "*.png"
        
        # With debug
        modal run main.py --input-path input.png --debug
    """
    import os
    from pathlib import Path
    
    print(f"{'='*60}")
    print("RASTER TO SVG CONVERTER - Modal Deployment")
    print(f"{'='*60}\n")
    
    if not input_path and not input_url:
        print("Error: Either --input-path or --input-url must be provided")
        return
    
    if batch:
        # Batch mode: process directory
        input_dir = Path(input_path)
        if not input_dir.is_dir():
            print(f"Error: {input_path} is not a directory")
            return
        
        # Find all matching files
        image_files = {}
        for file_path in input_dir.glob(pattern):
            with open(file_path, 'rb') as f:
                image_files[file_path.name] = f.read()
        
        if not image_files:
            print(f"No files matching pattern '{pattern}' found in {input_path}")
            return
        
        print(f"Found {len(image_files)} images to process\n")
        
        # Process in batch
        results = convert_batch_images.remote(
            image_files=image_files,
            debug=debug,
            ocr_confidence=ocr_confidence,
            convert_images=convert_images,
        )
        
        # Save SVG outputs
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for detail in results['details']:
            if detail['status'] == 'success':
                # Note: In batch mode, we'd need to modify convert_batch_images 
                # to return SVG content. For now, just report statistics.
                print(f"\n✓ {detail['file']}: {detail['statistics']}")
        
        # Print summary
        print(f"\n{'='*60}")
        print("BATCH CONVERSION COMPLETE")
        print(f"{'='*60}")
        print(f"Total files:     {results['total']}")
        print(f"Successful:      {results['successful']}")
        print(f"Failed:          {results['failed']}")
        
    else:
        # Single file mode
        if input_url:
            # URL mode
            print(f"Converting from URL '{input_url}' to '{output_path}'...\n")
            
            # Convert on Modal
            result = convert_image_to_svg.remote(
                image_url=input_url,
                output_filename=output_path,
                debug=debug,
                ocr_confidence=ocr_confidence,
                convert_images=convert_images,
            )
        else:
            # Local file mode
            input_file = Path(input_path)
            if not input_file.exists():
                print(f"Error: File not found: {input_path}")
                return
            
            # Read input image
            with open(input_file, 'rb') as f:
                image_bytes = f.read()
            
            print(f"Converting '{input_path}' to '{output_path}'...\n")
            
            # Convert on Modal
            result = convert_image_to_svg.remote(
                image_bytes=image_bytes,
                output_filename=output_path,
                debug=debug,
                ocr_confidence=ocr_confidence,
                convert_images=convert_images,
            )
        
        # Save SVG output
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(result['svg_content'])
        
        # Save debug images if available
        if debug and result['debug_images']:
            debug_dir = output_file.parent / 'debug_output'
            debug_dir.mkdir(exist_ok=True)
            for filename, image_data in result['debug_images'].items():
                debug_path = debug_dir / filename
                with open(debug_path, 'wb') as f:
                    f.write(image_data)
            print(f"\nDebug images saved to: {debug_dir}")
        
        # Print results
        print(f"\n{'='*60}")
        print("CONVERSION COMPLETE")
        print(f"{'='*60}")
        print(f"Output file:     {output_path}")
        print(f"\nStatistics:")
        stats = result['statistics']
        print(f"  Text elements:       {stats['text_elements']}")
        print(f"  Logos:               {stats['logos']}")
        print(f"  Containers:          {stats['containers']}")
        print(f"  Images (containers): {stats['images_in_containers']}")
        print(f"  Images (standalone): {stats['standalone_images']}")
        print(f"  Shape elements:      {stats['shapes']}")
        print(f"  Dimensions:          {stats['dimensions'][0]}x{stats['dimensions'][1]}")
        print(f"\n✓ Conversion completed successfully!")