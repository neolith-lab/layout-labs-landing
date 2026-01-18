# ML-Powered Infographic Layerizer

Convert raster infographics to layered, editable formats (SVG, PSD) using state-of-the-art ML models.

## Features

- **SAM 2 Segmentation**: Pixel-perfect detection of all visual elements
- **CLIP Classification**: Zero-shot categorization (logo, icon, photo, text, etc.)
- **LaMa Inpainting**: Clean background reconstruction
- **PaddleOCR**: Accurate text extraction with styling
- **Multi-format Export**: SVG, PSD, Figma-compatible JSON

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For GPU acceleration (recommended)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Model Downloads

Models are downloaded automatically on first use. For manual download:

```bash
# SAM 2 (default: vit_h, ~2.4GB)
wget https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt

# Or SAM 1 (if SAM 2 unavailable)
wget https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
```

## Quick Start

```bash
# Basic conversion
python -m ml_pipeline.cli infographic.png -o output.svg

# High-quality mode (slower, better results)
python -m ml_pipeline.cli infographic.png -o output.svg --quality

# Fast mode (quicker, lower quality)
python -m ml_pipeline.cli infographic.png -o output.svg --fast

# Export to PSD
python -m ml_pipeline.cli infographic.png -o output.psd --format psd

# With debug visualizations
python -m ml_pipeline.cli infographic.png -o output.svg --debug
```

## Python API

```python
from ml_pipeline import InfographicLayerizer, get_default_config

# Basic usage
from ml_pipeline import process_infographic

result = process_infographic(
    "infographic.png",
    "output.svg",
    output_format="svg"
)

print(f"Detected {len(result.layers)} layers")
print(f"Extracted {len(result.text_elements)} text elements")

# Advanced usage with custom config
config = get_default_config()
config.sam.model_type = "vit_l"  # Use lighter model
config.output.save_debug = True

pipeline = InfographicLayerizer(config)
result = pipeline.process("infographic.png", "output.svg")

# Access individual layers
for layer in result.layers:
    print(f"{layer.id}: {layer.category} at {layer.bbox}")
    
# Access text
for text in result.text_elements:
    print(f"'{text.text}' - size {text.font_size}px, color {text.color}")
```

## Pipeline Stages

### 1. Segmentation (SAM)
Segment Anything Model detects all distinct visual elements with pixel-perfect masks.

### 2. Classification (CLIP)
Each segment is classified into categories:
- `logo` - Brand marks and logos
- `icon` - Symbols and icons
- `photo` - Photographs and realistic images
- `illustration` - Drawings and artwork
- `text_heading` - Title/heading text
- `text_body` - Paragraph text
- `container` - Cards, boxes, frames
- `shape` - Decorative shapes
- `chart` - Graphs and data visualizations
- `button` - UI buttons
- `connector` - Arrows and lines

### 3. Layer Ordering
Elements are ordered by z-index using:
- Category-based priorities (containers below icons)
- Containment relationships
- Area heuristics

### 4. Text Extraction (PaddleOCR)
Extracts text with:
- Position and bounding box
- Estimated font size
- Font weight (normal/bold)
- Text color

### 5. Background Reconstruction (LaMa)
Removes all foreground elements and reconstructs a clean background using large mask inpainting.

### 6. Output Generation
Generates layered output:
- **SVG**: Figma-importable with named layers
- **PSD**: Adobe Photoshop with layer structure
- **JSON**: Figma plugin data format

## Configuration

```python
from ml_pipeline import PipelineConfig, SAMConfig, CLIPConfig

config = PipelineConfig(
    sam=SAMConfig(
        model_type="vit_h",      # vit_h (best), vit_l, vit_b (fastest)
        points_per_side=32,       # More = finer segmentation
        device="auto"             # auto, cuda, mps, cpu
    ),
    clip=CLIPConfig(
        model_name="ViT-B/32",   # ViT-B/32 or ViT-L/14
    ),
    max_image_size=2048,         # Resize if larger
    min_element_size=20,         # Ignore tiny elements
)
```

## Output Formats

### SVG (Recommended for Figma)
- Named layer groups
- Editable text elements
- Embedded images as base64
- Import directly to Figma

### PSD
- True Photoshop layers
- Preserves transparency
- Requires `psd-tools` or `pytoshop`

### JSON (Figma Plugin)
- Structured data for programmatic import
- Base64 image data included
- Use with custom Figma plugin

## Performance

| Model Config | GPU (RTX 3090) | CPU (M1 Pro) | Quality |
|-------------|----------------|--------------|---------|
| Fast        | ~5s            | ~30s         | Good    |
| Default     | ~15s           | ~90s         | Better  |
| Quality     | ~30s           | ~180s        | Best    |

## Troubleshooting

### CUDA Out of Memory
```python
config.sam.model_type = "vit_b"  # Use smaller model
config.max_image_size = 1024     # Resize large images
```

### Slow on CPU
```bash
python -m ml_pipeline.cli input.png --fast
```

### Poor Segmentation
- Increase `points_per_side` in SAMConfig
- Use `--quality` mode
- Ensure image is high resolution

### Missing Text
- Check PaddleOCR language setting
- Lower OCR confidence threshold
- Text may be detected as part of logo/icon

## License

MIT License - see LICENSE file

## Acknowledgments

- [Segment Anything (Meta)](https://github.com/facebookresearch/segment-anything)
- [CLIP (OpenAI)](https://github.com/openai/CLIP)
- [LaMa (Samsung)](https://github.com/advimman/lama)
- [PaddleOCR (Baidu)](https://github.com/PaddlePaddle/PaddleOCR)
