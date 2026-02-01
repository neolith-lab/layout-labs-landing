# Extraction Data Structure

## Overview
The `result['extraction_data']` contains the complete extraction results in a structured JSON format that's uploaded to S3 and also returned in the API response.

## Complete Structure

```javascript
{
  // METADATA
  "metadata": {
    "timestamp": "2026-02-01T12:34:56.789",
    "input_file": "/tmp/input.png",
    "output_file": null,  // SVG path if generated, null in JSON-only mode
    "s3_bucket": "layoutlabs-temp",
    "s3_prefix": "extractions/ea652face1e748d88360cf4aaa1f3500",
    "json_s3_url": "https://layoutlabs-temp.s3.ap-south-1.amazonaws.com/extractions/.../extraction_data.json"
  },
  
  // STATISTICS
  "statistics": {
    "text_elements": 45,
    "logos": 0,
    "containers": 9,
    "images_in_containers": 21,
    "standalone_images": 3,
    "shapes": 0,
    "dimensions": [1024, 1024]  // [width, height]
  },
  
  // STAGES - All detected elements organized by detection stage
  "stages": {
    
    // === TEXT DETECTION STAGE ===
    "text_detection": {
      "stage": "text_detection",
      "count": 45,
      "elements": [
        {
          "id": 0,
          "text": "Title Text Here",
          "bbox": {
            "x": 100,
            "y": 50,
            "width": 300,
            "height": 40,
            "x2": 400,
            "y2": 90
          },
          "font": {
            "family": "Arial",
            "size": 24,
            "weight": "bold",
            "style": "normal",
            "classified_font": "Inter",
            "classified_font_version": "Regular",
            "classification_confidence": 0.892,
            "fallback_fonts": ["Arial", "Helvetica", "sans-serif"],
            "line_height": 1.2,
            "letter_spacing": 0.0
          },
          "color": "#000000",
          "confidence": 0.95,
          "num_lines": 1
        },
        // ... more text elements
      ]
    },
    
    // === IMAGE DETECTION STAGE ===
    "image_detection": {
      "stage": "image_detection",
      "count": 24,
      "elements": [
        {
          "id": 0,
          "bbox": {
            "x": 150,
            "y": 200,
            "width": 200,
            "height": 150,
            "x2": 350,
            "y2": 350
          },
          "is_photo": true,
          "dominant_colors": [
            [45, 123, 200],   // RGB colors
            [230, 240, 250]
          ],
          "area": 30000,
          "aspect_ratio": 1.333,
          
          // BASE64 DATA - For direct embedding in Excalidraw
          "base64_data": "iVBORw0KGgoAAAANSUhEUgAA...(full base64 string)",
          "mime_type": "image/png",
          
          // S3 URL - For downloading/viewing
          "s3_url": "https://layoutlabs-temp.s3.ap-south-1.amazonaws.com/extractions/.../image_000.png"
        },
        // ... more image elements
      ]
    },
    
    // === CONTAINER DETECTION STAGE ===
    "container_detection": {
      "stage": "container_detection",
      "count": 9,
      "elements": [
        {
          "id": 0,
          "container_type": "RECTANGLE",
          "bbox": {
            "x": 50,
            "y": 100,
            "width": 400,
            "height": 300,
            "x2": 450,
            "y2": 400
          },
          
          // COLOR INFORMATION - Extracted from original image
          "fill_color": "#F5F5F5",      // Hex color of container background
          "stroke_color": "#CCCCCC",    // Hex color of container border
          "stroke_width": 2,
          "corner_radius": 8,
          
          "contains_image": true,
          "contains_text": true,
          "area": 120000,
          "aspect_ratio": 1.333,
          
          // Cropped container image (for reference/debugging)
          "cropped_image": "container_000.png",
          "s3_url": "https://layoutlabs-temp.s3.ap-south-1.amazonaws.com/extractions/.../container_000.png"
        },
        // ... more container elements
      ]
    },
    
    // === BACKGROUND EXTRACTION STAGE ===
    "background_extraction": {
      "stage": "background_extraction",
      "dimensions": {
        "width": 1024,
        "height": 1024
      },
      "average_color": {
        "rgb": [255, 255, 255],  // RGB
        "hex": "#FFFFFF"         // Hex
      },
      
      // BASE64 DATA - For direct embedding in Excalidraw
      "base64_data": "iVBORw0KGgoAAAANSUhEUgAA...(full base64 string)",
      "mime_type": "image/png",
      
      // S3 URL - For downloading/viewing
      "background_image": "background.png",
      "s3_url": "https://layoutlabs-temp.s3.ap-south-1.amazonaws.com/extractions/.../background.png"
    }
  }
}
```

## Key Features

### 1. **No Text Images**
- Text elements do NOT include cropped images
- Text is defined purely by metadata (content, font, size, color, etc.)
- This reduces storage and allows proper text editing in Excalidraw

### 2. **Base64 Embedded Images**
- All images include `base64_data` field with pre-encoded PNG data
- This allows direct embedding in Excalidraw without re-downloading from S3
- Both `base64_data` and `s3_url` are provided for flexibility

### 3. **Extracted Container Colors**
- `fill_color` and `stroke_color` are extracted from the original image
- Colors are in hex format (e.g., `#F5F5F5`)
- This ensures containers match the original design colors

### 4. **Dual Storage Model**
```
┌─────────────────────┐
│   Extraction Data   │
├─────────────────────┤
│                     │
│  1. JSON Metadata   │──► S3: extraction_data.json
│     - Text info     │
│     - Bboxes        │
│     - Colors        │
│     - Stats         │
│                     │
│  2. Base64 Images   │──► Embedded in JSON
│     - Images        │   (for Excalidraw)
│     - Background    │
│                     │
│  3. S3 URLs         │──► Reference to files
│     - Images        │   (for viewing/download)
│     - Containers    │
│     - Background    │
└─────────────────────┘
```

## Usage in Excalidraw Conversion

When `generate_excalidraw=True`, the Excalidraw converter:

1. **Reads from `stages`**:
   ```javascript
   text_elements = extraction_data['stages']['text_detection']['elements']
   containers = extraction_data['stages']['container_detection']['elements']
   images = extraction_data['stages']['image_detection']['elements']
   background = extraction_data['stages']['background_extraction']
   ```

2. **Uses base64 directly** (no S3 download):
   ```javascript
   // For images
   image_base64 = image['base64_data']
   mime_type = image['mime_type']
   
   // For background
   bg_base64 = background['base64_data']
   ```

3. **Extracts colors for containers**:
   ```javascript
   fill_color = container['fill_color']      // e.g., "#F5F5F5"
   stroke_color = container['stroke_color']  // e.g., "#CCCCCC"
   ```

4. **Renders text from metadata**:
   ```javascript
   text_content = text['text']
   font_size = text['font']['size']
   font_family = text['font']['family']
   color = text['color']
   ```

## API Response

When calling `convert_image_to_svg.remote()`, the response includes:

```javascript
{
  "success": true,
  
  "statistics": {
    "text_elements": 45,
    "logos": 0,
    "containers": 9,
    "images_in_containers": 21,
    "standalone_images": 3,
    "dimensions": [1024, 1024]
  },
  
  "extraction_data": {
    // Full structure shown above
  },
  
  // If generate_excalidraw=True:
  "excalidraw_json": {
    "type": "excalidraw",
    "version": 2,
    "elements": [...],  // All Excalidraw elements
    "files": {...}      // Embedded base64 images
  },
  
  "excalidraw_s3_url": "https://layoutlabs-temp.s3.ap-south-1.amazonaws.com/extractions/.../output.excalidraw"
}
```

## Benefits

1. **Efficient**: Base64 data embedded in JSON, no need to re-download from S3
2. **Complete**: Both metadata and binary data in one structure
3. **Flexible**: S3 URLs available for external access/viewing
4. **Accurate**: Extracted colors match the original design
5. **Text-friendly**: Text as metadata, not images (editable in Excalidraw)
