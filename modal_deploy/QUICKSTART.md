# Quick Setup Guide for Modal Deployment

## Step 1: Install Modal

```bash
pip install modal
```

## Step 2: Authenticate

```bash
modal token new
```

This will open your browser to authenticate with Modal.

## Step 3: Deploy the App

The app is automatically deployed when you run it. No separate deploy step needed!

## Step 4: Run Your First Conversion

### From Command Line:

```bash
# Single file
modal run main.py --input-path ../dev_destructure/input.png --output-path output.svg

# With debug mode
modal run main.py --input-path ../dev_destructure/input.png --output-path output.svg --debug

# Batch mode
modal run main.py --input-path ../dev_destructure/sample_data --output-path ./output --batch
```

### From Python:

```python
from pathlib import Path

# Option 1: Using the CLI-style interface
!modal run main.py --input-path input.png --output-path output.svg

# Option 2: Using the Python API
import modal

# Read image
with open("input.png", "rb") as f:
    image_bytes = f.read()

# Get the function
convert_fn = modal.Function.lookup("raster-to-svg-converter", "convert_image_to_svg")

# Convert
result = convert_fn.remote(
    image_bytes=image_bytes,
    output_filename="output.svg",
    debug=False,
    ocr_confidence=60
)

# Save SVG
with open("output.svg", "w") as f:
    f.write(result["svg_content"])

print(f"Conversion complete! Stats: {result['statistics']}")
```

## Step 5: Monitor Your Jobs

Visit https://modal.com to see your running jobs, logs, and usage.

## Common Commands

```bash
# View app logs
modal app logs raster-to-svg-converter

# List deployed apps
modal app list

# Stop a running app
modal app stop raster-to-svg-converter
```

## Testing Locally First

Before using Modal, test the converter locally:

```bash
cd ../dev_destructure
python cli.py input.png -o output.svg --debug
```

## Cost Estimation

Modal pricing (as of 2024):
- **Free tier**: $30/month in credits
- **Compute**: ~$0.000231/second for 4 CPU + 8GB RAM
- **Storage**: Minimal (only intermediate files)

Typical conversion:
- Small image (1MB): ~5-10 seconds = ~$0.001-0.002
- Medium image (5MB): ~15-30 seconds = ~$0.003-0.007
- Large image (20MB): ~30-60 seconds = ~$0.007-0.014

## Troubleshooting

### "App not found" error

Run the app once to deploy it:
```bash
modal run main.py --input-path test.png --output-path test.svg
```

### Import errors in IDE

These are expected - the imports work in the Modal container. You can ignore them locally.

### Slow first run

The first run builds and caches the container image (~2-3 minutes). Subsequent runs are fast (~5-10 seconds startup).

## Next Steps

1. Try the example: `python example_usage.py input.png output.svg`
2. Customize parameters in `main.py` (CPU, memory, timeout)
3. Add your own preprocessing or postprocessing steps
4. Set up webhook endpoints for automated conversions

For more details, see the full README.md.
