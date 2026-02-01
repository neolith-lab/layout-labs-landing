# Excalidraw Conversion - Fixes Applied ✓

## Issue Resolved

**Error:** `An unexpected error occurred - 'extraction_data'`

**Root Cause:** The Excalidraw converter was expecting data in dictionary format, but the extraction pipeline returns Python objects (dataclasses) with a different structure.

---

## Changes Made

### 1. **CLI Integration Fix** (`cli.py`)

**Problem:** CLI was trying to access `result['extraction_data']` which doesn't exist.

**Fix:** Changed to use `result['elements']` which contains the actual extracted data:
```python
# Before (❌ Wrong)
excalidraw_path = excalidraw_converter.convert_to_file(
    extraction_data=result['extraction_data'],  # ❌ doesn't exist
    ...
)

# After (✓ Correct)
excalidraw_path = excalidraw_converter.convert_to_file(
    extraction_data=result['elements'],  # ✓ correct key
    ...
)
```

### 2. **Data Format Compatibility** (`excalidraw_converter.py`)

**Problem:** Converter expected dict keys but received Python objects with attributes.

**Fix:** Added universal accessor method that works with both formats:
```python
def _get_value(self, obj: Any, key: str, default: Any = None) -> Any:
    """Get value from either a dict or an object attribute"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    else:
        return getattr(obj, key, default)
```

### 3. **Element Structure Mapping** (`excalidraw_converter.py`)

**Problem:** Converter expected keys like `images` and `text_elements`, but extraction returns `images_in_containers`, `standalone_images`, and `text`.

**Fix:** Added fallback logic to support both formats:
```python
# Support both formats for images
images = extraction_data.get('images', [])
if not images:
    images = extraction_data.get('images_in_containers', []) + extraction_data.get('standalone_images', [])

# Support both formats for text
text_elements = extraction_data.get('text_elements', extraction_data.get('text', []))
```

### 4. **BoundingBox Object Handling** (`excalidraw_converter.py`)

**Problem:** Extraction returns `BoundingBox` objects, not dicts or lists.

**Fix:** Added handling for object attributes:
```python
# Handle BoundingBox object
if hasattr(bbox, 'x'):
    x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
# Handle dict format
elif isinstance(bbox, dict):
    x = bbox.get('x', 0)
    y = bbox.get('y', 0)
    w = bbox.get('width', bbox.get('w', 100))
    h = bbox.get('height', bbox.get('h', 100))
# Handle list format
elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
    x, y, w, h = bbox
    # Check if [x1, y1, x2, y2] format
    if w > 10000 or h > 10000:
        x, y, x2, y2 = bbox
        w, h = x2 - x, y2 - y
```

---

## ✓ Current Status

**Conversion works!** But with a caveat:

### Without S3 (Current Test)
- ✅ Containers: **9 converted**
- ✅ Text: **45 elements converted**
- ⚠️ Images: **24 skipped** (no S3 URLs)

### Output File
- **File created:** `output.excalidraw` (48KB)
- **Format:** Valid Excalidraw JSON
- **Elements:** 54 total (9 containers + 45 text)

---

## 🚀 How to Use Properly

### Option 1: With Images (Full Conversion)

```bash
# Upload extracted elements to S3 and embed images
python3 cli.py input.png \
  --excalidraw \
  --s3-bucket layoutlabs-temp \
  --debug

# This will:
# 1. Extract all elements
# 2. Upload images to S3
# 3. Download images from S3
# 4. Encode as base64
# 5. Embed in Excalidraw JSON
```

**Output:** Complete Excalidraw file with embedded images

### Option 2: Without Images (Fast Mode)

```bash
# Skip image downloads for faster processing
python3 cli.py input.png \
  --excalidraw \
  --no-download-images \
  --debug

# This will:
# 1. Extract all elements
# 2. Generate containers and text
# 3. Skip image downloads
```

**Output:** Excalidraw file with containers and text only (what you have now)

### Option 3: S3 + No Download (Fastest)

```bash
# Store in S3 but don't embed in Excalidraw
python3 cli.py input.png \
  --excalidraw \
  --s3-bucket layoutlabs-temp \
  --no-download-images \
  --debug

# This will:
# 1. Extract all elements
# 2. Upload images to S3 (saved for later)
# 3. Generate Excalidraw with containers and text
# 4. Image S3 URLs stored in debug JSON
```

**Output:** Fast conversion + S3 backup of images

---

## 📊 Verification

### Check Your Current Output

```bash
# Verify the file structure
cat output.excalidraw | head -100

# Check element count
grep '"type":' output.excalidraw | wc -l
# Should show: 54 elements

# Check what types of elements
grep -o '"type": "[^"]*"' output.excalidraw | sort | uniq -c
# Should show:
#   9 "type": "rectangle"  (containers)
#  45 "type": "text"       (text elements)
```

### Load in Excalidraw Editor

1. Navigate to your infogen app
2. Go to the Excalidraw Editor page
3. Click "Load JSON" button
4. Select: `output.excalidraw`
5. Verify:
   - ✓ 9 rectangles (containers) appear
   - ✓ 45 text elements appear
   - ⚠️ Images missing (because no S3 URLs)

---

## 🎯 Next Steps

### To Get Images Working

**You need AWS credentials set up:**

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=ap-south-1

# Then run with S3
python3 cli.py input.png \
  --excalidraw \
  --s3-bucket layoutlabs-temp \
  --debug
```

### To Test Without AWS

**Use the current output (no images):**

```bash
# Generate without images
python3 cli.py input.png \
  --excalidraw \
  --no-download-images

# Load in Excalidraw to test text and containers
```

---

## 📋 Complete Example Workflow

### Development Mode (Fast, No Images)

```bash
cd /Users/stav.42/neolith/layout-labs-landing/dev_destructure

# Convert to Excalidraw (fast mode)
python3 cli.py input.png \
  -o test.excalidraw \
  --excalidraw \
  --no-download-images \
  --debug

# Output files:
# - test.excalidraw (Excalidraw JSON)
# - debug_output/combined_extraction_data.json (full extraction data)
# - debug_output/text_elements/ (text crops)
# - debug_output/image_elements/ (image crops)
# - debug_output/container_elements/ (container crops)
```

### Production Mode (With Images)

```bash
cd /Users/stav.42/neolith/layout-labs-landing/dev_destructure

# Set AWS credentials
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=ap-south-1

# Convert with full image embedding
python3 cli.py input.png \
  -o production.excalidraw \
  --excalidraw \
  --s3-bucket layoutlabs-temp \
  --debug

# Output files:
# - production.excalidraw (with embedded images)
# - S3: s3://layoutlabs-temp/extractions/[uuid]/* (uploaded elements)
# - debug_output/* (local debug data)
```

---

## 🔧 Debugging

### If Conversion Fails

**Check the logs:**
```bash
python3 cli.py input.png --excalidraw --debug 2>&1 | tee conversion.log
```

**Common issues:**

1. **"Image missing s3_url"**
   - Solution: Use `--s3-bucket` flag or `--no-download-images`

2. **AWS credentials error**
   - Solution: Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`

3. **"Failed to download image"**
   - Check S3 bucket permissions
   - Check network connectivity
   - Verify S3 URLs are public or credentials have access

### Inspect the JSON

```bash
# Pretty print the JSON
python3 -m json.tool output.excalidraw | head -200

# Check specific element types
jq '.elements[] | select(.type == "text") | .text' output.excalidraw
jq '.elements[] | select(.type == "rectangle") | {x, y, width, height}' output.excalidraw
```

---

## ✅ Summary

**What's Fixed:**
- ✓ Error: `'extraction_data'` resolved
- ✓ CLI integration working
- ✓ Object/dict compatibility added
- ✓ BoundingBox object handling
- ✓ Element structure mapping

**What Works:**
- ✓ Containers → Excalidraw rectangles
- ✓ Text → Excalidraw text elements
- ✓ File generation (valid JSON)
- ⏳ Images (requires S3 setup)

**Current Output:**
- File: `output.excalidraw` (48KB)
- Elements: 54 (9 containers + 45 text)
- Ready to load in Excalidraw!

**To Enable Images:**
```bash
# Set up AWS credentials
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret  
export AWS_REGION=ap-south-1

# Run with S3
python3 cli.py input.png --excalidraw --s3-bucket layoutlabs-temp
```

---

**Status: ✅ WORKING** (Images require S3 configuration)
