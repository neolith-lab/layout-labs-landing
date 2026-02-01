```
EXCALIDRAW JSON S3 UPLOAD FLOW
================================

┌─────────────────────────────────────────────────────────────────────┐
│  User Command: modal run main.py --input-path img.png --excalidraw │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Modal Remote Function                            │
│                  convert_image_to_svg()                             │
├─────────────────────────────────────────────────────────────────────┤
│  1. Load image from URL/bytes                                       │
│  2. Run RasterToSVGConverter.convert()                              │
│     ├─ Extract text, images, containers, background                 │
│     ├─ Upload each element to S3                                    │
│     └─ Return extraction_data with S3 URLs                          │
│                                                                      │
│  3. IF generate_excalidraw=True:                                    │
│     ┌───────────────────────────────────────────────────────┐      │
│     │ ExcalidrawConverter.convert()                          │      │
│     │  ├─ Convert extraction_data to Excalidraw format       │      │
│     │  ├─ Download images from S3 URLs (if enabled)          │      │
│     │  ├─ Embed images as base64 in JSON                     │      │
│     │  └─ Return excalidraw_json object                      │      │
│     └───────────────────────────────────────────────────────┘      │
│                       │                                              │
│                       ▼                                              │
│     ┌───────────────────────────────────────────────────────┐      │
│     │ S3 Upload Process                                      │      │
│     │  1. Save excalidraw_json to temp file                  │      │
│     │  2. Generate S3 key:                                   │      │
│     │     {s3_prefix}/output.excalidraw                      │      │
│     │  3. Upload temp file to S3                             │      │
│     │  4. Generate public URL:                               │      │
│     │     https://bucket.s3.region.aws.com/{key}             │      │
│     │  5. Add URL to response['excalidraw_s3_url']           │      │
│     │  6. Clean up temp file                                 │      │
│     └───────────────────────────────────────────────────────┘      │
│                                                                      │
│  4. Return response with:                                           │
│     - extraction_data (with S3 URLs for all elements)               │
│     - excalidraw_json (full JSON object)                            │
│     - excalidraw_s3_url (S3 URL to uploaded file)                   │
│     - statistics                                                    │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Local Entrypoint main()                          │
├─────────────────────────────────────────────────────────────────────┤
│  1. Print extraction statistics                                     │
│  2. Save extraction_data.json locally                               │
│  3. IF excalidraw:                                                  │
│     - Save output.excalidraw locally                                │
│     - Print local file path                                         │
│     - Print S3 URL (if available)                                   │
│     - Print usage instructions                                      │
└─────────────────────────────────────────────────────────────────────┘


S3 STORAGE STRUCTURE
====================

s3://layoutlabs-temp/extractions/{unique-uuid}/
│
├── text_elements/
│   ├── text_000.png ────────────┐
│   ├── text_001.png             │
│   └── text_elements.json       │
│                                 │
├── image_elements/               │
│   ├── image_000.png ────────┐  │
│   ├── image_001.png         │  │
│   └── image_elements.json   │  │
│                              │  │
├── container_elements/        │  │
│   ├── container_000.png      │  │
│   ├── container_001.png      │  │
│   └── container_elements.json│  │
│                              │  │
├── background/                │  │
│   ├── background.png ────┐   │  │
│   └── background.json    │   │  │
│                          │   │  │
├── extraction_data.json   │   │  │
│   (References all above) │   │  │
│                          │   │  │
└── output.excalidraw ─────┼───┼──┼─ NEW: Uploaded Excalidraw JSON
    (Full Excalidraw JSON  │   │  │      with embedded images)
     with base64 images) ──┘   │  │
                               │  │
                               │  │
     ┌─────────────────────────┘  │
     │  Excalidraw downloads       │
     │  images from S3 URLs    ────┘
     │  and embeds as base64
     │  (if download_images=True)
     └────────────────────────────


EXAMPLE OUTPUT
==============

$ modal run main.py --input-path infographic.png --excalidraw

============================================================
RASTER TO SVG CONVERTER - Modal Deployment
Excalidraw JSON Generation Mode
============================================================

Processing image: infographic.png
✓ Excalidraw JSON generated with 47 elements
Uploading Excalidraw JSON to S3...
✓ Excalidraw JSON uploaded to S3: https://layoutlabs-temp.s3.ap-south-1.amazonaws.com/extractions/abc123.../output.excalidraw

============================================================
EXTRACTION COMPLETE
============================================================

Statistics:
  Text elements:       15
  Logos:               0
  Containers:          5
  Images (containers): 3
  Images (standalone): 2
  Dimensions:          1200x800

S3 Storage:
  Bucket: layoutlabs-temp
  Prefix: extractions/abc123def456...

✓ Extraction data saved to: extraction_data.json
✓ All elements uploaded to S3!

============================================================
EXCALIDRAW JSON GENERATED
============================================================
✓ Excalidraw file saved locally: output.excalidraw
✓ Excalidraw file uploaded to S3: https://layoutlabs-temp.s3.ap-south-1.amazonaws.com/extractions/abc123.../output.excalidraw

You can now:
  1. Open this file in your Excalidraw editor
  2. Click 'Load JSON' button
  3. Select: output.excalidraw

✓ Images embedded: 5 files (base64 encoded)
```
