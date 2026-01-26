# Raster to SVG Converter - Modal Deployment

This directory contains the Modal deployment for the Raster to SVG converter, allowing you to convert infographic images to editable SVG files in the cloud.

## Prerequisites

1. Install Modal:
```bash
pip install modal
```

2. Authenticate with Modal:
```bash
modal token new
```

## Usage

### Single File Conversion

Convert a single image to SVG:

```bash
modal run main.py --input-path input.png --output-path output.svg
```

With debug mode (saves intermediate steps):

```bash
modal run main.py --input-path input.png --output-path output.svg --debug
```

Adjust OCR confidence threshold:

```bash
modal run main.py --input-path input.png --output-path output.svg --ocr-confidence 70
```

### Batch Conversion

Convert all PNG files in a directory:

```bash
modal run main.py --input-path ./images --output-path ./output --batch
```

Process JPG files:

```bash
modal run main.py --input-path ./images --output-path ./output --batch --pattern "*.jpg"
```

### Python API Usage

You can also use the Modal functions directly from Python:

```python
import modal

# Get the app
app = modal.App.lookup("raster-to-svg-converter", create_if_missing=True)

# Read your image
with open("input.png", "rb") as f:
    image_bytes = f.read()

# Convert using Modal
with app.run():
    convert_fn = modal.Function.lookup("raster-to-svg-converter", "convert_image_to_svg")
    result = convert_fn.remote(
        image_bytes=image_bytes,
        output_filename="output.svg",
        debug=True,
        ocr_confidence=60
    )
    
    # Save the SVG
    with open("output.svg", "w") as f:
        f.write(result["svg_content"])
    
    print(f"Statistics: {result['statistics']}")
```

## Configuration Options

### Command Line Arguments

- `--input-path`: Input image file or directory (required)
- `--output-path`: Output SVG file or directory (default: "output.svg")
- `--batch`: Enable batch mode for processing directories
- `--pattern`: File pattern for batch mode (default: "*.png")
- `--debug`: Enable debug mode to save intermediate processing steps
- `--ocr-confidence`: Minimum OCR confidence threshold, 0-100 (default: 60)
- `--convert-images`: Convert embedded images to SVG (experimental)

### Function Parameters

The `convert_image_to_svg` function accepts:

- `image_bytes` (bytes): Input image as bytes (required)
- `output_filename` (str): Name for output SVG file
- `debug` (bool): Enable debug mode
- `ocr_confidence` (int): Minimum OCR confidence threshold (0-100)
- `convert_images` (bool): Convert embedded images to SVG (experimental)

## Return Values

The conversion function returns a dictionary with:

```python
{
    'svg_content': str,  # The generated SVG as a string
    'statistics': {
        'text_elements': int,
        'logos': int,
        'containers': int,
        'images_in_containers': int,
        'standalone_images': int,
        'shapes': int,
        'dimensions': tuple[int, int]
    },
    'debug_images': dict[str, bytes]  # Debug images if debug=True
}
```

## Resource Allocation

The Modal function is configured with:
- **CPU**: 4 cores
- **Memory**: 8GB RAM
- **Timeout**: 10 minutes (single), 30 minutes (batch)

These can be adjusted in `main.py` by modifying the `@app.function()` decorator parameters.

## Architecture

The converter runs through the following phases:

### Phase 1: Text Detection and Removal
1. Detect all text using OCR (Tesseract + EasyOCR)
2. Remove text and infill using dominant border color

### Phase 2: Detection and Removal on Infilled Image
1. Detect images/icons
2. Remove images and infill
3. Detect containers (rounded rectangles, cards)
4. Clean container interiors
5. Remove containers and infill background

### Phase 3: SVG Generation
Creates layered SVG with:
- Layer 1: Background
- Layer 2: Container shapes
- Layer 3: Images inside containers
- Layer 4: Standalone images
- Layer 5: Text

## Troubleshooting

### Import Errors in IDE

The import errors in your IDE for Modal-specific imports are expected and can be ignored. The code runs in the Modal container where all dependencies are installed.

### OCR Issues

If text detection is poor, try:
- Adjusting `--ocr-confidence` (lower for more text, higher for better accuracy)
- Ensuring input images have good resolution (at least 72 DPI)

### Memory Issues

For very large images, you may need to increase memory allocation in the `@app.function()` decorator.

## Local Development

To test changes locally before deploying:

```bash
cd ../dev_destructure
python cli.py input.png -o output.svg --debug
```

## Deployment

Modal automatically handles deployment. Each `modal run` command:
1. Builds the container image (cached after first run)
2. Uploads your code changes
3. Runs the function in the cloud
4. Streams results back to you

## Cost Considerations

Modal charges based on:
- Compute time (CPU/memory usage)
- Container startup time
- Egress (data transfer)

The function is optimized to minimize costs by:
- Using efficient CPU allocation
- Returning only necessary data
- Caching the container image

