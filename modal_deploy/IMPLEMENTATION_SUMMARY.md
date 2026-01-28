# S3 Integration & JSON Export - Implementation Summary

## Overview

The raster-to-SVG converter has been enhanced to support:
1. **S3 Storage**: All extracted elements (text, images, containers, background) are uploaded to Amazon S3
2. **JSON Export**: Complete extraction data with S3 URLs returned as JSON
3. **Modal Deployment**: Updated to support S3 credentials and JSON-only responses

## Changes Made

### 1. `dev_destructure/raster_to_svg.py`

#### Added S3 Support
- **Constructor updated**: Now accepts `s3_bucket` and `s3_prefix` parameters
- **Boto3 integration**: Automatically initializes S3 client when bucket is provided
- **Upload methods**: 
  - `_upload_to_s3()`: Upload files to S3
  - `_upload_image_to_s3()`: Upload numpy arrays as PNG to S3

#### Updated Debug Methods
All debug saving methods now:
- Save files locally (as before)
- Upload to S3 (if enabled)
- Include `s3_url` field in JSON metadata

**Modified methods:**
- `_save_text_elements_debug()`: Uploads cropped text images
- `_save_image_elements_debug()`: Uploads cropped image elements  
- `_save_container_elements_debug()`: Uploads cropped container images
- `_save_background_debug()`: Uploads full background image

#### JSON Structure with S3 URLs

Each element in the JSON now includes an `s3_url` field:

```json
{
  "id": 0,
  "text": "Sample Text",
  "bbox": { ... },
  "font": { ... },
  "cropped_image": "text_000.png",
  "s3_url": "https://bucket.s3.amazonaws.com/prefix/text_elements/text_000.png"
}
```

### 2. `modal_deploy/main.py`

#### Added AWS Integration
- **Secret management**: Uses `modal.Secret.from_name("aws-credentials")`
- **Boto3 dependency**: Added to pip install list
- **Environment variable**: Supports `AWS_S3_BUCKET` env var

#### Updated Function Signature

```python
def convert_image_to_svg(
    image_url: str = None,
    image_bytes: bytes = None,
    output_filename: str = "output.svg",
    debug: bool = True,  # ← Default True for extraction
    ocr_confidence: int = 60,
    convert_images: bool = False,
    return_json_only: bool = True,  # ← New parameter
    s3_bucket: str = None,  # ← New parameter
) -> dict:
```

#### Return Modes

**JSON-only mode** (`return_json_only=True`):
- Returns extraction data with S3 URLs
- Does NOT include SVG content or debug images
- Minimal response size, optimal for API usage

**Full mode** (`return_json_only=False`):
- Returns SVG content
- Includes debug images as binary data
- Larger response, suitable for local development

### 3. Documentation

- **`S3_SETUP.md`**: Complete guide for configuring AWS S3 with Modal
- **`IMPLEMENTATION_SUMMARY.md`**: This document

## S3 File Organization

```
s3://your-bucket/
└── extractions/
    └── {uuid}/                    # Unique ID per conversion
        ├── text_elements/
        │   ├── text_000.png
        │   ├── text_001.png
        │   └── text_elements.json
        ├── image_elements/
        │   ├── image_000.png
        │   ├── image_001.png
        │   └── image_elements.json
        ├── container_elements/
        │   ├── container_000.png
        │   ├── container_001.png
        │   └── container_elements.json
        ├── background/
        │   ├── background.png
        │   └── background.json
        └── combined_extraction_data.json
```

## Usage Examples

### Local Usage (No S3)

```python
from raster_to_svg import RasterToSVGConverter

# Without S3 - files saved locally only
converter = RasterToSVGConverter()
result = converter.convert('input.png', 'output.svg')
```

### Local Usage with S3

```python
from raster_to_svg import RasterToSVGConverter

# With S3 - files saved locally AND uploaded to S3
converter = RasterToSVGConverter(
    s3_bucket='my-bucket',
    s3_prefix='my-project/extractions'
)
result = converter.convert('input.png', 'output.svg')
```

### Modal Usage (JSON-only)

```python
import modal

app = modal.App.lookup("raster-to-svg-converter")
convert_fn = modal.Function.lookup("raster-to-svg-converter", "convert_image_to_svg")

# Returns JSON with S3 URLs
result = convert_fn.remote(
    image_url="https://example.com/image.png",
    return_json_only=True,  # Only JSON, no SVG or images
    s3_bucket="my-bucket"    # Optional, uses env var by default
)

# Access extraction data
extraction = result['extraction_data']
for elem in extraction['stages']['text_detection']['elements']:
    print(f"Text: {elem['text']}, URL: {elem['s3_url']}")
```

### Modal Usage (Full Response)

```python
# Returns SVG content + debug images
result = convert_fn.remote(
    image_url="https://example.com/image.png",
    return_json_only=False,  # Include SVG and images
    debug=True
)

svg_content = result['svg_content']
debug_images = result['debug_images']  # Binary image data
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Local development
pip install boto3

# Modal deployment (automatic via image definition)
# boto3 is included in the Modal image
```

### 2. Configure AWS Credentials

**For Local:**
```bash
# Use AWS CLI or environment variables
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1
```

**For Modal:**
```bash
# Create Modal secret
modal secret create aws-credentials \
  AWS_ACCESS_KEY_ID=your-key \
  AWS_SECRET_ACCESS_KEY=your-secret \
  AWS_DEFAULT_REGION=us-east-1 \
  AWS_S3_BUCKET=your-bucket-name
```

### 3. Create S3 Bucket

```bash
aws s3 mb s3://your-bucket-name --region us-east-1

# Optional: Enable public access for generated URLs
aws s3api put-bucket-policy --bucket your-bucket-name --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::your-bucket-name/*"
  }]
}'
```

## Type Conversion for JSON Serialization

All numeric and collection types are explicitly converted to Python native types to ensure JSON serialization:

- `int()` for all integer values (bbox coordinates, counts, IDs)
- `float()` for all floating point values (confidence, aspect ratio)
- `str()` for all string values
- `bool()` for all boolean values
- Nested lists explicitly converted element-by-element (e.g., dominant colors)

This prevents `TypeError: Object of type int64 is not JSON serializable` errors with numpy types.

## Benefits

1. **Scalability**: Extracted elements stored in S3, not sent over network
2. **Persistence**: Elements remain accessible after function execution
3. **Efficiency**: JSON responses are small, only containing URLs
4. **Flexibility**: Can choose between JSON-only or full response
5. **Cost-effective**: S3 storage is inexpensive for small images

## Testing

### Test Local S3 Upload

```bash
cd dev_destructure
python cli.py input.png -o output.svg
# Check ./debug_output for local files
# Check S3 bucket for uploaded files (if configured)
```

### Test Modal Deployment

```bash
cd modal_deploy

# Deploy the app
modal deploy main.py

# Test with a sample image
modal run main.py --input-url "https://example.com/image.png"
```

## Notes

- S3 URLs are generated as `https://{bucket}.s3.amazonaws.com/{key}`
- Each conversion gets a unique UUID prefix to avoid conflicts
- Local files are still saved for backward compatibility
- S3 upload failures are logged as warnings but don't stop the conversion
- boto3 import is lazy-loaded only when S3 is enabled
