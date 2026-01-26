#!/usr/bin/env python3
"""
CLI for ML-powered Infographic Layerizer

Usage:
    python -m ml_pipeline.cli input.png -o output.svg
    python -m ml_pipeline.cli input.png -o output.psd --format psd
    python -m ml_pipeline.cli input.png --quality  # Use high-quality models
    python -m ml_pipeline.cli input.png --fast     # Use faster models
"""

import argparse
import logging
import sys
from pathlib import Path

from .config import get_default_config, get_fast_config, get_quality_config
from .pipeline import InfographicLayerizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Convert raster infographics to layered, editable formats',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion to SVG
  python -m ml_pipeline.cli infographic.png -o output.svg
  
  # High-quality conversion (slower, better results)
  python -m ml_pipeline.cli infographic.png -o output.svg --quality
  
  # Fast conversion (lower quality, faster)
  python -m ml_pipeline.cli infographic.png -o output.svg --fast
  
  # Export to PSD
  python -m ml_pipeline.cli infographic.png -o output.psd --format psd
  
  # Export Figma-compatible JSON
  python -m ml_pipeline.cli infographic.png -o output.json --format json
  
  # Batch processing
  python -m ml_pipeline.cli ./images/*.png -o ./output/ --batch

Supported output formats:
  svg   - Layered SVG (default, best for Figma import)
  psd   - Adobe Photoshop layered file
  json  - JSON data for Figma plugin import
        """
    )
    
    # Input/Output
    parser.add_argument('input', 
                       help='Input image file')
    parser.add_argument('-o', '--output',
                       help='Output file path')
    parser.add_argument('-f', '--format', 
                       choices=['svg', 'psd', 'json', 'figma'],
                       default='svg',
                       help='Output format (default: svg)')
    
    # Quality presets
    quality_group = parser.add_mutually_exclusive_group()
    quality_group.add_argument('--fast', action='store_true',
                              help='Use faster, smaller models')
    quality_group.add_argument('--quality', action='store_true',
                              help='Use highest quality models (slower)')
    
    # Model options
    parser.add_argument('--sam-model', 
                       choices=['vit_h', 'vit_l', 'vit_b'],
                       help='SAM model size (default: vit_h)')
    parser.add_argument('--device',
                       choices=['auto', 'cuda', 'mps', 'cpu'],
                       default='auto',
                       help='Device to run models on')
    
    # Processing options
    parser.add_argument('--max-size', type=int, default=2048,
                       help='Maximum image dimension (default: 2048)')
    parser.add_argument('--min-element', type=int, default=20,
                       help='Minimum element size in pixels (default: 20)')
    
    # Output options
    parser.add_argument('--no-debug', action='store_true',
                       help='Disable debug visualizations (debug is ON by default)')
    parser.add_argument('--debug-dir', default='./debug_output',
                       help='Directory for debug output')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Select config
    if args.fast:
        config = get_fast_config()
        logger.info("Using fast configuration")
    elif args.quality:
        config = get_quality_config()
        logger.info("Using high-quality configuration")
    else:
        config = get_default_config()
    
    # Apply CLI overrides
    if args.sam_model:
        config.sam.model_type = args.sam_model
    if args.device:
        config.sam.device = args.device
        config.clip.device = args.device
        config.lama.device = args.device
    
    config.max_image_size = args.max_size
    config.min_element_size = args.min_element
    config.output.save_debug = not args.no_debug  # Debug is ON by default
    config.output.debug_dir = args.debug_dir
    
    # Determine output path
    input_path = Path(args.input)
    if args.output:
        output_path = args.output
    else:
        ext = '.svg' if args.format == 'svg' else f'.{args.format}'
        output_path = str(input_path.with_suffix(ext))
    
    # Process
    try:
        print(f"\n{'='*60}")
        print("ML-POWERED INFOGRAPHIC LAYERIZER")
        print(f"{'='*60}")
        print(f"Input:  {args.input}")
        print(f"Output: {output_path}")
        print(f"Format: {args.format}")
        print(f"{'='*60}\n")
        
        pipeline = InfographicLayerizer(config)
        result = pipeline.process(
            str(input_path),
            output_path,
            args.format
        )
        
        print(f"\n{'='*60}")
        print("CONVERSION COMPLETE")
        print(f"{'='*60}")
        print(f"Output:          {output_path}")
        print(f"Layers:          {len(result.layers)}")
        print(f"Text elements:   {len(result.text_elements)}")
        print(f"Processing time: {result.processing_time:.2f}s")
        
        # Category breakdown
        categories = {}
        for layer in result.layers:
            categories[layer.category] = categories.get(layer.category, 0) + 1
        
        print(f"\nLayer breakdown:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")
        
        if not args.no_debug:
            print(f"\nDebug output: {args.debug_dir}")
        
        print(f"{'='*60}\n")
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
