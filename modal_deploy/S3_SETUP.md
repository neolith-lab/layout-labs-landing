# S3 Setup for Modal Deployment

This document explains how to configure AWS S3 for storing extracted elements when using the Modal deployment.

## Prerequisites

1. An AWS account with S3 access
2. An S3 bucket for storing extracted elements
3. AWS credentials (Access Key ID and Secret Access Key)

## Setting up AWS Credentials in Modal

### Step 1: Create Modal Secret

Create a Modal secret named `aws-credentials` with your AWS credentials:

```bash
modal secret create aws-credentials \
  AWS_ACCESS_KEY_ID=<your-access-key-id> \
  AWS_SECRET_ACCESS_KEY=<your-secret-access-key> \
  AWS_DEFAULT_REGION=us-east-1 \
  AWS_S3_BUCKET=raster-to-svg-extractions
```

Replace the values with your actual AWS credentials and desired bucket name.

### Step 2: Create S3 Bucket

Create an S3 bucket to store the extracted elements:

```bash
aws s3 mb s3://raster-to-svg-extractions --region us-east-1
```

### Step 3: Configure Bucket Policy (Optional)

If you want the extracted elements to be publicly accessible, configure a bucket policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::raster-to-svg-extractions/*"
    }
  ]
}
```

Apply the policy:

```bash
aws s3api put-bucket-policy \
  --bucket raster-to-svg-extractions \
  --policy file://bucket-policy.json
```

## Usage

### Via Modal Function

When calling the Modal function, S3 upload will be enabled automatically if `debug=True`:

```python
import modal

app = modal.App.lookup("raster-to-svg-converter")
convert_fn = modal.Function.lookup("raster-to-svg-converter", "convert_image_to_svg")

# Call with S3 support (default)
result = convert_fn.remote(
    image_url="https://example.com/infographic.png",
    debug=True,  # Enables extraction and S3 upload
    return_json_only=True,  # Returns JSON with S3 URLs
    s3_bucket="raster-to-svg-extractions"  # Optional, uses env var by default
)

# Access the extraction data
extraction_data = result['extraction_data']

# Get S3 URLs for extracted elements
for text_elem in extraction_data['stages']['text_detection']['elements']:
    print(f"Text: {text_elem['text']}")
    print(f"S3 URL: {text_elem['s3_url']}")

for image_elem in extraction_data['stages']['image_detection']['elements']:
    print(f"Image S3 URL: {image_elem['s3_url']}")
```

### JSON Output Structure

The returned JSON includes S3 URLs for all extracted elements:

```json
{
  "success": true,
  "statistics": {
    "text_elements": 45,
    "containers": 9,
    "images_in_containers": 15,
    "standalone_images": 9,
    "dimensions": [1024, 1024]
  },
  "extraction_data": {
    "metadata": {
      "timestamp": "2026-01-27T10:30:00",
      "input_file": "input.png",
      "output_file": "output.svg",
      "debug_output_dir": "/tmp/debug_output"
    },
    "statistics": { ... },
    "stages": {
      "text_detection": {
        "stage": "text_detection",
        "count": 45,
        "elements": [
          {
            "id": 0,
            "text": "CAR MANUFACTURING PROCESS",
            "bbox": { "x": 100, "y": 50, "width": 300, "height": 40 },
            "font": { ... },
            "s3_url": "https://raster-to-svg-extractions.s3.amazonaws.com/extractions/abc123/text_elements/text_000.png"
          }
        ]
      },
      "image_detection": {
        "stage": "image_detection",
        "count": 24,
        "elements": [
          {
            "id": 0,
            "bbox": { ... },
            "s3_url": "https://raster-to-svg-extractions.s3.amazonaws.com/extractions/abc123/image_elements/image_000.png"
          }
        ]
      },
      "container_detection": {
        "stage": "container_detection",
        "count": 9,
        "elements": [
          {
            "id": 0,
            "container_type": "rectangle",
            "bbox": { ... },
            "s3_url": "https://raster-to-svg-extractions.s3.amazonaws.com/extractions/abc123/container_elements/container_000.png"
          }
        ]
      },
      "background_extraction": {
        "stage": "background_extraction",
        "dimensions": { "width": 1024, "height": 1024 },
        "average_color": { "rgb": [255, 255, 255], "hex": "#ffffff" },
        "s3_url": "https://raster-to-svg-extractions.s3.amazonaws.com/extractions/abc123/background/background.png"
      }
    }
  }
}
```

## S3 File Organization

Extracted elements are organized in S3 with the following structure:

```
s3://raster-to-svg-extractions/
└── extractions/
    └── {unique-id}/                    # UUID for each extraction
        ├── text_elements/
        │   ├── text_000.png
        │   ├── text_001.png
        │   └── ...
        ├── image_elements/
        │   ├── image_000.png
        │   ├── image_001.png
        │   └── ...
        ├── container_elements/
        │   ├── container_000.png
        │   ├── container_001.png
        │   └── ...
        └── background/
            └── background.png
```

## Cost Considerations

- **S3 Storage**: Standard storage costs apply (~$0.023/GB/month)
- **S3 Requests**: PUT requests cost ~$0.005 per 1,000 requests
- **Data Transfer**: Outbound data transfer costs apply if accessing from outside AWS

For a typical infographic with 50 elements, storage cost is negligible (<$0.01/month).

## Troubleshooting

### "Failed to upload to S3" warnings

- Verify AWS credentials are correct in Modal secret
- Check S3 bucket exists and is accessible
- Ensure boto3 is installed (should be automatic with Modal image)

### S3 URLs return 403 Forbidden

- Verify bucket policy allows public read access (if needed)
- Or use pre-signed URLs for temporary access

## Security Best Practices

1. **Use IAM roles** instead of access keys when possible
2. **Restrict bucket access** to specific IP ranges if needed
3. **Enable S3 versioning** to recover from accidental deletions
4. **Set up lifecycle policies** to automatically delete old extractions
5. **Use encryption** (SSE-S3 or SSE-KMS) for sensitive data

## Example: Cleanup Old Extractions

Set up a lifecycle policy to automatically delete extractions older than 30 days:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket raster-to-svg-extractions \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "Delete old extractions",
      "Status": "Enabled",
      "Prefix": "extractions/",
      "Expiration": { "Days": 30 }
    }]
  }'
```
