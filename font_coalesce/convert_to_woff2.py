"""
Convert all TTF fonts to WOFF2 format
Uses fonttools for high-quality conversion
"""

import os
from fontTools.ttLib import TTFont
from pathlib import Path

# Configuration
INPUT_DIR = "google_fonts"
OUTPUT_DIR = "google_fonts_woff2"

def convert_ttf_to_woff2(input_path, output_path):
    """
    Convert a TTF font to WOFF2 format
    """
    try:
        # Load the font
        font = TTFont(input_path)
        
        # Save as WOFF2
        # The flavor parameter tells fonttools to output WOFF2
        font.flavor = 'woff2'
        font.save(output_path)
        font.close()
        
        return True
    except Exception as e:
        print(f"Error converting {input_path}: {e}")
        return False

def main():
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Get all TTF files
    input_dir_path = Path(INPUT_DIR)
    ttf_files = list(input_dir_path.glob("*.ttf"))
    
    if not ttf_files:
        print(f"No TTF files found in {INPUT_DIR}/")
        return
    
    print(f"Found {len(ttf_files)} TTF files to convert\n")
    
    converted = 0
    failed = 0
    
    for ttf_file in sorted(ttf_files):
        # Generate output filename
        output_filename = ttf_file.stem + ".woff2"
        output_path = Path(OUTPUT_DIR) / output_filename
        
        print(f"Converting: {ttf_file.name} → {output_filename}...", end=" ")
        
        success = convert_ttf_to_woff2(str(ttf_file), str(output_path))
        
        if success:
            # Get file sizes for comparison
            input_size = ttf_file.stat().st_size / 1024  # KB
            output_size = output_path.stat().st_size / 1024  # KB
            compression = ((input_size - output_size) / input_size) * 100
            
            print(f"✓ ({input_size:.1f}KB → {output_size:.1f}KB, {compression:.1f}% smaller)")
            converted += 1
        else:
            print("✗ FAILED")
            failed += 1
    
    # Summary
    print(f"\n{'='*60}")
    print("CONVERSION COMPLETE")
    print(f"{'='*60}")
    print(f"✓ Converted: {converted} fonts")
    if failed > 0:
        print(f"✗ Failed: {failed} fonts")
    print(f"Output directory: {OUTPUT_DIR}/")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
