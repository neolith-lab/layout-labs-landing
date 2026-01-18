"""
Configuration settings for the Raster to SVG converter
"""

# OCR Settings
OCR_CONFIG = {
    'tesseract_config': '--oem 3 --psm 6',
    'min_confidence': 60,
    'use_easyocr': True,  # Fallback to EasyOCR for better accuracy
    'languages': ['en'],
}

# Image Processing Settings
IMAGE_PROCESSING = {
    'background_fill_method': 'inpaint_telea',  # or 'inpaint_ns'
    'inpaint_radius': 5,
    'min_image_size': 100,  # minimum pixels for image detection
    'blur_kernel_size': 5,
}

# Shape Detection Settings
SHAPE_DETECTION = {
    'min_area': 100,
    'epsilon_factor': 0.02,
    'min_circle_ratio': 0.7,
    'min_rect_ratio': 0.85,
}

# SVG Output Settings
SVG_OUTPUT = {
    'default_font_family': 'Arial',
    'default_font_size': 12,
    'preserve_aspect_ratio': True,
    'layer_order': ['background', 'shapes', 'images', 'text'],
}

# Color Settings
COLOR_SETTINGS = {
    'color_tolerance': 30,
    'min_color_cluster_size': 50,
}

# Debug Settings
DEBUG = {
    'save_intermediate_steps': True,
    'output_dir': './debug_output',
    'verbose': True,
}
