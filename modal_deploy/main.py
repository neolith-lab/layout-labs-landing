"""
Modal deployment for Raster to SVG converter
Converts infographic images to editable SVG files in the cloud
"""

import modal
import io
from pathlib import Path

# Create Modal app
app = modal.App("raster-to-svg-converter")

# Define secrets for AWS credentials
aws_secret = modal.Secret.from_name("aws-credentials")

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
        "boto3>=1.28.0",  # Added for S3 support
    ).add_local_dir("./logic", remote_path="/root/dev_destructure")
)

# # Mount the source code
# code_mount = modal.Mount.from_local_dir(
#     "../dev_destructure",
#     remote_path="/root/dev_destructure",
# )


@app.function(
    image=image,
    secrets=[aws_secret],  # Add AWS credentials
    timeout=600,  # 10 minutes timeout
    cpu=4,  # Use 4 CPUs for faster processing
    memory=8192,  # 8GB RAM for image processing
    gpu="L40S"
)
def convert_image_to_svg(
    image_url: str = None,
    image_bytes: bytes = None,
    s3_bucket: str = None,  # S3 bucket for storing extracted elements
) -> dict:
    """
    Convert a raster infographic image and extract all elements to S3.
    Returns JSON with S3 URLs for all extracted elements.
    
    Args:
        image_url: URL of the input image (preferred method)
        image_bytes: Input image as bytes (alternative to image_url)
        s3_bucket: S3 bucket name for storing extracted elements (defaults to env var)
    
    Returns:
        Dictionary with extraction data and statistics (all elements uploaded to S3)
    """
    import sys
    import tempfile
    import cv2
    import numpy as np
    import requests
    import os
    
    # Add the dev_destructure directory to Python path
    sys.path.insert(0, "/root/dev_destructure")
    
    from raster_to_svg import RasterToSVGConverter
    
    # Get S3 bucket from parameter or environment
    if s3_bucket is None:
        s3_bucket = os.environ.get('AWS_S3_BUCKET', 'raster-to-svg-extractions')
    
    print(f"Starting conversion with S3 bucket: {s3_bucket}")
    
    # Get image bytes from URL if provided
    if image_url:
        print(f"Downloading image from: {image_url}")
        
        # Add headers to handle various URL types
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/png,image/jpeg,image/*,*/*'
        }
        response = requests.get(image_url, timeout=30, headers=headers, allow_redirects=True)
        response.raise_for_status()
        image_bytes = response.content
        print(f"Downloaded {len(image_bytes)} bytes")
        
        # Check if content is actually an image
        content_type = response.headers.get('content-type', '')
        if 'html' in content_type.lower():
            raise ValueError(
                f"URL returned HTML instead of an image (content-type: {content_type}). "
                f"Please use a direct image URL. For filebin.net, try downloading the file "
                f"and uploading it to a proper image host like Imgur, or use the raw file URL."
            )
    elif image_bytes is None:
        raise ValueError("Either image_url or image_bytes must be provided")
    
    # Decode image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        # Provide helpful error message
        content_preview = image_bytes[:100].decode('utf-8', errors='ignore')
        if content_preview.startswith('<!DOCTYPE') or content_preview.startswith('<html'):
            raise ValueError(
                "Failed to decode image - URL returned HTML instead of image data. "
                "Please use a direct image URL (e.g., from Imgur, your own S3, or a CDN)."
            )
        raise ValueError(
            f"Failed to decode image - invalid image format. "
            f"Downloaded {len(image_bytes)} bytes. "
            f"Make sure the URL points directly to an image file (PNG, JPG, etc.)"
        )
    
    print(f"Image loaded: {image.shape[1]}x{image.shape[0]} pixels")
    
    # Create temporary file for input
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_input:
        cv2.imwrite(tmp_input.name, image)
        tmp_input_path = tmp_input.name
    
    try:
        # Create converter with S3 support (no SVG generation)
        converter = RasterToSVGConverter(s3_bucket=s3_bucket)
        result = converter.convert(
            tmp_input_path,
            generate_svg=False  # JSON-only mode, no SVG
        )
        
        # Return extraction data with S3 URLs
        response = {
            'success': True,
            'statistics': result['statistics'],
            'extraction_data': result['extraction_data']
        }
        
        print(f"Conversion complete: {result['statistics']}")
        return response
        
    finally:
        # Cleanup
        if os.path.exists(tmp_input_path):
            os.unlink(tmp_input_path)


@app.local_entrypoint()
def main(
    input_path: str = None,
    input_url: str = None,
    s3_bucket: str = None,
):
    """
    Local entrypoint for Modal CLI usage - Returns JSON with S3 URLs
    
    Usage:
        # Single file from local path
        modal run main.py --input-path input.png
        
        # Single file from URL
        modal run main.py --input-url https://example.com/image.png
        
        # With custom S3 bucket
        modal run main.py --input-path input.png --s3-bucket my-bucket
    """
    import json
    from pathlib import Path
    
    print(f"{'='*60}")
    print("RASTER TO SVG CONVERTER - Modal Deployment")
    print("JSON Extraction Mode (No SVG Generation)")
    print(f"{'='*60}\n")
    
    if not input_path and not input_url:
        print("Error: Either --input-path or --input-url must be provided")
        return
    
    if input_url:
        # URL mode
        print(f"Processing image from URL: {input_url}\n")
        
        # Convert on Modal
        result = convert_image_to_svg.remote(
            image_url=input_url,
            s3_bucket=s3_bucket,
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
        
        print(f"Processing image: {input_path}\n")
        
        # Convert on Modal
        result = convert_image_to_svg.remote(
            image_bytes=image_bytes,
            s3_bucket=s3_bucket,
        )
    
    # Print results
    print(f"\n{'='*60}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"\nStatistics:")
    stats = result['statistics']
    print(f"  Text elements:       {stats['text_elements']}")
    print(f"  Logos:               {stats['logos']}")
    print(f"  Containers:          {stats['containers']}")
    print(f"  Images (containers): {stats['images_in_containers']}")
    print(f"  Images (standalone): {stats['standalone_images']}")
    print(f"  Dimensions:          {stats['dimensions'][0]}x{stats['dimensions'][1]}")
    
    # Print S3 info
    if result['extraction_data']:
        metadata = result['extraction_data']['metadata']
        print(f"\nS3 Storage:")
        print(f"  Bucket: {metadata.get('s3_bucket')}")
        print(f"  Prefix: {metadata.get('s3_prefix')}")
    
    # Save extraction data to local JSON file
    output_json = 'extraction_data.json'
    with open(output_json, 'w') as f:
        json.dump(result['extraction_data'], f, indent=2)
    
    print(f"\n✓ Extraction data saved to: {output_json}")
    print(f"✓ All elements uploaded to S3!")
