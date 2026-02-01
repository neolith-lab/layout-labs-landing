# Excalidraw JSON S3 Upload - Implementation Summary

## Overview
The Excalidraw JSON output is now automatically uploaded to S3 along with all other extracted elements (text, images, containers, background) when using the `--excalidraw` flag.

## Changes Made

### 1. **main.py - Modal Function** (`convert_image_to_svg`)
**Location:** Lines 167-233

When `generate_excalidraw=True`, the function now:
1. Generates the Excalidraw JSON using `ExcalidrawConverter`
2. Saves it to a temporary file
3. Uploads to S3 at `{s3_prefix}/output.excalidraw`
4. Generates and returns the S3 URL in the response
5. Cleans up the temporary file

**Key Features:**
- Uses the same S3 bucket and prefix as other extraction elements
- Handles errors gracefully (continues even if S3 upload fails)
- Returns both the JSON data AND the S3 URL in the response

### 2. **main.py - Local Entrypoint** (`main`)
**Location:** Lines 341-367

Updated to display the S3 URL when Excalidraw JSON is generated:
- Saves Excalidraw JSON locally to `output.excalidraw`
- Displays both local path and S3 URL (if available)
- Provides clear feedback about where the file is stored

## Usage Examples

### Basic Excalidraw Generation with S3 Upload
```bash
modal run main.py --input-path input.png --excalidraw
```
**Output includes:**
```
✓ Excalidraw JSON generated with X elements
✓ Excalidraw JSON uploaded to S3: https://bucket.s3.region.amazonaws.com/extractions/uuid/output.excalidraw
✓ Excalidraw file saved locally: output.excalidraw
✓ Excalidraw file uploaded to S3: https://...
```

### With Custom S3 Bucket
```bash
modal run main.py --input-path input.png --excalidraw --s3-bucket my-custom-bucket
```

### Without Image Downloads (faster, smaller file)
```bash
modal run main.py --input-path input.png --excalidraw --no-download-images
```

## S3 Storage Structure

When processing an image, all elements are stored in S3 under a unique prefix:

```
s3://your-bucket/extractions/{unique-uuid}/
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
├── extraction_data.json          # Combined extraction metadata
└── output.excalidraw             # NEW: Excalidraw JSON file
```

## Response Structure

When `generate_excalidraw=True`, the response includes:

```python
{
    'success': True,
    'statistics': {
        'text_elements': 10,
        'logos': 0,
        'containers': 3,
        'images_in_containers': 2,
        'standalone_images': 1,
        'dimensions': (800, 600)
    },
    'extraction_data': {
        'metadata': {
            'timestamp': '2026-02-01T...',
            's3_bucket': 'layoutlabs-temp',
            's3_prefix': 'extractions/abc123...',
            'json_s3_url': 'https://...'
        },
        'stages': {...}
    },
    'excalidraw_json': {
        'type': 'excalidraw',
        'version': 2,
        'elements': [...],
        'files': {...}
    },
    'excalidraw_s3_url': 'https://bucket.s3.region.amazonaws.com/extractions/abc123/output.excalidraw'
}
```

## Benefits

1. **Centralized Storage**: All extraction outputs (including Excalidraw) in one S3 location
2. **Easy Sharing**: Share the S3 URL directly instead of transferring large JSON files
3. **Version Control**: Each extraction has a unique UUID prefix for tracking
4. **Integration Ready**: S3 URLs can be used directly in downstream applications
5. **Fallback Safety**: Local file is still saved even if S3 upload fails

## Error Handling

- If S3 upload fails, a warning is logged but the process continues
- The Excalidraw JSON is still returned in the response and saved locally
- This ensures the extraction pipeline doesn't fail due to S3 issues

## Environment Variables Required

For S3 uploads to work, ensure these are set:
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=ap-south-1  # Your bucket region
export AWS_S3_BUCKET=layoutlabs-temp  # Optional, can pass via CLI
```

## Next Steps / Future Enhancements

1. **Add signed URLs** for private S3 buckets with expiration
2. **Compress large Excalidraw files** before uploading (gzip)
3. **Add metadata tags** to S3 objects for better organization
4. **Implement cleanup** for old extractions (retention policy)
5. **Add download endpoint** in API to fetch from S3
