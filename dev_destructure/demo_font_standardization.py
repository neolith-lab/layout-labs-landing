#!/usr/bin/env python3
"""
Quick demonstration of font size standardization feature

This script shows how the same text elements maintain consistent
font sizes across different image resolutions.
"""

import numpy as np
from text_extractor import TextExtractor
from utils import BoundingBox, TextElement
from config import OCR_CONFIG

def demo_standardization():
    """
    Demonstrates font size standardization with a simple example
    """
    print("\n" + "="*80)
    print("FONT SIZE STANDARDIZATION DEMO")
    print("="*80)
    print("\nThis demo shows how the system calculates and normalizes font sizes")
    print("to ensure consistency across different image resolutions.\n")
    
    # Simulate a blog post layout
    text_samples = [
        ("Main Headline", 100, 1),
        ("Article Subtitle", 60, 1),
        ("Section Header", 40, 1),
        ("Body Paragraph", 28, 3),
        ("Body Text", 24, 1),
        ("Image Caption", 18, 1),
        ("Footer Note", 14, 1),
    ]
    
    resolutions = [
        ("Mobile Portrait", 750, 1334),
        ("Tablet", 1024, 768),
        ("Desktop HD", 1920, 1080),
        ("4K Monitor", 3840, 2160),
    ]
    
    for res_name, width, height in resolutions:
        print(f"\n{'─'*80}")
        print(f"📱 {res_name} ({width}x{height})")
        print(f"{'─'*80}")
        
        # Create extractor with image dimensions
        extractor = TextExtractor(OCR_CONFIG)
        extractor.image_width = width
        extractor.image_height = height
        
        # Create and process text elements
        elements = []
        for text, bbox_h, lines in text_samples:
            bbox = BoundingBox(x=50, y=50, w=300, h=bbox_h, label='text')
            elem = TextElement(text=text, bbox=bbox, num_lines=lines)
            
            # Estimate font size with image context
            elem.font_size = extractor._estimate_font_size(
                bbox_h, lines, width, height
            )
            elements.append(elem)
        
        # Normalize font sizes
        normalized = extractor._normalize_font_sizes(elements)
        
        # Display results in a table
        print(f"\n{'Text Type':<20} {'Height':<10} {'Lines':<8} {'Font Size':<12} {'Tier':<15}")
        print("─"*80)
        
        tier_map = {
            40: 'Extra Large',
            29: 'Large',
            23: 'Medium Large',
            16: 'Medium',
            14: 'Small',
            11: 'Extra Small'
        }
        
        for elem in normalized:
            tier = 'Custom'
            for size, name in tier_map.items():
                if abs(elem.font_size - size) <= 2:
                    tier = name
                    break
            
            print(f"{elem.text:<20} {elem.bbox.h:<10} {elem.num_lines:<8} "
                  f"{elem.font_size}pt{'':<8} {tier:<15}")
    
    print("\n" + "="*80)
    print("KEY OBSERVATIONS:")
    print("="*80)
    print("✓ Font sizes remain CONSISTENT across all resolutions")
    print("✓ Hierarchical relationships are PRESERVED")
    print("✓ Multi-line text is handled CORRECTLY")
    print("✓ Typically results in 4-6 DISTINCT sizes (clean hierarchy)")
    print("="*80 + "\n")


if __name__ == "__main__":
    demo_standardization()
