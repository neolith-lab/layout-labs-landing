# CLI with S3 Upload - Usage Guide

## Overview

The CLI now supports uploading extracted elements (text, images, containers, background) to Amazon S3 during the conversion process.

## Prerequisites

1. **AWS Credentials**: Configure AWS credentials via:
   - Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - AWS CLI configuration: `~/.aws/credentials`
   - IAM role (if running on EC2/ECS)

2. **boto3 installed**:
   ```bash
   pip install boto3
   ```

3. **S3 Bucket**: Create a bucket for storing extractions:
   ```bash
   aws s3 mb s3://my-extractions-bucket
   ```

## Basic Usage

### Single File with S3 Upload

```bash
python cli.py input.png -o output.svg --debug --s3-bucket my-extractions-bucket
```

This will:
1. Convert `input.png` to `output.svg`
2. Extract all elements (text, images, containers, background)
3. Save files locally in `./debug_output/`
4. Upload all files to S3 at `s3://my-extractions-bucket/extractions/<uuid>/`
5. Create `combined_extraction_data.json` with all S3 URLs

### With Custom S3 Prefix

```bash
python cli.py input.png -o output.svg --debug \
  --s3-bucket my-extractions-bucket \
  --s3-prefix my-project/batch-2024-01
```

Files will be uploaded to: `s3://my-extractions-bucket/my-project/batch-2024-01/`

### Batch Mode with S3

```bash
python cli.py ./images -o ./output --batch --debug \
  --s3-bucket my-extractions-bucket \
  --s3-prefix my-project/batch-001
```

Each image will be processed and uploaded to S3 with a unique UUID subdirectory.

## Command-Line Options

### S3-Specific Options

| Option | Description | Example |
|--------|-------------|---------|
| `--s3-bucket` | S3 bucket name | `--s3-bucket my-bucket` |
| `--s3-prefix` | Custom prefix/folder | `--s3-prefix project/v1` |

### Required for S3 Upload

- `--debug` flag must be enabled for element extraction and S3 upload

## Output

### Console Output

```
Converting 'input.png' to 'output.svg'...
S3 Storage enabled: s3://my-extractions-bucket/extractions/abc123...
INFO:raster_to_svg:Starting conversion: input.png -> output.svg
...
INFO:raster_to_svg:Saving text elements debug data...
INFO:raster_to_svg:Saved 45 text elements to ./debug_output/text_elements
INFO:raster_to_svg:Uploaded to S3: https://my-bucket.s3.amazonaws.com/...
...

============================================================
CONVERSION COMPLETE
============================================================
Output file:     output.svg

Statistics:
  Text elements:       45
  Containers:          9
  Images (containers): 15
  Images (standalone): 9
  Dimensions:          1024x1024

Debug output:    ./debug_output
S3 uploads:      s3://my-extractions-bucket/extractions/abc123.../
                 Check combined_extraction_data.json for all S3 URLs
```

### Local Files Created

```
./debug_output/
├── text_elements/
│   ├── text_000.png
│   ├── text_001.png
│   └── text_elements.json
├── image_elements/
│   ├── image_000.png
│   └── image_elements.json
├── container_elements/
│   ├── container_000.png
│   └── container_elements.json
├── background/
│   ├── background.png
│   └── background.json
└── combined_extraction_data.json  ← Contains all S3 URLs
```

### S3 Structure

```
s3://my-extractions-bucket/
└── extractions/
    └── abc123-def456-.../           # UUID for this conversion
        ├── text_elements/
        │   ├── text_000.png
        │   └── ...
        ├── image_elements/
        │   ├── image_000.png
        │   └── ...
        ├── container_elements/
        │   └── ...
        └── background/
            └── background.png
```

## Accessing S3 URLs

### From JSON File

```bash
cat ./debug_output/combined_extraction_data.json | jq '.stages.text_detection.elements[0].s3_url'
# Output: "https://my-bucket.s3.amazonaws.com/extractions/.../text_elements/text_000.png"
```

### From Python

```python
import json

# Read the combined JSON
with open('./debug_output/combined_extraction_data.json', 'r') as f:
    data = json.load(f)

# Get text element S3 URLs
for elem in data['stages']['text_detection']['elements']:
    print(f"Text: {elem['text']}")
    print(f"S3 URL: {elem['s3_url']}")
    print()

# Get image S3 URLs
for elem in data['stages']['image_detection']['elements']:
    print(f"Image bbox: {elem['bbox']}")
    print(f"S3 URL: {elem['s3_url']}")
    print()

# Get background S3 URL
background_url = data['stages']['background_extraction']['s3_url']
print(f"Background: {background_url}")
```

## Examples

### 1. Simple Conversion with S3

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=us-east-1

# Convert and upload
python cli.py infographic.png -o result.svg --debug --s3-bucket my-bucket
```

### 2. Batch Processing with S3

```bash
# Process all PNGs in a directory
python cli.py ./infographics -o ./output --batch --debug \
  --s3-bucket my-bucket \
  --s3-prefix company-assets/2024/january
```

### 3. With Custom Debug Directory

```bash
python cli.py input.png -o output.svg --debug \
  --debug-dir ./my-debug \
  --s3-bucket my-bucket
```

### 4. High Confidence OCR + S3

```bash
python cli.py input.png -o output.svg --debug \
  --ocr-confidence 80 \
  --s3-bucket my-bucket
```

## Troubleshooting

### "Failed to upload to S3" Warnings

**Problem**: Files are processed but not uploaded to S3.

**Solutions**:
1. Check AWS credentials:
   ```bash
   aws sts get-caller-identity
   ```

2. Verify bucket exists and is accessible:
   ```bash
   aws s3 ls s3://my-bucket/
   ```

3. Check IAM permissions (need `s3:PutObject`):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:PutObject", "s3:PutObjectAcl"],
       "Resource": "arn:aws:s3:::my-bucket/*"
     }]
   }
   ```

### S3 URLs Return 403 Forbidden

**Problem**: Can't access uploaded files via HTTPS URL.

**Solution**: Make bucket publicly readable (if appropriate):
```bash
aws s3api put-bucket-policy --bucket my-bucket --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::my-bucket/*"
  }]
}'
```

Or use pre-signed URLs for temporary access.

### boto3 Not Found

**Problem**: `ModuleNotFoundError: No module named 'boto3'`

**Solution**:
```bash
pip install boto3
```

## Cost Estimation

For typical infographic (1024x1024 px) with 50 text elements, 20 images, 10 containers:

- **Storage**: ~5 MB per infographic
- **S3 Storage Cost**: ~$0.023/GB/month = $0.00012/month per infographic
- **Upload Cost**: ~80 PUT requests × $0.005/1000 = $0.0004
- **Data Transfer**: Usually free (first 100 GB/month)

**Total cost per infographic**: < $0.001 (essentially free)

## Best Practices

1. **Use prefixes** to organize by project/date:
   ```bash
   --s3-prefix projects/acme-corp/2024-01/batch-001
   ```

2. **Enable lifecycle policies** to auto-delete old extractions:
   ```bash
   aws s3api put-bucket-lifecycle-configuration \
     --bucket my-bucket \
     --lifecycle-configuration file://lifecycle.json
   ```

3. **Use separate buckets** for different environments:
   - Development: `my-app-dev-extractions`
   - Production: `my-app-prod-extractions`

4. **Store metadata** in your database linking to S3 URLs for easy retrieval

5. **Enable versioning** for important assets:
   ```bash
   aws s3api put-bucket-versioning \
     --bucket my-bucket \
     --versioning-configuration Status=Enabled
   ```

## Integration with Applications

### Web API Example

```python
from flask import Flask, request, jsonify
import subprocess
import json

app = Flask(__name__)

@app.route('/convert', methods=['POST'])
def convert():
    # Save uploaded file
    file = request.files['image']
    file.save('/tmp/input.png')
    
    # Run CLI with S3
    subprocess.run([
        'python', 'cli.py',
        '/tmp/input.png',
        '-o', '/tmp/output.svg',
        '--debug',
        '--s3-bucket', 'my-bucket'
    ])
    
    # Read extraction data
    with open('./debug_output/combined_extraction_data.json') as f:
        data = json.load(f)
    
    # Return S3 URLs
    return jsonify({
        'svg_url': '/tmp/output.svg',
        'extraction_data': data
    })
```

## See Also

- [S3_SETUP.md](../modal_deploy/S3_SETUP.md) - S3 setup for Modal deployment
- [IMPLEMENTATION_SUMMARY.md](../modal_deploy/IMPLEMENTATION_SUMMARY.md) - Technical details
- [README.md](README.md) - Main project documentation
