"""
Test script to demonstrate font size normalization
"""

import numpy as np
from text_extractor import TextElement
from utils import BoundingBox

def test_font_normalization():
    """Demonstrate the font size normalization feature"""
    
    print("=" * 80)
    print("Font Size Normalization Test")
    print("=" * 80)
    print()
    
    # Simulate different image sizes
    test_images = [
        ("Small Mobile", 480, 800),
        ("Large Mobile", 720, 1280),
        ("Tablet", 1024, 768),
        ("Desktop", 1920, 1080),
        ("4K", 3840, 2160),
    ]
    
    # Create sample text elements with various heights
    sample_texts = [
        ("Hero Heading", 80, 1),
        ("Section Title", 50, 1),
        ("Subheading", 35, 1),
        ("Body Text", 24, 1),
        ("Small Text", 18, 1),
        ("Caption", 14, 1),
        ("Multi-line Paragraph", 72, 3),
    ]
    
    from text_extractor import TextExtractor
    from config import OCR_CONFIG
    
    for img_name, width, height in test_images:
        print(f"\n{img_name} ({width}x{height})")
        print("-" * 80)
        
        # Create a dummy image
        dummy_image = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Create extractor
        extractor = TextExtractor(OCR_CONFIG)
        extractor.image_width = width
        extractor.image_height = height
        
        # Create text elements
        text_elements = []
        for text, bbox_height, num_lines in sample_texts:
            bbox = BoundingBox(x=10, y=10, w=200, h=bbox_height, label='text')
            element = TextElement(
                text=text,
                bbox=bbox,
                num_lines=num_lines
            )
            
            # Estimate font size
            element.font_size = extractor._estimate_font_size(
                bbox_height,
                num_lines,
                image_width=width,
                image_height=height
            )
            
            text_elements.append(element)
        
        # Normalize font sizes
        normalized_elements = extractor._normalize_font_sizes(text_elements)
        
        # Display results
        print(f"{'Text Type':<25} {'Raw Height':<12} {'Lines':<8} {'Estimated':<12} {'Normalized':<12}")
        print("-" * 80)
        
        for elem, (text, bbox_h, num_lines) in zip(normalized_elements, sample_texts):
            # Re-calculate estimated for display
            estimated = extractor._estimate_font_size(bbox_h, num_lines, width, height)
            print(f"{text:<25} {bbox_h:<12} {num_lines:<8} {estimated:<12} {elem.font_size:<12}")
        
        print()
    
    print("=" * 80)
    print("\nKey Features:")
    print("1. Font sizes are calculated relative to image dimensions")
    print("2. Sizes are normalized into consistent tiers (hero, heading, body, etc.)")
    print("3. Hierarchical relationships are preserved across different image sizes")
    print("4. Multi-line text is handled correctly")
    print("=" * 80)


if __name__ == "__main__":
    test_font_normalization()
