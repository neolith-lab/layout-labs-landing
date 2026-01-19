#!/usr/bin/env python3
"""Test text-as-image rendering"""

from svg_generator import SVGGenerator
import traceback

# Create a simple test
gen = SVGGenerator()

# Test rendering text as image
try:
    print("Testing text rendering...")
    text_img = gen._render_text_as_image('Hello World', 'Roboto', 24, (0, 0, 0), False)
    if text_img is not None:
        print(f'Text rendered as image: shape={text_img.shape}')
    else:
        print('Text rendering returned None - font may not be available')
except Exception as e:
    print(f'Error: {e}')
    traceback.print_exc()

print('Test complete!')
