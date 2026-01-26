#!/usr/bin/env python3
"""
Example script showing how to use the Modal-deployed converter from Python
"""

import modal
from pathlib import Path


def convert_single_image(input_path: str, output_path: str, debug: bool = False):
    """
    Convert a single image to SVG using Modal
    
    Args:
        input_path: Path to input image
        output_path: Path for output SVG
        debug: Enable debug mode
    """
    # Read the input image
    with open(input_path, 'rb') as f:
        image_bytes = f.read()
    
    # Get the Modal function
    convert_fn = modal.Function.lookup("raster-to-svg-converter", "convert_image_to_svg")
    
    print(f"Converting {input_path} using Modal...")
    
    # Run conversion on Modal
    result = convert_fn.remote(
        image_bytes=image_bytes,
        output_filename=Path(output_path).name,
        debug=debug,
        ocr_confidence=60,
        convert_images=False,
    )
    
    # Save the SVG
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(result['svg_content'])
    
    print(f"✓ Saved SVG to: {output_path}")
    
    # Save debug images if available
    if debug and result['debug_images']:
        debug_dir = output_file.parent / 'debug_output'
        debug_dir.mkdir(exist_ok=True)
        
        for filename, image_data in result['debug_images'].items():
            debug_path = debug_dir / filename
            with open(debug_path, 'wb') as f:
                f.write(image_data)
        
        print(f"✓ Saved {len(result['debug_images'])} debug images to: {debug_dir}")
    
    # Print statistics
    stats = result['statistics']
    print(f"\nStatistics:")
    print(f"  Text elements:       {stats['text_elements']}")
    print(f"  Logos:               {stats['logos']}")
    print(f"  Containers:          {stats['containers']}")
    print(f"  Images (containers): {stats['images_in_containers']}")
    print(f"  Images (standalone): {stats['standalone_images']}")
    print(f"  Shape elements:      {stats['shapes']}")
    print(f"  Dimensions:          {stats['dimensions'][0]}x{stats['dimensions'][1]}")
    
    return result


def convert_multiple_images(image_paths: list[str], output_dir: str, debug: bool = False):
    """
    Convert multiple images to SVG using Modal batch processing
    
    Args:
        image_paths: List of input image paths
        output_dir: Directory for output SVGs
        debug: Enable debug mode
    """
    # Prepare image files dictionary
    image_files = {}
    for path in image_paths:
        with open(path, 'rb') as f:
            image_files[Path(path).name] = f.read()
    
    # Get the Modal function
    batch_fn = modal.Function.lookup("raster-to-svg-converter", "convert_batch_images")
    
    print(f"Converting {len(image_files)} images using Modal batch processing...")
    
    # Run batch conversion on Modal
    results = batch_fn.remote(
        image_files=image_files,
        debug=debug,
        ocr_confidence=60,
        convert_images=False,
    )
    
    print(f"\n{'='*60}")
    print("BATCH CONVERSION COMPLETE")
    print(f"{'='*60}")
    print(f"Total files:     {results['total']}")
    print(f"Successful:      {results['successful']}")
    print(f"Failed:          {results['failed']}")
    
    if results['failed'] > 0:
        print("\nFailed files:")
        for detail in results['details']:
            if detail['status'] == 'failed':
                print(f"  - {detail['file']}: {detail['error']}")
    
    return results


if __name__ == '__main__':
    import sys
    
    # Example 1: Convert a single image
    if len(sys.argv) >= 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        debug = '--debug' in sys.argv
        
        result = convert_single_image(input_file, output_file, debug=debug)
        
    else:
        print("Usage:")
        print("  python example_usage.py <input_image> <output_svg> [--debug]")
        print("\nExample:")
        print("  python example_usage.py input.png output.svg")
        print("  python example_usage.py input.png output.svg --debug")
