#!/usr/bin/env python3
"""
Test script to verify Modal deployment is working correctly
"""

import sys
from pathlib import Path


def test_modal_deployment():
    """
    Run basic tests to verify Modal deployment
    """
    print("="*60)
    print("Testing Modal Deployment")
    print("="*60)
    
    # Test 1: Check if Modal is installed
    print("\n[Test 1] Checking Modal installation...")
    try:
        import modal
        print("✓ Modal is installed")
    except ImportError:
        print("✗ Modal is not installed. Run: pip install modal")
        return False
    
    image_bytes = None
    
    input_file = Path("../dev_destructure/input.png")
    with open(input_file, 'rb') as f:
        image_bytes = f.read()

    
    output_path = "test_output.svg"
    f = modal.Function.from_name("raster-to-svg-converter", "convert_image_to_svg")
    result = f.remote(image_bytes=image_bytes, output_filename="test_output.svg", debug=False, ocr_confidence=60, convert_images=False)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(result['svg_content'])
    # Test 2: Attempt to lookup deployed function


if __name__ == '__main__':
    success = test_modal_deployment()
    sys.exit(0 if success else 1)
