#!/usr/bin/env python3
"""
Test script for Excalidraw conversion
Creates a simple test case to verify the conversion works
"""

import json
from excalidraw_converter import ExcalidrawConverter


def create_test_extraction_data():
    """Create sample extraction data for testing"""
    return {
        'containers': [
            {
                'bbox': [50, 50, 400, 300],
                'background_color': '#f8f9fa',
                'border_color': '#dee2e6',
            }
        ],
        'text_elements': [
            {
                'text': 'Test Infographic Title',
                'bbox': [100, 100, 300, 40],
                'font_size': 32,
                'color': '#212529',
                'font_family': 'virgil',
                'text_align': 'center',
            },
            {
                'text': 'This is a sample text element\nwith multiple lines\nfor testing purposes.',
                'bbox': [100, 160, 300, 60],
                'font_size': 16,
                'color': '#495057',
            }
        ],
        'shapes': [
            {
                'bbox': [500, 100, 150, 150],
                'type': 'circle',
                'stroke_color': '#2f9e44',
                'fill_color': '#b2f2bb',
                'fill_style': 'hachure',
                'stroke_width': 3,
            }
        ],
        'images': [],  # Empty for testing without images
        'logos': [],
    }


def create_test_statistics():
    """Create sample statistics"""
    return {
        'text_elements': 2,
        'logos': 0,
        'containers': 1,
        'images_in_containers': 0,
        'standalone_images': 0,
        'shapes': 1,
        'dimensions': [800, 600],
    }


def main():
    print("="*60)
    print("EXCALIDRAW CONVERTER TEST")
    print("="*60)
    print()
    
    # Create test data
    print("Creating test extraction data...")
    extraction_data = create_test_extraction_data()
    statistics = create_test_statistics()
    
    # Create converter
    print("Initializing ExcalidrawConverter...")
    converter = ExcalidrawConverter()
    
    # Convert without downloading images (since we have none)
    print("\nConverting to Excalidraw format...")
    excalidraw_json = converter.convert(
        extraction_data=extraction_data,
        statistics=statistics,
        download_images=False  # No images to download
    )
    
    # Save to file
    output_file = 'test_output.excalidraw'
    print(f"\nSaving to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(excalidraw_json, f, indent=2)
    
    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")
    print(f"\n✓ Generated: {output_file}")
    print(f"✓ Elements: {len(excalidraw_json['elements'])}")
    print(f"✓ Files: {len(excalidraw_json['files'])}")
    
    print("\nElement breakdown:")
    element_types = {}
    for elem in excalidraw_json['elements']:
        elem_type = elem['type']
        element_types[elem_type] = element_types.get(elem_type, 0) + 1
    
    for elem_type, count in element_types.items():
        print(f"  - {elem_type}: {count}")
    
    print("\nNext steps:")
    print("  1. Open your Excalidraw editor")
    print("  2. Click 'Load JSON'")
    print(f"  3. Select: {output_file}")
    print("  4. Verify elements appear correctly")
    
    print("\n✓ Test successful!")


if __name__ == '__main__':
    main()
