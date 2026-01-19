"""
Test script to verify font classifier integration with text extraction
"""

import cv2
import logging
from text_extractor import TextExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_font_classification(image_path: str):
    """Test font classification on an image"""
    print(f"\nTesting font classification on: {image_path}")
    print("="*100)
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to load image: {image_path}")
        return
    
    # Extract text with font classification
    extractor = TextExtractor()
    text_elements = extractor.extract_text_elements(image)
    
    # Print results
    print(f"\nFound {len(text_elements)} text elements:\n")
    print(f"{'Text':<40} {'Font':<30} {'Size':<8} {'Lines':<8} {'Confidence':<12}")
    print("="*100)
    
    for element in text_elements:
        text_preview = element.text.replace('\n', ' ')[:40]
        
        # Build font display
        if element.classified_font:
            font_display = f"{element.classified_font}"
            if element.classified_font_version:
                font_display += f" ({element.classified_font_version})"
            confidence_str = f"{element.font_classification_confidence:.3f}"
        else:
            font_display = f"{element.font_family} (fallback)"
            confidence_str = f"{element.confidence:.3f}"
        
        print(f"{text_preview:<40} {font_display:<30} {element.font_size}pt    {element.num_lines}        {confidence_str:<12}")
    
    print("="*100)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # Default test images
        image_path = "input.png"
    
    test_font_classification(image_path)
