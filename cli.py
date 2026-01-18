"""
CLI wrapper for easy command-line usage
"""

import sys
import argparse
from pathlib import Path
from raster_to_svg import RasterToSVGConverter
from config import DEBUG, OCR_CONFIG, SHAPE_DETECTION


def main():
    parser = argparse.ArgumentParser(
        description='Convert raster infographics to editable SVG',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert single image
  python cli.py input.png -o output.svg
  
  # Batch convert all PNGs in a folder
  python cli.py ./images -o ./output --batch
  
  # Enable debug mode
  python cli.py input.png -o output.svg --debug
  
  # Adjust OCR confidence threshold
  python cli.py input.png -o output.svg --ocr-confidence 70
  
  # Process JPG files in batch
  python cli.py ./images -o ./output --batch --pattern "*.jpg"
        """
    )
    
    # Required arguments
    parser.add_argument('input', 
                       help='Input image file or directory (for batch mode)')
    
    # Optional arguments
    parser.add_argument('-o', '--output',
                       help='Output SVG file or directory (for batch mode)')
    parser.add_argument('-b', '--batch', action='store_true',
                       help='Batch mode: process directory of images')
    parser.add_argument('--pattern', default='*.png',
                       help='File pattern for batch mode (default: *.png)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode (saves intermediate steps)')
    
    # Advanced options
    parser.add_argument('--ocr-confidence', type=int,
                       help='Minimum OCR confidence threshold (0-100)')
    parser.add_argument('--min-shape-area', type=int,
                       help='Minimum area for shape detection')
    parser.add_argument('--convert-images', action='store_true',
                       help='Convert embedded images to SVG (experimental)')
    parser.add_argument('--debug-dir', 
                       help='Directory for debug output')
    
    args = parser.parse_args()
    
    # Apply configuration
    if args.debug:
        DEBUG['save_intermediate_steps'] = True
        if args.debug_dir:
            DEBUG['output_dir'] = args.debug_dir
    
    if args.verbose:
        DEBUG['verbose'] = True
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.ocr_confidence:
        OCR_CONFIG['min_confidence'] = args.ocr_confidence
    
    if args.min_shape_area:
        SHAPE_DETECTION['min_area'] = args.min_shape_area
    
    # Create converter
    converter = RasterToSVGConverter()
    
    try:
        if args.batch:
            # Batch mode
            output_dir = args.output or 'output_svg'
            print(f"Converting images from '{args.input}' to '{output_dir}'...")
            
            results = converter.convert_batch(args.input, output_dir, args.pattern)
            
            print(f"\n{'='*60}")
            print("BATCH CONVERSION COMPLETE")
            print(f"{'='*60}")
            print(f"Total files:     {results['total']}")
            print(f"Successful:      {results['successful']}")
            print(f"Failed:          {results['failed']}")
            print(f"Output directory: {output_dir}")
            
            if results['failed'] > 0:
                print("\nFailed files:")
                for detail in results['details']:
                    if detail['status'] == 'failed':
                        print(f"  - {detail['file']}: {detail['error']}")
            
            return 0 if results['failed'] == 0 else 1
            
        else:
            # Single file mode
            output_path = args.output or 'output.svg'
            print(f"Converting '{args.input}' to '{output_path}'...")
            
            result = converter.convert(args.input, output_path,
                                     convert_images_to_svg=args.convert_images)
            
            print(f"\n{'='*60}")
            print("CONVERSION COMPLETE")
            print(f"{'='*60}")
            print(f"Output file:     {result['output_path']}")
            print(f"\nStatistics:")
            print(f"  Text elements:  {result['statistics']['text_elements']}")
            print(f"  Image elements: {result['statistics']['image_elements']}")
            print(f"  Shape elements: {result['statistics']['shape_elements']}")
            print(f"  Dimensions:     {result['statistics']['dimensions'][0]}x{result['statistics']['dimensions'][1]}")
            
            if DEBUG.get('save_intermediate_steps', False):
                print(f"\nDebug output:    {DEBUG.get('output_dir', './debug_output')}")
            
            return 0
            
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: An unexpected error occurred - {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
