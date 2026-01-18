# Raster to SVG Infographic Converter

A robust, production-ready pipeline for converting raster infographics to fully editable SVG format with intelligent element detection and reconstruction.

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 Overview

This comprehensive tool automatically converts raster infographics (PNG, JPG) into editable SVG files by:
- **Extracting text** with OCR and font identification
- **Detecting embedded images** and preserving them
- **Identifying shapes** (circles, rectangles, polygons, lines, arrows)
- **Reconstructing backgrounds** intelligently
- **Generating layered SVG** output for easy editing

## ✨ Features

### 🔤 Advanced Text Extraction
- Dual OCR engines (Tesseract + EasyOCR)
- Font size, weight, and style detection
- Accurate color extraction
- Bounding box identification
- Confidence scoring

### 🖼️ Intelligent Image Detection
- Multi-method detection (color variance, edge density, texture analysis)
- Photo vs. graphic classification
- Dominant color extraction
- Automatic background filling

### 🔷 Comprehensive Shape Detection
- **Circles & Ellipses**: Perfect circular detection
- **Rectangles**: Regular and rotated
- **Polygons**: Multi-sided shapes
- **Lines & Arrows**: Vector path detection
- Fill and stroke color extraction

### 🎨 Smart Background Filling
- Telea and Navier-Stokes inpainting
- Context-aware filling
- Boundary smoothing
- Progressive layer removal

### 📐 Layered SVG Output
- Organized layer structure (background → shapes → images → text)
- Preserves colors and styles
- Fully editable in Inkscape, Adobe Illustrator, Figma
- Embedded images as base64

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd layout-labs-landing

# Run setup
python setup.py
```

### System Requirements

- Python 3.7+
- Tesseract OCR ([installation guide](https://github.com/tesseract-ocr/tesseract))

**Install Tesseract:**
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

### Basic Usage

```python
from raster_to_svg import RasterToSVGConverter

# Create converter
converter = RasterToSVGConverter()

# Convert image
result = converter.convert('input.png', 'output.svg')

print(f"✓ Converted! Found:")
print(f"  - {result['statistics']['text_elements']} text elements")
print(f"  - {result['statistics']['image_elements']} images")
print(f"  - {result['statistics']['shape_elements']} shapes")
```

### Command Line Interface

```bash
# Convert single image
python cli.py input.png -o output.svg

# Batch convert directory
python cli.py ./images --batch -o ./output

# Enable debug mode
python cli.py input.png -o output.svg --debug

# Adjust settings
python cli.py input.png -o output.svg --ocr-confidence 70 --min-shape-area 200
```

## 📖 Documentation

- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** - Comprehensive usage guide
- **[API_REFERENCE.md](API_REFERENCE.md)** - Complete API documentation
- **[example_usage.py](example_usage.py)** - Working examples

## 🔧 Project Structure

```
layout-labs-landing/
├── README.md                 # This file
├── USAGE_GUIDE.md           # Detailed usage guide
├── API_REFERENCE.md         # API documentation
├── LICENSE                  # MIT License
├── requirements.txt         # Python dependencies
├── setup.py                 # Setup script
├── config.py               # Configuration settings
├── utils.py                # Utility functions
├── advanced_utils.py       # Advanced utilities
├── text_extractor.py       # Text OCR module
├── background_filler.py    # Background filling
├── image_detector.py       # Image detection
├── shape_detector.py       # Shape detection
├── svg_generator.py        # SVG generation
├── raster_to_svg.py        # Main converter
├── cli.py                  # Command-line interface
├── example_usage.py        # Usage examples
└── test_converter.py       # Unit tests
```

## 🎓 Pipeline Methodology

The converter implements an 11-step methodology:

1. **Text OCR** - Extract text with font identification
2. **Text Removal** - Remove text and fill background
3. **Image Detection** - Identify embedded images
4. **Image Removal** - Remove images and fill background
5. **Image to SVG** - Optional vectorization (experimental)
6. **Shape Detection** - Identify geometric shapes
7. **Shape Removal** - Remove shapes and fill background
8. **Shape Reconstruction** - Convert to SVG elements
9. **Background to SVG** - Vectorize background
10. **Layer Composition** - Arrange elements in layers
11. **Final SVG Output** - Generate complete SVG

## 🎨 Examples

### Create and Convert Sample

```bash
python example_usage.py
```

### Custom Configuration

```python
from config import DEBUG, OCR_CONFIG

# Enable debug mode
DEBUG['save_intermediate_steps'] = True

# Adjust OCR confidence
OCR_CONFIG['min_confidence'] = 70

# Convert
converter = RasterToSVGConverter()
result = converter.convert('input.png', 'output.svg')
```

### Programmatic Access

```python
result = converter.convert('input.png', 'output.svg')

# Access detected elements
for text in result['elements']['text']:
    print(f"Text: '{text.text}' at ({text.bbox.x}, {text.bbox.y})")
    print(f"  Font: {text.font_family}, Size: {text.font_size}px")
    print(f"  Color: {text.color}")

for shape in result['elements']['shapes']:
    print(f"Shape: {shape.shape_type.value}")
    print(f"  Fill: {shape.fill_color}, Stroke: {shape.stroke_color}")
```

## 🧪 Testing

Run tests:
```bash
python test_converter.py
```

## 📊 Debug Mode

Enable debug mode to save intermediate processing steps:

```python
from config import DEBUG

DEBUG['save_intermediate_steps'] = True
DEBUG['output_dir'] = './debug_output'
```

Debug outputs:
- `01_text_detection.png` - Detected text elements
- `02_text_removed.png` - After text removal
- `03_image_detection.png` - Detected images
- `04_images_removed.png` - After image removal
- `06_shape_detection.png` - Detected shapes
- `07_shapes_removed_background.png` - Clean background

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# OCR Settings
OCR_CONFIG = {
    'min_confidence': 60,
    'use_easyocr': True,
    'languages': ['en'],
}

# Shape Detection
SHAPE_DETECTION = {
    'min_area': 100,
    'epsilon_factor': 0.02,
}

# Debug Settings
DEBUG = {
    'save_intermediate_steps': False,
    'output_dir': './debug_output',
}
```

## 🔬 Technologies

- **OpenCV** - Image processing and computer vision
- **NumPy** - Numerical operations
- **Tesseract/EasyOCR** - Optical character recognition
- **svgwrite** - SVG generation
- **Pillow** - Image handling
- **scikit-image** - Advanced image processing
- **Shapely** - Geometric operations

## 📝 License

MIT License - see [LICENSE](LICENSE) file

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Enhanced font identification using ML models
- Better italic/bold text detection
- Improved arrow detection algorithms
- Support for gradients and patterns
- Real-time image-to-SVG vectorization
- Multi-language support expansion

## 🐛 Known Limitations

- Font identification is approximate (exact matching requires font database)
- Complex overlapping elements may not separate perfectly
- Handwritten text recognition is limited
- Image-to-SVG vectorization is experimental
- Very small or low-contrast elements may be missed

## 📞 Support

For issues, questions, or feature requests, please open an issue on GitHub.

## 🙏 Acknowledgments

Built with modern computer vision and OCR technologies to make infographic editing accessible and efficient.

---

**Made with ❤️ for the design and data visualization community**
