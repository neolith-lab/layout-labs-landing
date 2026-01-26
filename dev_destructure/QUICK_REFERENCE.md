# Quick Reference Guide

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Tesseract OCR
brew install tesseract  # macOS
# or
sudo apt-get install tesseract-ocr  # Linux

# Run setup
python setup.py
```

## Quick Start

### Python API

```python
from raster_to_svg import RasterToSVGConverter

# Basic conversion
converter = RasterToSVGConverter()
result = converter.convert('input.png', 'output.svg')

# Batch conversion
results = converter.convert_batch('./images', './output')
```

### Command Line

```bash
# Single file
python cli.py input.png -o output.svg

# Batch mode
python cli.py ./images --batch -o ./output

# With debug
python cli.py input.png -o output.svg --debug

# Custom settings
python cli.py input.png -o output.svg --ocr-confidence 70
```

## Configuration Quick Tweaks

```python
from config import DEBUG, OCR_CONFIG, SHAPE_DETECTION

# Enable debug mode
DEBUG['save_intermediate_steps'] = True
DEBUG['output_dir'] = './my_debug'

# Adjust OCR
OCR_CONFIG['min_confidence'] = 70
OCR_CONFIG['use_easyocr'] = True

# Adjust shape detection
SHAPE_DETECTION['min_area'] = 200
SHAPE_DETECTION['epsilon_factor'] = 0.03
```

## Common Tasks

### Get Element Statistics

```python
result = converter.convert('input.png', 'output.svg')
stats = result['statistics']

print(f"Text elements: {stats['text_elements']}")
print(f"Images: {stats['image_elements']}")
print(f"Shapes: {stats['shape_elements']}")
```

### Access Detected Elements

```python
result = converter.convert('input.png', 'output.svg')

# Text elements
for text in result['elements']['text']:
    print(f"{text.text} at ({text.bbox.x}, {text.bbox.y})")

# Shapes
for shape in result['elements']['shapes']:
    print(f"{shape.shape_type.value}: {shape.fill_color}")

# Images
for img in result['elements']['images']:
    print(f"Image: {img.bbox.w}x{img.bbox.h} pixels")
```

### Process Multiple Files

```python
import glob
from pathlib import Path

converter = RasterToSVGConverter()

for img_path in glob.glob('./images/*.png'):
    output = f'./output/{Path(img_path).stem}.svg'
    converter.convert(img_path, output)
```

## Module Reference

| Module | Purpose |
|--------|---------|
| `raster_to_svg.py` | Main orchestrator |
| `text_extractor.py` | Text OCR |
| `image_detector.py` | Image detection |
| `shape_detector.py` | Shape detection |
| `background_filler.py` | Background filling |
| `svg_generator.py` | SVG generation |
| `utils.py` | Utilities |
| `config.py` | Configuration |

## Import Patterns

```python
# Main converter
from raster_to_svg import RasterToSVGConverter

# Individual modules
from text_extractor import TextExtractor
from image_detector import ImageDetector
from shape_detector import ShapeDetector
from background_filler import BackgroundFiller
from svg_generator import SVGGenerator

# Utilities
from utils import BoundingBox, rgb_to_hex, calculate_iou

# Config
from config import DEBUG, OCR_CONFIG, SHAPE_DETECTION
```

## Troubleshooting

### Tesseract Not Found

```python
# Set Tesseract path manually
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'
```

### Low Text Detection

```python
# Lower confidence threshold
OCR_CONFIG['min_confidence'] = 50

# Enable EasyOCR
OCR_CONFIG['use_easyocr'] = True
```

### Missing Small Shapes

```python
# Reduce minimum area
SHAPE_DETECTION['min_area'] = 50
```

### Poor Background Filling

```python
# Increase inpainting radius
IMAGE_PROCESSING['inpaint_radius'] = 10

# Try different method
IMAGE_PROCESSING['background_fill_method'] = 'inpaint_ns'
```

## File Outputs

### Standard Output
- `output.svg` - Final SVG file

### Debug Output (when enabled)
- `01_text_detection.png`
- `02_text_removed.png`
- `03_image_detection.png`
- `04_images_removed.png`
- `06_shape_detection.png`
- `07_shapes_removed_background.png`

## Supported Input Formats

- PNG
- JPG/JPEG
- BMP
- TIFF
- (Most formats supported by OpenCV)

## SVG Layer Structure

```xml
<svg>
  <g id="layer_background">...</g>
  <g id="layer_shapes">...</g>
  <g id="layer_images">...</g>
  <g id="layer_text">...</g>
</svg>
```

## Performance Tips

1. **Disable debug mode** for faster processing
2. **Adjust thresholds** based on your images
3. **Use batch mode** for multiple files
4. **Preprocess images** (denoise, enhance) beforehand
5. **Lower OCR confidence** for noisy images

## Examples Location

- `example_usage.py` - Comprehensive examples
- `test_converter.py` - Test cases showing usage

## Documentation Files

- `README.md` - Main documentation
- `USAGE_GUIDE.md` - Detailed guide
- `API_REFERENCE.md` - API docs
- `PROJECT_SUMMARY.md` - Technical overview
- `QUICK_REFERENCE.md` - This file

## Getting Help

```python
# Check configuration
from config import *
print(OCR_CONFIG)
print(SHAPE_DETECTION)

# Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Save debug images
DEBUG['save_intermediate_steps'] = True
```

## Version Check

```python
import cv2
import numpy as np

print(f"OpenCV: {cv2.__version__}")
print(f"NumPy: {np.__version__}")
```
