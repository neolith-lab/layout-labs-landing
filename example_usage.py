"""
Example usage of the Raster to SVG Converter
"""

import cv2
from raster_to_svg import RasterToSVGConverter

def example_basic_usage():
    """Basic usage example"""
    print("=" * 60)
    print("EXAMPLE 1: Basic Usage")
    print("=" * 60)
    
    # Create converter
    converter = RasterToSVGConverter()
    
    # Convert a single image
    result = converter.convert(
        input_path='input_infographic.png',
        output_path='output.svg'
    )
    
    print(f"\nConversion completed!")
    print(f"Output: {result['output_path']}")
    print(f"Text elements found: {result['statistics']['text_elements']}")
    print(f"Images found: {result['statistics']['image_elements']}")
    print(f"Shapes found: {result['statistics']['shape_elements']}")


def example_batch_conversion():
    """Batch conversion example"""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Batch Conversion")
    print("=" * 60)
    
    converter = RasterToSVGConverter()
    
    # Convert all PNG files in a directory
    results = converter.convert_batch(
        input_dir='./input_images',
        output_dir='./output_svgs',
        pattern='*.png'
    )
    
    print(f"\nBatch conversion completed!")
    print(f"Total files: {results['total']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")


def example_with_custom_config():
    """Example with custom configuration"""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Custom Configuration")
    print("=" * 60)
    
    # Modify configuration
    from config import OCR_CONFIG, SHAPE_DETECTION, DEBUG
    
    # Enable debug mode
    DEBUG['save_intermediate_steps'] = True
    DEBUG['output_dir'] = './debug_custom'
    
    # Adjust OCR settings
    OCR_CONFIG['min_confidence'] = 70
    
    # Adjust shape detection sensitivity
    SHAPE_DETECTION['min_area'] = 200
    
    # Create converter
    converter = RasterToSVGConverter()
    
    # Convert
    result = converter.convert(
        input_path='complex_infographic.png',
        output_path='output_custom.svg'
    )
    
    print(f"\nConversion with custom settings completed!")
    print(f"Check debug output in: {DEBUG['output_dir']}")


def example_programmatic_access():
    """Example of programmatic access to extracted elements"""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Programmatic Access to Elements")
    print("=" * 60)
    
    converter = RasterToSVGConverter()
    
    result = converter.convert(
        input_path='sample_infographic.png',
        output_path='output_programmatic.svg'
    )
    
    # Access extracted elements
    elements = result['elements']
    
    print("\n--- Text Elements ---")
    for i, text in enumerate(elements.get('text', []), 1):
        print(f"{i}. '{text.text}' at ({text.bbox.x}, {text.bbox.y})")
        print(f"   Font: {text.font_family}, Size: {text.font_size}px")
        print(f"   Color: {text.color}")
    
    print("\n--- Image Elements ---")
    for i, img in enumerate(elements.get('images', []), 1):
        print(f"{i}. Image at ({img.bbox.x}, {img.bbox.y})")
        print(f"   Size: {img.bbox.w}x{img.bbox.h}")
        print(f"   Type: {'Photo' if img.is_photo else 'Graphic'}")
    
    print("\n--- Shape Elements ---")
    for i, shape in enumerate(elements.get('shapes', []), 1):
        print(f"{i}. {shape.shape_type.value} at ({shape.bbox.x}, {shape.bbox.y})")
        print(f"   Fill: {shape.fill_color}, Stroke: {shape.stroke_color}")


def create_sample_infographic():
    """Create a sample infographic for testing"""
    print("\n" + "=" * 60)
    print("CREATING SAMPLE INFOGRAPHIC")
    print("=" * 60)
    
    import numpy as np
    
    # Create a blank canvas
    width, height = 800, 600
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    
    # Add colored background
    canvas[:, :] = (240, 248, 255)  # Light blue
    
    # Add some shapes
    # Rectangle
    cv2.rectangle(canvas, (50, 50), (250, 150), (100, 100, 255), -1)
    cv2.rectangle(canvas, (50, 50), (250, 150), (0, 0, 0), 2)
    
    # Circle
    cv2.circle(canvas, (400, 100), 50, (100, 255, 100), -1)
    cv2.circle(canvas, (400, 100), 50, (0, 0, 0), 2)
    
    # Ellipse
    cv2.ellipse(canvas, (600, 100), (60, 40), 0, 0, 360, (255, 100, 100), -1)
    cv2.ellipse(canvas, (600, 100), (60, 40), 0, 0, 360, (0, 0, 0), 2)
    
    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(canvas, 'Sample Infographic', (200, 300), font, 2, (0, 0, 0), 3)
    cv2.putText(canvas, 'Convert to SVG!', (250, 400), font, 1.5, (50, 50, 50), 2)
    
    # Add some lines
    cv2.line(canvas, (100, 500), (700, 500), (0, 0, 0), 2)
    cv2.arrowedLine(canvas, (100, 450), (300, 450), (255, 0, 0), 3)
    
    # Save
    output_path = 'sample_infographic.png'
    cv2.imwrite(output_path, canvas)
    print(f"Sample infographic created: {output_path}")
    
    return output_path


if __name__ == '__main__':
    # Create a sample infographic
    sample_path = create_sample_infographic()
    
    print("\nNow converting the sample infographic...\n")
    
    # Run basic example with the sample
    converter = RasterToSVGConverter()
    result = converter.convert(
        input_path=sample_path,
        output_path='sample_output.svg'
    )
    
    print(f"\n{'='*60}")
    print("CONVERSION COMPLETE!")
    print(f"{'='*60}")
    print(f"Input: {sample_path}")
    print(f"Output: {result['output_path']}")
    print(f"\nStatistics:")
    for key, value in result['statistics'].items():
        print(f"  {key}: {value}")
    
    print("\n" + "="*60)
    print("To run other examples, uncomment them in the code.")
    print("="*60)
    
    # Uncomment to run other examples:
    # example_batch_conversion()
    # example_with_custom_config()
    # example_programmatic_access()
