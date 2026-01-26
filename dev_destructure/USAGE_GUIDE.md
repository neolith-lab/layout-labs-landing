# Raster to SVG Infographic Converter

## Project Structure

```
layout-labs-landing/
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
├── config.py                # Configuration settings
├── utils.py                 # Utility functions and classes
├── text_extractor.py        # Step 1: Text OCR
├── background_filler.py     # Steps 2, 4, 7: Background filling
├── image_detector.py        # Steps 3-5: Image detection
├── shape_detector.py        # Steps 6-8: Shape detection
├── svg_generator.py         # Steps 9-11: SVG generation
├── raster_to_svg.py         # Main converter orchestrator
├── example_usage.py         # Usage examples
└── test_converter.py        # Unit tests
```

## Installation & Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Tesseract OCR

**macOS:**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

## Quick Start

### Basic Usage

```python
from raster_to_svg import RasterToSVGConverter

# Create converter
converter = RasterToSVGConverter()

# Convert image to SVG
result = converter.convert('input.png', 'output.svg')

print(f"Converted! Found {result['statistics']['text_elements']} text elements")
```

### Command Line Usage

```bash
# Single file
python raster_to_svg.py input.png -o output.svg

# Batch conversion
python raster_to_svg.py ./images -o ./output_svgs --batch

# With verbose output
python raster_to_svg.py input.png -o output.svg -v
```

### Run Example

```bash
python example_usage.py
```

This will create a sample infographic and convert it to SVG.

## Pipeline Overview

The converter follows an 11-step methodology:

1. **Text OCR** - Extract text with font identification and bounding boxes
2. **Text Removal** - Remove text and fill background
3. **Image Detection** - Identify embedded images
4. **Image Removal** - Remove images and fill background
5. **Image to SVG** - Optional vectorization of images
6. **Shape Detection** - Identify geometric shapes (circles, rectangles, polygons, etc.)
7. **Shape Removal** - Remove shapes and fill background
8. **Shape Reconstruction** - Convert shapes to structured SVG elements
9. **Background to SVG** - Convert background to SVG
10. **Layer Composition** - Arrange elements in layers
11. **Final SVG Output** - Generate complete editable SVG

## Configuration

Edit `config.py` to customize:

- OCR settings (confidence thresholds, languages)
- Image processing parameters (inpainting method, blur kernel)
- Shape detection sensitivity
- SVG output preferences
- Debug options

Example:

```python
from config import DEBUG, OCR_CONFIG

# Enable debug output
DEBUG['save_intermediate_steps'] = True
DEBUG['output_dir'] = './my_debug'

# Adjust OCR confidence
OCR_CONFIG['min_confidence'] = 70
```

## Features

### Text Extraction
- Tesseract and EasyOCR support
- Font size estimation
- Font weight detection (bold/normal)
- Color extraction
- Bounding box detection

### Image Detection
- Color variance analysis
- Edge density detection
- Texture analysis
- Photo vs. graphic classification
- Dominant color extraction

### Shape Detection
- Circles, ellipses
- Rectangles (regular and rotated)
- Polygons
- Lines and arrows
- Fill and stroke color extraction

### Background Filling
- Telea and Navier-Stokes inpainting
- Boundary smoothing
- Context-aware filling

### SVG Generation
- Layered output (background, shapes, images, text)
- Preserves colors and styles
- Editable in vector graphics software
- Embedded images as base64

## Advanced Usage

### Batch Processing

```python
converter = RasterToSVGConverter()

results = converter.convert_batch(
    input_dir='./infographics',
    output_dir='./svg_output',
    pattern='*.png'
)

print(f"Converted {results['successful']}/{results['total']} files")
```

### Programmatic Element Access

```python
result = converter.convert('input.png', 'output.svg')

# Access extracted elements
for text in result['elements']['text']:
    print(f"Text: '{text.text}' at position ({text.bbox.x}, {text.bbox.y})")
    print(f"  Font: {text.font_family}, Size: {text.font_size}px")

for shape in result['elements']['shapes']:
    print(f"Shape: {shape.shape_type.value}")
    print(f"  Fill: {shape.fill_color}, Stroke: {shape.stroke_color}")
```

## Testing

Run unit tests:

```bash
python test_converter.py
```

## Debug Mode

Enable debug mode to save intermediate steps:

```python
from config import DEBUG

DEBUG['save_intermediate_steps'] = True
DEBUG['output_dir'] = './debug_output'
```

This will save:
- `01_text_detection.png` - Detected text with bounding boxes
- `02_text_removed.png` - Image after text removal
- `03_image_detection.png` - Detected images
- `04_images_removed.png` - Image after image removal
- `06_shape_detection.png` - Detected shapes
- `07_shapes_removed_background.png` - Clean background

## Limitations

- Font identification is approximate (requires font database for exact matching)
- Complex overlapping elements may not separate perfectly
- Image-to-SVG conversion is experimental
- Handwritten text may not be recognized accurately
- Very small or low-contrast elements may be missed

## Dependencies

Core libraries:
- OpenCV - Image processing
- NumPy - Numerical operations
- Tesseract/EasyOCR - Text recognition
- svgwrite - SVG generation
- Pillow - Image handling
- scikit-image - Advanced image processing
- Shapely - Geometric operations

## Performance Tips

1. For large batches, process in parallel
2. Adjust detection thresholds based on your images
3. Disable debug mode for faster processing
4. Use lower OCR confidence for noisy images
5. Preprocess images (denoise, enhance contrast) for better results

## License

MIT License - See LICENSE file

## Contributing

Contributions welcome! Areas for improvement:
- Better font identification using ML
- Enhanced shape classification
- Improved text baseline detection
- Support for more shape types
- Better handling of overlapping elements

## Support

For issues and questions, please check the documentation or open an issue on GitHub.
