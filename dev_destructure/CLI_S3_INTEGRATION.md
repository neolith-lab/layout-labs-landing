# CLI S3 Integration - Summary

## Changes Made

Updated `/dev_destructure/cli.py` to support S3 uploads when running locally.

### New Command-Line Arguments

```python
--s3-bucket BUCKET_NAME      # S3 bucket for storing extracted elements
--s3-prefix PREFIX           # Custom S3 prefix/folder (optional, auto-generated if not provided)
```

### Updated Examples in Help Text

```bash
# Upload extracted elements to S3
python cli.py input.png -o output.svg --debug --s3-bucket my-bucket

# Upload to S3 with custom prefix
python cli.py input.png -o output.svg --debug --s3-bucket my-bucket --s3-prefix my-project/v1
```

### Converter Initialization

The converter is now created with S3 parameters:

```python
converter = RasterToSVGConverter(
    s3_bucket=args.s3_bucket,
    s3_prefix=args.s3_prefix
)
```

### Enhanced Output

The CLI now displays S3 information when uploads are enabled:

**Before conversion:**
```
S3 Storage enabled: s3://my-bucket/extractions/<auto>
```

**After conversion (single file mode):**
```
Debug output:    ./debug_output
S3 uploads:      s3://my-bucket/extractions/abc123.../
                 Check combined_extraction_data.json for all S3 URLs
```

**After conversion (batch mode):**
```
S3 uploads:      s3://my-bucket/extractions/abc123.../
                 Extracted elements uploaded for each image
```

## Usage Examples

### Basic S3 Upload

```bash
# Set AWS credentials first
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1

# Convert with S3 upload
python cli.py input.png -o output.svg --debug --s3-bucket my-bucket
```

**What happens:**
1. Converts `input.png` → `output.svg`
2. Extracts all elements (text, images, containers, background)
3. Saves files locally in `./debug_output/`
4. Uploads all files to S3
5. Generates JSON with S3 URLs

### Batch Processing with S3

```bash
python cli.py ./images -o ./output --batch --debug \
  --s3-bucket my-extractions \
  --s3-prefix batch-2024-01-27
```

### With Custom Debug Directory

```bash
python cli.py input.png -o output.svg --debug \
  --debug-dir ./my-debug \
  --s3-bucket my-bucket
```

## File Structure

### Local Files
```
./debug_output/
├── text_elements/
│   ├── text_000.png, text_001.png, ...
│   └── text_elements.json
├── image_elements/
│   ├── image_000.png, image_001.png, ...
│   └── image_elements.json
├── container_elements/
│   ├── container_000.png, container_001.png, ...
│   └── container_elements.json
├── background/
│   ├── background.png
│   └── background.json
└── combined_extraction_data.json  ← Master JSON with all S3 URLs
```

### S3 Files (Same Structure)
```
s3://my-bucket/
└── extractions/
    └── {uuid}/
        ├── text_elements/*.png
        ├── image_elements/*.png
        ├── container_elements/*.png
        └── background/*.png
```

## Accessing S3 URLs

The `combined_extraction_data.json` file contains all S3 URLs:

```json
{
  "stages": {
    "text_detection": {
      "elements": [
        {
          "text": "HELLO WORLD",
          "s3_url": "https://my-bucket.s3.amazonaws.com/.../text_000.png"
        }
      ]
    },
    "image_detection": {
      "elements": [
        {
          "s3_url": "https://my-bucket.s3.amazonaws.com/.../image_000.png"
        }
      ]
    },
    "container_detection": {
      "elements": [
        {
          "s3_url": "https://my-bucket.s3.amazonaws.com/.../container_000.png"
        }
      ]
    },
    "background_extraction": {
      "s3_url": "https://my-bucket.s3.amazonaws.com/.../background.png"
    }
  }
}
```

## Prerequisites

1. **Install boto3**:
   ```bash
   pip install boto3
   ```

2. **Configure AWS credentials** (one of):
   - Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - AWS CLI: `~/.aws/credentials`
   - IAM role (if on EC2)

3. **Create S3 bucket**:
   ```bash
   aws s3 mb s3://my-bucket
   ```

## Important Notes

1. **--debug flag required**: S3 upload only works when `--debug` is enabled (this triggers element extraction)

2. **Local files still saved**: Files are saved both locally AND to S3

3. **Unique UUID per conversion**: Each conversion gets a unique UUID prefix to avoid conflicts

4. **Failures are warnings**: If S3 upload fails, the conversion continues and a warning is logged

5. **Public vs Private**: By default, uploaded files may not be publicly accessible. Configure bucket policy if needed.

## Documentation

- **[CLI_S3_USAGE.md](CLI_S3_USAGE.md)** - Complete CLI usage guide with S3
- **[S3_SETUP.md](../modal_deploy/S3_SETUP.md)** - S3 configuration for Modal
- **[IMPLEMENTATION_SUMMARY.md](../modal_deploy/IMPLEMENTATION_SUMMARY.md)** - Technical details

## Testing

```bash
# Test without S3 (local only)
python cli.py input.png -o output.svg --debug

# Test with S3
python cli.py input.png -o output.svg --debug --s3-bucket test-bucket

# Check S3 uploads
aws s3 ls s3://test-bucket/extractions/ --recursive

# Download a specific file
aws s3 cp s3://test-bucket/extractions/{uuid}/text_elements/text_000.png ./test.png
```

## Benefits

✅ **Easy to use**: Just add `--s3-bucket` flag  
✅ **Flexible**: Optional custom prefix for organization  
✅ **Safe**: Failures don't stop conversion  
✅ **Complete**: All elements uploaded with URLs in JSON  
✅ **Scalable**: S3 handles storage, not local disk
