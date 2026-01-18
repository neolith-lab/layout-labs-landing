# API Reference

## Main Classes

### RasterToSVGConverter

Main orchestrator class for the conversion pipeline.

```python
from raster_to_svg import RasterToSVGConverter

converter = RasterToSVGConverter()
```

#### Methods

##### `convert(input_path: str, output_path: str, convert_images_to_svg: bool = False) -> Dict`

Convert a single raster image to SVG.

**Parameters:**
- `input_path` (str): Path to input image file
- `output_path` (str): Path for output SVG file
- `convert_images_to_svg` (bool): Whether to vectorize embedded images (experimental)

**Returns:**
- Dictionary with keys:
  - `success` (bool): Whether conversion succeeded
  - `output_path` (str): Path to generated SVG
  - `statistics` (dict): Conversion statistics
  - `elements` (dict): Extracted elements

**Example:**
```python
result = converter.convert('input.png', 'output.svg')
print(f"Found {result['statistics']['text_elements']} text elements")
```

##### `convert_batch(input_dir: str, output_dir: str, pattern: str = '*.png') -> Dict`

Convert multiple images in batch.

**Parameters:**
- `input_dir` (str): Directory containing input images
- `output_dir` (str): Directory for output SVG files
- `pattern` (str): Glob pattern for files to process

**Returns:**
- Dictionary with batch results

---

### TextExtractor

Extract text from images using OCR.

```python
from text_extractor import TextExtractor

extractor = TextExtractor()
```

#### Methods

##### `extract_text_elements(image: np.ndarray) -> List[TextElement]`

Extract all text elements from an image.

**Parameters:**
- `image` (np.ndarray): Input image in BGR format

**Returns:**
- List of `TextElement` objects

---

### ImageDetector

Detect embedded images within infographics.

```python
from image_detector import ImageDetector

detector = ImageDetector()
```

#### Methods

##### `detect_images(image: np.ndarray, text_bboxes: List[BoundingBox] = None, shape_bboxes: List[BoundingBox] = None) -> List[ImageElement]`

Detect embedded images.

**Parameters:**
- `image` (np.ndarray): Input image
- `text_bboxes` (List[BoundingBox]): Text regions to exclude
- `shape_bboxes` (List[BoundingBox]): Shape regions to exclude

**Returns:**
- List of `ImageElement` objects

---

### ShapeDetector

Detect and classify geometric shapes.

```python
from shape_detector import ShapeDetector

detector = ShapeDetector()
```

#### Methods

##### `detect_shapes(image: np.ndarray, text_bboxes: List[BoundingBox] = None, image_bboxes: List[BoundingBox] = None) -> List[ShapeElement]`

Detect geometric shapes.

**Parameters:**
- `image` (np.ndarray): Input image
- `text_bboxes` (List[BoundingBox]): Text regions to exclude
- `image_bboxes` (List[BoundingBox]): Image regions to exclude

**Returns:**
- List of `ShapeElement` objects

---

### BackgroundFiller

Fill backgrounds after element removal.

```python
from background_filler import BackgroundFiller

filler = BackgroundFiller()
```

#### Methods

##### `remove_and_fill(image: np.ndarray, bboxes: List[BoundingBox], label_filter: str = None) -> np.ndarray`

Remove elements and fill their backgrounds.

**Parameters:**
- `image` (np.ndarray): Input image
- `bboxes` (List[BoundingBox]): Regions to remove
- `label_filter` (str): Only remove boxes with this label

**Returns:**
- Image with elements removed and background filled

---

### SVGGenerator

Generate SVG from detected elements.

```python
from svg_generator import SVGGenerator

generator = SVGGenerator()
```

#### Methods

##### `generate_svg(width: int, height: int, background_image: np.ndarray = None, text_elements: List[TextElement] = None, image_elements: List[ImageElement] = None, shape_elements: List[ShapeElement] = None, output_path: str = 'output.svg') -> str`

Generate complete SVG from all elements.

**Parameters:**
- `width` (int): SVG canvas width
- `height` (int): SVG canvas height
- `background_image` (np.ndarray): Background image
- `text_elements` (List[TextElement]): Text elements
- `image_elements` (List[ImageElement]): Image elements
- `shape_elements` (List[ShapeElement]): Shape elements
- `output_path` (str): Output file path

**Returns:**
- Path to generated SVG file

---

## Data Classes

### BoundingBox

Represents a rectangular bounding box.

**Attributes:**
- `x` (int): X coordinate
- `y` (int): Y coordinate
- `w` (int): Width
- `h` (int): Height
- `label` (str): Label/category
- `confidence` (float): Detection confidence

**Properties:**
- `x2`: Right edge coordinate
- `y2`: Bottom edge coordinate
- `center`: Center point (x, y)
- `area`: Area in pixels

---

### TextElement

Represents extracted text with styling.

**Attributes:**
- `text` (str): The text content
- `bbox` (BoundingBox): Bounding box
- `font_family` (str): Font family name
- `font_size` (int): Font size in pixels
- `font_weight` (str): 'normal' or 'bold'
- `font_style` (str): 'normal' or 'italic'
- `color` (str): Text color (hex format)
- `confidence` (float): OCR confidence

---

### ImageElement

Represents a detected image.

**Attributes:**
- `bbox` (BoundingBox): Bounding box
- `image_data` (np.ndarray): Image pixels
- `is_photo` (bool): Whether it's a photo or graphic
- `dominant_colors` (List[Tuple]): Dominant colors

---

### ShapeElement

Represents a detected shape.

**Attributes:**
- `shape_type` (ShapeType): Type of shape
- `bbox` (BoundingBox): Bounding box
- `contour` (np.ndarray): Shape contour
- `fill_color` (str): Fill color (hex)
- `stroke_color` (str): Stroke color (hex)
- `stroke_width` (int): Stroke width
- `properties` (Dict): Additional properties

---

### ShapeType (Enum)

Shape type enumeration.

**Values:**
- `RECTANGLE`: Rectangle or square
- `CIRCLE`: Circle
- `ELLIPSE`: Ellipse
- `POLYGON`: Polygon
- `LINE`: Line
- `ARROW`: Arrow
- `UNKNOWN`: Unknown shape

---

## Utility Functions

### `rgb_to_hex(rgb: Tuple[int, int, int]) -> str`

Convert RGB tuple to hex color string.

### `hex_to_rgb(hex_color: str) -> Tuple[int, int, int]`

Convert hex color string to RGB tuple.

### `calculate_iou(bbox1: BoundingBox, bbox2: BoundingBox) -> float`

Calculate Intersection over Union between two bounding boxes.

### `merge_overlapping_boxes(bboxes: List[BoundingBox], iou_threshold: float = 0.3) -> List[BoundingBox]`

Merge overlapping bounding boxes.

### `inpaint_image(image: np.ndarray, mask: np.ndarray, method: str = 'telea', radius: int = 5) -> np.ndarray`

Inpaint image using specified method.

---

## Configuration

Import and modify configuration:

```python
from config import OCR_CONFIG, IMAGE_PROCESSING, SHAPE_DETECTION, SVG_OUTPUT, DEBUG

# Modify OCR settings
OCR_CONFIG['min_confidence'] = 70
OCR_CONFIG['use_easyocr'] = True

# Modify shape detection
SHAPE_DETECTION['min_area'] = 200

# Enable debug mode
DEBUG['save_intermediate_steps'] = True
DEBUG['output_dir'] = './my_debug'
```

### Configuration Options

#### OCR_CONFIG
- `tesseract_config`: Tesseract configuration string
- `min_confidence`: Minimum OCR confidence (0-100)
- `use_easyocr`: Use EasyOCR as fallback
- `languages`: List of languages

#### IMAGE_PROCESSING
- `background_fill_method`: 'inpaint_telea' or 'inpaint_ns'
- `inpaint_radius`: Radius for inpainting
- `min_image_size`: Minimum image size in pixels
- `blur_kernel_size`: Blur kernel size

#### SHAPE_DETECTION
- `min_area`: Minimum shape area
- `epsilon_factor`: Contour approximation factor
- `min_circle_ratio`: Minimum circularity ratio
- `min_rect_ratio`: Minimum rectangularity ratio

#### SVG_OUTPUT
- `default_font_family`: Default font family
- `default_font_size`: Default font size
- `preserve_aspect_ratio`: Preserve aspect ratio
- `layer_order`: Order of layers

#### DEBUG
- `save_intermediate_steps`: Save debug images
- `output_dir`: Debug output directory
- `verbose`: Verbose logging
