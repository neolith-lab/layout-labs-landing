# Pipeline Architecture

## High-Level Flow

```
Input Raster Image
        ↓
┌───────────────────┐
│ RasterToSVGConverter │
└───────────────────┘
        ↓
┌─────────────────────────────────────┐
│     STEP 1: Text Extraction         │
│  TextExtractor.extract_text_elements │
│  • Tesseract OCR                     │
│  • EasyOCR (fallback)               │
│  • Font size/weight/style detection │
│  • Color extraction                  │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│     STEP 2: Text Removal            │
│  BackgroundFiller.remove_and_fill    │
│  • Create mask from text bboxes     │
│  • Telea/Navier-Stokes inpainting   │
│  • Boundary smoothing               │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│     STEP 3-4: Image Detection       │
│  ImageDetector.detect_images         │
│  • Color variance analysis          │
│  • Edge density detection           │
│  • Texture complexity               │
│  • Photo vs graphic classification  │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│     STEP 4: Image Removal           │
│  BackgroundFiller.remove_and_fill    │
│  • Remove detected images           │
│  • Fill backgrounds                 │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│     STEP 6-8: Shape Detection       │
│  ShapeDetector.detect_shapes         │
│  • Adaptive thresholding            │
│  • Contour detection                │
│  • Shape classification:            │
│    - Circles                        │
│    - Rectangles                     │
│    - Ellipses                       │
│    - Polygons                       │
│    - Lines/Arrows                   │
│  • Color extraction                 │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│     STEP 7: Shape Removal           │
│  BackgroundFiller.remove_and_fill    │
│  • Remove detected shapes           │
│  • Get clean background             │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│     STEP 9-11: SVG Generation       │
│  SVGGenerator.generate_svg           │
│  • Create layered SVG:              │
│    Layer 1: Background              │
│    Layer 2: Shapes                  │
│    Layer 3: Images                  │
│    Layer 4: Text                    │
│  • Preserve colors & styles         │
└─────────────────────────────────────┘
        ↓
   Output SVG File
```

## Module Dependencies

```
raster_to_svg.py (Main Orchestrator)
    ├── text_extractor.py
    │   ├── utils.py
    │   ├── config.py
    │   ├── pytesseract
    │   └── easyocr
    │
    ├── background_filler.py
    │   ├── utils.py
    │   ├── config.py
    │   └── cv2 (OpenCV)
    │
    ├── image_detector.py
    │   ├── utils.py
    │   ├── config.py
    │   └── cv2 (OpenCV)
    │
    ├── shape_detector.py
    │   ├── utils.py
    │   ├── config.py
    │   └── cv2 (OpenCV)
    │
    └── svg_generator.py
        ├── text_extractor.py (TextElement)
        ├── image_detector.py (ImageElement)
        ├── shape_detector.py (ShapeElement)
        ├── utils.py
        ├── config.py
        └── svgwrite
```

## Data Flow

```
Input Image (np.ndarray)
        ↓
┌───────────────────┐
│  Text Elements    │
│  - text           │
│  - bbox           │
│  - font_size      │
│  - font_weight    │
│  - color          │
└───────────────────┘
        ↓
┌───────────────────┐
│  Image Elements   │
│  - image_data     │
│  - bbox           │
│  - is_photo       │
│  - dominant_colors│
└───────────────────┘
        ↓
┌───────────────────┐
│  Shape Elements   │
│  - shape_type     │
│  - contour        │
│  - bbox           │
│  - fill_color     │
│  - stroke_color   │
│  - properties     │
└───────────────────┘
        ↓
┌───────────────────┐
│  Background Image │
│  (np.ndarray)     │
└───────────────────┘
        ↓
    SVG Output
```

## Class Hierarchy

```
BoundingBox (utils.py)
    • x, y, w, h
    • x2, y2 (properties)
    • center (property)
    • area (property)

TextElement (text_extractor.py)
    • text: str
    • bbox: BoundingBox
    • font_family: str
    • font_size: int
    • font_weight: str
    • font_style: str
    • color: str
    • confidence: float

ImageElement (image_detector.py)
    • bbox: BoundingBox
    • image_data: np.ndarray
    • is_photo: bool
    • dominant_colors: List[Tuple]

ShapeElement (shape_detector.py)
    • shape_type: ShapeType (enum)
    • bbox: BoundingBox
    • contour: np.ndarray
    • fill_color: str
    • stroke_color: str
    • stroke_width: int
    • properties: Dict

ShapeType (Enum)
    • RECTANGLE
    • CIRCLE
    • ELLIPSE
    • POLYGON
    • LINE
    • ARROW
    • UNKNOWN
```

## Processing Pipeline Detail

```
┌─────────────────────────────────────────────────────────┐
│                    INPUT IMAGE                          │
│                  (800x600 pixels)                       │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              TEXT OCR & DETECTION                       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│  │Preprocess │→ │ Tesseract │→ │  Extract  │          │
│  │   Image   │  │    OCR    │  │   Font    │          │
│  └───────────┘  └───────────┘  │Properties │          │
│                                  └───────────┘          │
│  Output: TextElement[] (e.g., 15 elements)             │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              BACKGROUND FILLING #1                      │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│  │Create Mask│→ │  Inpaint  │→ │  Smooth   │          │
│  │from Bboxes│  │  (Telea)  │  │Boundaries │          │
│  └───────────┘  └───────────┘  └───────────┘          │
│  Output: Image with text removed                       │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              IMAGE DETECTION                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │   Color    │  │    Edge    │  │  Texture   │       │
│  │ Variance   │→ │  Density   │→ │  Analysis  │       │
│  └────────────┘  └────────────┘  └────────────┘       │
│           ↓                ↓              ↓             │
│  ┌────────────────────────────────────────┐            │
│  │    Merge & Validate Detections         │            │
│  └────────────────────────────────────────┘            │
│  Output: ImageElement[] (e.g., 3 images)               │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              BACKGROUND FILLING #2                      │
│  Remove images and fill backgrounds                     │
│  Output: Image with images removed                      │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              SHAPE DETECTION                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│  │Threshold  │→ │  Find     │→ │ Classify  │          │
│  │  Image    │  │ Contours  │  │  Shapes   │          │
│  └───────────┘  └───────────┘  └───────────┘          │
│           ↓                                             │
│  ┌───────────────────────────────────────┐             │
│  │Shape Classification:                  │             │
│  │ • Circle? (circularity ratio)        │             │
│  │ • Rectangle? (4 vertices + ratio)    │             │
│  │ • Ellipse? (aspect ratio)            │             │
│  │ • Line? (high aspect ratio)          │             │
│  │ • Polygon? (default)                 │             │
│  └───────────────────────────────────────┘             │
│  Output: ShapeElement[] (e.g., 8 shapes)               │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              BACKGROUND FILLING #3                      │
│  Remove shapes to get clean background                  │
│  Output: Clean background image                         │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              SVG GENERATION                             │
│  ┌─────────────────────────────────────┐               │
│  │ Create SVG (800x600)                │               │
│  │                                     │               │
│  │ Layer 1: Background                 │               │
│  │   <image> with base64 PNG           │               │
│  │                                     │               │
│  │ Layer 2: Shapes                     │               │
│  │   <circle>, <rect>, <polygon>...    │               │
│  │   (8 shape elements)                │               │
│  │                                     │               │
│  │ Layer 3: Images                     │               │
│  │   <image> with base64 PNG           │               │
│  │   (3 image elements)                │               │
│  │                                     │               │
│  │ Layer 4: Text                       │               │
│  │   <text> with font styling          │               │
│  │   (15 text elements)                │               │
│  └─────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                  OUTPUT SVG FILE                        │
│              (Fully Editable)                           │
└─────────────────────────────────────────────────────────┘
```

## Configuration Flow

```
config.py
    ├── OCR_CONFIG
    │   ├── tesseract_config
    │   ├── min_confidence
    │   ├── use_easyocr
    │   └── languages
    │
    ├── IMAGE_PROCESSING
    │   ├── background_fill_method
    │   ├── inpaint_radius
    │   ├── min_image_size
    │   └── blur_kernel_size
    │
    ├── SHAPE_DETECTION
    │   ├── min_area
    │   ├── epsilon_factor
    │   ├── min_circle_ratio
    │   └── min_rect_ratio
    │
    ├── SVG_OUTPUT
    │   ├── default_font_family
    │   ├── default_font_size
    │   ├── preserve_aspect_ratio
    │   └── layer_order
    │
    └── DEBUG
        ├── save_intermediate_steps
        ├── output_dir
        └── verbose
```

## Algorithm Details

### Text OCR
```
1. Preprocess image
   ├── Convert to grayscale
   ├── Bilateral filter (noise reduction)
   └── Adaptive threshold

2. Run OCR
   ├── Primary: Tesseract with custom config
   └── Fallback: EasyOCR if available

3. Extract font properties
   ├── Font size: height * 0.75 (pixel to point)
   ├── Font weight: pixel density analysis
   └── Font style: slant analysis

4. Extract colors
   ├── Convert to LAB color space
   ├── Separate foreground/background
   └── Get median color
```

### Image Detection
```
For each method:

Method 1: Color Variance
   ├── Convert to LAB
   ├── Calculate local variance (15x15 kernel)
   ├── Normalize to 0-255
   └── Threshold at 100

Method 2: Edge Density
   ├── Canny edge detection
   ├── Calculate local density (20x20 kernel)
   └── Threshold at 30

Method 3: Texture Complexity
   ├── Calculate local std dev
   ├── Normalize
   └── Threshold at 50

Final:
   ├── Merge all detections
   ├── Remove overlaps (IoU > 0.3)
   └── Validate size (> min_image_size)
```

### Shape Detection
```
1. Preprocess
   ├── Grayscale
   ├── Bilateral filter
   ├── Adaptive threshold
   └── Morphological cleanup

2. Find contours
   └── Filter by area > min_area

3. For each contour:
   ├── Approximate contour
   ├── Calculate properties
   └── Classify:
       ├── Circle? circularity > 0.7
       ├── Rectangle? 4 vertices + ratio > 0.85
       ├── Ellipse? aspect ratio 1.2-3.0
       ├── Line? aspect ratio > 5
       └── Polygon? (default)

4. Extract colors
   ├── Fill: erode mask, get interior pixels
   └── Stroke: contour pixels only
```

### Background Filling
```
1. Create mask from bboxes
2. Dilate mask (3x3 kernel)
3. Inpaint
   ├── Telea (fast, good for small regions)
   └── or Navier-Stokes (slower, better quality)
4. Smooth boundaries
   ├── Detect boundary region
   ├── Apply Gaussian blur
   └── Blend with original
```

## Performance Characteristics

```
Typical 800x600 infographic:

Step 1: Text OCR           →  2-4 seconds
Step 2: Text Removal       →  0.5-1 second
Step 3-4: Image Detection  →  1-2 seconds
Step 4: Image Removal      →  0.5-1 second
Step 6-8: Shape Detection  →  1-2 seconds
Step 7: Shape Removal      →  0.5-1 second
Step 9-11: SVG Generation  →  0.5-1 second

Total: ~7-13 seconds

Memory usage: ~100-300 MB
```
