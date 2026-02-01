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
  
  # Upload extracted elements to S3
  python cli.py input.png -o output.svg --debug --s3-bucket my-bucket
  
  # Upload to S3 with custom prefix
  python cli.py input.png -o output.svg --debug --s3-bucket my-bucket --s3-prefix my-project/v1
  
  # Generate Excalidraw JSON (with embedded images)
  python cli.py input.png -o output.excalidraw --excalidraw
  
  # Generate Excalidraw JSON from S3 extraction (no image download)
  python cli.py input.png --s3-bucket my-bucket --excalidraw --no-download-images
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
    
    # S3 Storage options
    parser.add_argument('--s3-bucket',
                       help='S3 bucket name for storing extracted elements')
    parser.add_argument('--s3-prefix',
                       help='S3 prefix/folder for organizing uploads (default: auto-generated)')
    
    # Excalidraw export options
    parser.add_argument('--excalidraw', action='store_true',
                       help='Generate Excalidraw JSON format instead of SVG')
    parser.add_argument('--no-download-images', action='store_true',
                       help='Skip downloading images when generating Excalidraw JSON (faster, but no images in output)')
    
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
    
    # Create converter with S3 support if configured
    try:
        converter = RasterToSVGConverter(
            s3_bucket=args.s3_bucket,
            s3_prefix=args.s3_prefix
        )
    except (ValueError, ImportError, RuntimeError) as e:
        print(f"\n{'='*60}")
        print("ERROR: S3 Configuration Failed")
        print(f"{'='*60}")
        print(f"{e}")
        print(f"{'='*60}\n")
        return 1
    
    # Print S3 configuration if enabled
    if args.s3_bucket:
        print(f"S3 Storage enabled: s3://{args.s3_bucket}/{converter.s3_prefix}")
        print()
    
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
            
            if DEBUG.get('save_intermediate_steps', False) and args.s3_bucket:
                print(f"\nS3 uploads:      s3://{args.s3_bucket}/{converter.s3_prefix}/")
                print(f"                 Extracted elements uploaded for each image")
            
            if results['failed'] > 0:
                print("\nFailed files:")
                for detail in results['details']:
                    if detail['status'] == 'failed':
                        print(f"  - {detail['file']}: {detail['error']}")
            
            return 0 if results['failed'] == 0 else 1
            
        else:
            # Single file mode
            output_path = args.output or ('output.excalidraw' if args.excalidraw else 'output.svg')
            print(f"Converting '{args.input}' to '{output_path}'...")
            
            result = converter.convert(args.input, output_path,
                                     convert_images_to_svg=args.convert_images)
            
            # Generate Excalidraw JSON if requested
            if args.excalidraw:
                from excalidraw_converter import ExcalidrawConverter
                
                print(f"\n{'='*60}")
                print("GENERATING EXCALIDRAW JSON")
                print(f"{'='*60}\n")
                
                excalidraw_converter = ExcalidrawConverter()
                
                # Determine if we should download images
                download_images = not args.no_download_images
                
                if args.no_download_images:
                    print("Note: Skipping image downloads (--no-download-images enabled)")
                    print("      Images will not be embedded in the Excalidraw file\n")
                
                # Use 'elements' from result (contains text, images, containers, etc.)
                excalidraw_path = excalidraw_converter.convert_to_file(
                    extraction_data=result['elements'],
                    statistics=result['statistics'],
                    output_path=output_path,
                    download_images=download_images
                )
                
                print(f"\n{'='*60}")
                print("EXCALIDRAW CONVERSION COMPLETE")
                print(f"{'='*60}")
                print(f"Excalidraw file: {excalidraw_path}")
                print(f"\nYou can now:")
                print(f"  1. Open this file in your Excalidraw editor")
                print(f"  2. Click 'Load JSON' button")
                print(f"  3. Select: {excalidraw_path}")
                
                if download_images:
                    print(f"\n✓ Images are embedded as base64 in the file")
                else:
                    print(f"\n⚠ Images were NOT embedded (use without --no-download-images to embed)")
                
                return 0
            
            print(f"\n{'='*60}")
            print("CONVERSION COMPLETE")
            print(f"{'='*60}")
            print(f"Output file:     {result['output_path']}")
            print(f"\nStatistics:")
            print(f"  Text elements:       {result['statistics']['text_elements']}")
            print(f"  Logos:               {result['statistics']['logos']}")
            print(f"  Containers:          {result['statistics']['containers']}")
            print(f"  Images (containers): {result['statistics']['images_in_containers']}")
            print(f"  Images (standalone): {result['statistics']['standalone_images']}")
            print(f"  Shape elements:      {result['statistics']['shapes']}")
            print(f"  Dimensions:          {result['statistics']['dimensions'][0]}x{result['statistics']['dimensions'][1]}")
            
            if DEBUG.get('save_intermediate_steps', False):
                print(f"\nDebug output:    {DEBUG.get('output_dir', './debug_output')}")
                
                # Show S3 information if available
                if args.s3_bucket:
                    print(f"S3 uploads:      s3://{args.s3_bucket}/{converter.s3_prefix}/")
                    print(f"                 Check combined_extraction_data.json for all S3 URLs")
            
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
