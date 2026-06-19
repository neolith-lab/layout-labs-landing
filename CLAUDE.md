# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Raster to SVG Infographic Converter** - A computer vision pipeline that converts raster infographics (PNG, JPG) into editable SVG files and Excalidraw JSON format. The system uses OCR, ML-based detection, and intelligent inpainting to extract and reconstruct text, images, containers, and shapes.

## Repository Structure

The repository contains three main components:

1. **`dev_destructure/`** - Development/local conversion pipeline
   - Main converter implementation
   - All detection modules (text, image, container, shape, logo)
   - CLI interface for local testing
   - Python virtual environment in `venv/`

2. **`modal_deploy/`** - Cloud deployment (Modal serverless)
   - Serverless wrapper around the conversion pipeline
   - GPU-accelerated execution (L40S)
   - S3 integration for storage
   - Copies of core logic in `logic/` subdirectory

3. **`font_coalesce/`** - Font mapping utilities
   - Google Fonts integration
   - Font normalization and standardization
   - WOFF2 conversion tools

## Development Commands

### Local Development (dev_destructure/)

```bash
# Setup and installation
cd dev_destructure
python setup.py  # Installs all dependencies including Tesseract

# Basic conversion
python cli.py input.png -o output.svg

# With debug mode (saves intermediate processing steps)
python cli.py input.png -o output.svg --debug

# Excalidraw JSON generation with embedded images
python cli.py input.png -o output.excalidraw --excalidraw

# S3 upload with custom bucket and prefix
python cli.py input.png --s3-bucket my-bucket --s3-prefix project/v1

# Batch processing
python cli.py ./images -o ./output --batch --pattern "*.jpg"

# Adjust OCR confidence threshold
python cli.py input.png -o output.svg --ocr-confidence 70
```

### Modal Cloud Deployment (modal_deploy/)

```bash
# Install and authenticate Modal
pip install modal
modal token new

# Single file conversion from local path
modal run main.py --input-path input.png

# From URL (preferred for cloud execution)
modal run main.py --input-url https://example.com/image.png

# Generate Excalidraw JSON with embedded images
modal run main.py --input-path input.png --excalidraw

# With custom S3 bucket
modal run main.py --input-path input.png --s3-bucket my-bucket

# Excalidraw without downloading images (faster, smaller output)
modal run main.py --input-path input.png --excalidraw --no-download-images
```

### Testing

```bash
# Run local tests
cd dev_destructure
python test_converter.py
python test_excalidraw_converter.py
python test_image_filtering.py

# Test Modal deployment
cd modal_deploy
python test_deployment.py
```

## System Requirements

- **Python**: 3.10+ (project uses 3.10 specifically)
- **Tesseract OCR**: Required for text extraction
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- **GPU**: Optional but recommended for Modal deployment (uses L40S in cloud)

## Pipeline Architecture

The conversion happens in three distinct phases:

### Phase 1: Text Detection and Removal
1. OCR extraction using Tesseract + EasyOCR fallback
2. Font classification using ML model (ONNX runtime)
3. Text removal with dominant border color inpainting

### Phase 2: Detection and Removal (on text-removed image)
1. Image/icon detection using color variance, edge density, texture analysis
2. Logo detection using Siamese neural network (`siamese_logo_detector.pth`)
3. Container detection (rounded rectangles, cards)
4. Progressive removal with inpainting (Telea/Navier-Stokes algorithms)

### Phase 3: Generation
1. **SVG mode**: Creates layered SVG with background → containers → images → text
2. **Excalidraw mode**: Generates Excalidraw JSON with optional base64-embedded images

## Key Modules and Their Roles

### Core Detection Modules (dev_destructure/)
- **`raster_to_svg.py`**: Main orchestrator class `RasterToSVGConverter`
- **`text_extractor.py`**: OCR with `TextExtractor` class
- **`font_classifier.py`**: ML-based font family classification
- **`image_detector.py`**: Multi-method image detection
- **`container_detector.py`**: Rounded rectangle/card detection
- **`shape_detector.py`**: Geometric shape detection (circles, rectangles, polygons)
- **`logo_detector.py`**: Basic logo detection
- **`siamese_logo_detector.py`**: Advanced ML logo detection (98MB model)
- **`background_filler.py`**: Inpainting for element removal
- **`svg_generator.py`**: SVG file generation
- **`excalidraw_converter.py`**: Excalidraw JSON generation

### Configuration and Utilities
- **`config.py`**: All pipeline settings (OCR, detection thresholds, debug options)
- **`utils.py`**: Common utilities and `BoundingBox` class
- **`advanced_utils.py`**: Advanced utility functions
- **`cli.py`**: Command-line interface wrapper

### Machine Learning Pipeline (ml_pipeline/)
- **`data_structures.py`**: ML data structures
- **`segmentation.py`**: Image segmentation
- **`classification.py`**: Classification utilities
- **`inpainting.py`**: ML-based inpainting

## Data Flow and Element Structure

Elements detected by the pipeline follow this structure:

```python
# Text Element
TextElement(
    text: str,
    bbox: BoundingBox,
    font_family: str,
    font_size: int,
    font_weight: str,
    font_style: str,
    color: str,
    confidence: float
)

# Image Element
ImageElement(
    bbox: BoundingBox,
    image_data: np.ndarray,
    is_photo: bool,
    dominant_colors: List[Tuple]
)

# Container Element
ContainerElement(
    bbox: BoundingBox,
    border_radius: int,
    fill_color: str,
    stroke_color: str,
    images: List[ImageElement]  # Images inside the container
)
```

## Modal Deployment Details

The Modal deployment (`modal_deploy/main.py`) runs with:
- **CPU**: 4 cores
- **Memory**: 8GB RAM
- **GPU**: L40S (NVIDIA)
- **Timeout**: 10 minutes (single), 30 minutes (batch)
- **Image**: Debian slim with Python 3.10
- **Dependencies**: Includes PyTorch, ONNX GPU runtime, all CV libraries

Modal automatically caches the container image after the first build for faster subsequent runs.

## S3 Integration

When `--s3-bucket` is specified:
1. All extracted elements are uploaded to S3
2. JSON extraction data is stored at `s3://{bucket}/{prefix}/extraction_data.json`
3. Debug images are stored at `s3://{bucket}/{prefix}/debug/`
4. Excalidraw JSON is stored at `s3://{bucket}/{prefix}/output.excalidraw`

Required AWS environment variables for S3:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` or `AWS_DEFAULT_REGION`

## Font Mapping System

The `font_coalesce/` directory manages font standardization:
- **`anchors.py`**: Font anchor definitions
- **`mappers.py`**: Font mapping logic
- **`font_download.py`**: Downloads Google Fonts
- **`convert_to_woff2.py`**: Converts fonts to WOFF2 format
- **`final_font_mapping.csv`**: Master font mapping table
- **`google_fonts_mapping.tsv`**: Google Fonts metadata
- **`font_to_anchor_mapping.json`**: Font classification mappings (also in dev_destructure and modal_deploy/logic)

## Debug Mode

Enable with `--debug` flag to save intermediate processing steps:

```
debug_output/
├── text_elements/
│   ├── text_elements.json
│   └── text_detection_visualization.png
├── image_elements/
│   ├── image_elements.json
│   └── image_detection_visualization.png
├── container_elements/
│   ├── container_elements.json
│   └── container_detection_visualization.png
├── background/
│   ├── background.json
│   └── final_background.png
└── combined_extraction_data.json
```

## Configuration Customization

Edit `dev_destructure/config.py` to adjust:

```python
# OCR Settings
OCR_CONFIG = {
    'min_confidence': 60,  # Minimum OCR confidence (0-100)
    'use_easyocr': True,   # Enable EasyOCR fallback
    'languages': ['en'],
}

# Shape Detection
SHAPE_DETECTION = {
    'min_area': 100,        # Minimum shape area in pixels
    'epsilon_factor': 0.02, # Contour approximation factor
}

# Debug Settings
DEBUG = {
    'save_intermediate_steps': False,
    'output_dir': './debug_output',
    'verbose': False,
}
```

## Important Implementation Notes

### Synchronized Code Between dev_destructure and modal_deploy/logic
The `modal_deploy/logic/` directory contains copies of core modules from `dev_destructure/`. When modifying detection logic:
1. Make changes in `dev_destructure/` first
2. Test locally
3. Copy changes to `modal_deploy/logic/` before deploying

### Sequential Processing Order
The pipeline processes elements in a specific order to prevent interference:
1. Text removed first (text can overlap everything)
2. Images detected and removed (on text-free image)
3. Containers detected and removed (on text+image-free image)
4. Clean background extracted

### Font Classification
Uses a pre-trained ONNX model for font family classification. The model is downloaded from HuggingFace on first use and cached locally.

### Logo Detection
The Siamese logo detector (`siamese_logo_detector.pth`) is a 98MB PyTorch model trained for logo/icon identification. It helps distinguish logos from regular images to prevent incorrect text extraction from logo text.

## Performance Considerations

- **Typical processing time** (800x600 image): 7-13 seconds local, 5-8 seconds on Modal GPU
- **Memory usage**: 100-300MB for typical infographics
- **Batch processing**: Can process multiple images in parallel on Modal
- **GPU acceleration**: Modal deployment uses GPU for font classification and logo detection

## Known Limitations

- Font identification is approximate (maps to closest Google Font)
- Complex overlapping elements may not separate perfectly
- Handwritten text recognition is limited
- Very small (<50px) or low-contrast elements may be missed
- S3 upload requires proper AWS credentials configuration
