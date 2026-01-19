"""
Test script to verify image detection with container filtering
"""

from raster_to_svg import RasterToSVGConverter
from config import DEBUG
import sys

# Enable debug mode
DEBUG['save_intermediate_steps'] = True
DEBUG['verbose'] = True

def test_conversion(input_file):
    """Test the conversion with container filtering"""
    print(f"\n{'='*60}")
    print(f"Testing Image Detection with Container Filtering")
    print(f"{'='*60}\n")
    
    converter = RasterToSVGConverter()
    
    try:
        result = converter.convert(input_file, 'output_test.svg')
        
        print(f"\n{'='*60}")
        print("CONVERSION SUCCESSFUL")
        print(f"{'='*60}")
        print(f"\nStatistics:")
        print(f"  Text elements:       {result['statistics']['text_elements']}")
        print(f"  Containers:          {result['statistics']['containers']}")
        print(f"  Images (containers): {result['statistics']['images_in_containers']}")
        print(f"  Images (standalone): {result['statistics']['standalone_images']}")
        print(f"  Shapes:              {result['statistics']['shapes']}")
        
        print(f"\n{'='*60}")
        print("Debug images saved:")
        print(f"{'='*60}")
        print(f"  01_text_removed_infilled.png   - Text removed and infilled")
        print(f"  03_image_detection.png         - RED=kept images, GREEN=filtered containers")
        print(f"  04_images_removed_infilled.png - Images removed and infilled")
        print(f"  02_container_detection.png     - Detected containers")
        print(f"  background_clean.png           - Final background")
        
        return 0
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_image_filtering.py <input_image>")
        print("\nExample:")
        print("  python test_image_filtering.py input.png")
        sys.exit(1)
    
    input_file = sys.argv[1]
    sys.exit(test_conversion(input_file))
