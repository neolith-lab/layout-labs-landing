# Excalidraw Export Feature

## Overview

The raster-to-svg converter now supports exporting to **Excalidraw JSON format**, allowing you to open extracted infographics directly in Excalidraw for editing.

## What is Excalidraw?

Excalidraw is a whiteboard tool that lets you easily sketch diagrams with a hand-drawn feel. By converting your infographic extractions to Excalidraw format, you can:

- ✏️ Edit text elements
- 🎨 Modify colors and styles
- 📐 Resize and reposition elements
- 🖼️ Work with embedded images
- 💾 Save and share editable diagrams

## Features

### ✅ What's Supported

- **Text Elements** - All extracted text with positioning, font size, and colors
- **Images** - Logos and graphics embedded as base64 or linked from S3
- **Containers** - Background rectangles with borders and fills
- **Shapes** - Detected geometric shapes (rectangles, ellipses, etc.)
- **Layering** - Proper z-index (containers → shapes → images → text)

### 🎯 Element Mapping

| Extraction Type | Excalidraw Type | Notes |
|----------------|-----------------|-------|
| Text | Text | Font size, color, alignment preserved |
| Logo/Image | Image | Embedded as base64 or S3 reference |
| Container | Rectangle | Background with borders |
| Rectangle | Rectangle | Stroke and fill |
| Circle | Ellipse | Converted to ellipse shape |
| Diamond | Diamond | Native diamond shape |

## Usage

### Command Line (CLI)

#### Basic Excalidraw Export

```bash
# Convert image and generate Excalidraw JSON with embedded images
python cli.py input.png --excalidraw -o output.excalidraw
```

#### With S3 Storage (No Image Download)

```bash
# Extract to S3, generate Excalidraw JSON without downloading images
python cli.py input.png --s3-bucket my-bucket --excalidraw --no-download-images
```

This is **faster** but images won't be embedded in the Excalidraw file.

#### Full Example with Debug

```bash
# Extract, upload to S3, and generate Excalidraw with embedded images
python cli.py infographic.png \
  --excalidraw \
  --s3-bucket layoutlabs-temp \
  --s3-prefix project-x/v1 \
  --debug \
  -o my_diagram.excalidraw
```

### Modal Deployment

#### Basic Usage

```bash
# From URL with Excalidraw export
modal run main.py \
  --input-url https://example.com/infographic.png \
  --excalidraw
```

#### With S3 and Options

```bash
# Full pipeline: S3 upload + Excalidraw generation
modal run main.py \
  --input-path infographic.png \
  --s3-bucket my-bucket \
  --excalidraw
```

#### Fast Mode (No Image Download)

```bash
# Generate Excalidraw JSON without embedding images
modal run main.py \
  --input-url https://example.com/infographic.png \
  --excalidraw \
  --no-download-images
```

## Output Files

### With Excalidraw Export

When using `--excalidraw`, you'll get:

1. **`output.excalidraw`** - Main Excalidraw JSON file
2. **`extraction_data.json`** - Raw extraction data with S3 URLs
3. **`debug_output/`** - Intermediate files (if `--debug` enabled)

### Excalidraw File Structure

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://layoutlabs.com",
  "elements": [
    {
      "id": "...",
      "type": "rectangle|text|image|ellipse",
      "x": 100,
      "y": 200,
      "width": 300,
      "height": 150,
      // ... more properties
    }
  ],
  "appState": {
    "viewBackgroundColor": "#ffffff",
    "zoom": {"value": 1}
  },
  "files": {
    "file-uuid": {
      "dataURL": "data:image/png;base64,...",
      "mimeType": "image/png"
    }
  }
}
```

## Opening in Excalidraw

### In Your App (infogen)

1. Open the Excalidraw editor
2. Click **"Load JSON"** button in the toolbar
3. Select your `.excalidraw` file
4. Elements appear on the canvas!

### On excalidraw.com

1. Go to https://excalidraw.com
2. Click **Open** → **Open file**
3. Select your `.excalidraw` file
4. Edit and save!

## Performance Considerations

### With Image Embedding (`--excalidraw`)

- **Pros**: Complete, self-contained file that works offline
- **Cons**: Larger file size (images as base64), slower processing
- **Best for**: Final deliverables, sharing, archiving

### Without Image Embedding (`--excalidraw --no-download-images`)

- **Pros**: Fast processing, small file size
- **Cons**: No images in the Excalidraw file
- **Best for**: Quick text/shape extraction, testing layouts

## Examples

### Example 1: Marketing Infographic

```bash
# Extract and convert marketing infographic
python cli.py marketing_infographic.png \
  --excalidraw \
  -o marketing_editable.excalidraw

# Output:
# ✓ 15 text elements
# ✓ 3 logos embedded
# ✓ 8 containers
# ✓ Total: marketing_editable.excalidraw (2.3 MB)
```

### Example 2: Large Infographic (Fast Mode)

```bash
# Process large infographic quickly without images
python cli.py large_poster.png \
  --s3-bucket my-bucket \
  --excalidraw \
  --no-download-images

# Output:
# ✓ 45 text elements
# ✓ 12 containers
# ✓ Images in S3 (not embedded)
# ✓ Total: output.excalidraw (25 KB)
```

### Example 3: Batch Processing

```bash
# Process directory of infographics
python cli.py ./infographics/ \
  --batch \
  --pattern "*.png" \
  --excalidraw \
  -o ./excalidraw_output/

# Each PNG gets its own .excalidraw file
```

## Troubleshooting

### Issue: Images not showing in Excalidraw

**Solution**: Make sure you didn't use `--no-download-images` flag. Re-run without it:

```bash
python cli.py input.png --excalidraw  # Images will be embedded
```

### Issue: File too large

**Solution**: Use S3 storage without downloading images:

```bash
python cli.py input.png --s3-bucket my-bucket --excalidraw --no-download-images
```

### Issue: Text positioning is off

**Cause**: Different coordinate systems between extraction and Excalidraw

**Solution**: This is handled automatically. If issues persist, check the `bbox` format in your extraction data.

### Issue: Colors look different

**Cause**: Color format conversion

**Solution**: The converter normalizes colors to hex format. Check your extraction data's color format.

## Advanced Configuration

### Custom Font Mapping

Edit `excalidraw_converter.py`:

```python
font_family_map = {
    'virgil': 1,      # Hand-drawn
    'helvetica': 2,   # Clean sans-serif
    'cascadia': 3,    # Monospace
}
```

### Z-Index Layering

Elements are layered in this order:

1. **Containers** (a0, a1, a2...) - Background
2. **Shapes** (a3, a4, a5...) - Mid-layer
3. **Images** (a6, a7, a8...) - Above shapes
4. **Text** (a9, a10...) - Foreground

## API Integration

### Python API

```python
from excalidraw_converter import ExcalidrawConverter

# Create converter
converter = ExcalidrawConverter()

# Convert extraction data
excalidraw_json = converter.convert(
    extraction_data=extraction_result['extraction_data'],
    statistics=extraction_result['statistics'],
    download_images=True  # Set False to skip image downloads
)

# Save to file
converter.convert_to_file(
    extraction_data=extraction_data,
    statistics=statistics,
    output_path='output.excalidraw',
    download_images=True
)
```

### Modal Function

```python
import modal

result = convert_image_to_svg.remote(
    image_url="https://example.com/image.png",
    s3_bucket="my-bucket",
    generate_excalidraw=True,
    download_images=True
)

# Result includes:
# - extraction_data: Raw extraction
# - statistics: Element counts
# - excalidraw_json: Complete Excalidraw format (if generate_excalidraw=True)
```

## Next Steps

1. **Test the feature**: Try converting a simple infographic
2. **Load in Excalidraw**: Open your app and load the generated JSON
3. **Iterate**: Adjust extraction settings if positioning/sizing is off
4. **Integrate**: Add to your production pipeline

## Support

For issues or questions:
- Check the main README.md
- Review EXCALIDRAW_JSON_GUIDE.md in infogen repo
- Test with the sample file: `test_excalidraw.json`

---

**Happy diagramming! 🎨**
