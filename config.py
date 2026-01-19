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
    'min_image_size': 20,  # LOWERED from 30 - catch smaller icons
    'min_icon_size': 20,   # LOWERED from 30 - detect even smaller icons
    'max_icon_size': 150,  # NEW: maximum size for line icon detection
    'blur_kernel_size': 5,
    # Container filtering heuristics - UPDATED thresholds
    'container_size_threshold': 0.02,  # LOWERED to 0.02 - Images > 2% of total area likely containers
    'container_min_unique_colors': 1500,  # RAISED to 1500 - containers can have gradients + embedded icons
    'container_edge_simplicity_threshold': 0.4,  # RAISED from 0.3
    'container_fill_ratio_threshold': 0.70,  # NEW: 70% uniform fill = likely container
    'container_score_threshold': 35,  # LOWERED from 50 - stricter filtering
    # Edge detection thresholds - LOWERED for better sensitivity
    'edge_density_threshold': 10,  # LOWERED from 15 - catch simpler icons
    # Detection method thresholds - LOWERED for better sensitivity (Plan A)
    'color_variance_threshold': 75,  # LOWERED from 100 - detect lower variance icons
    'texture_threshold': 35,  # LOWERED from 50 - detect smoother icons
    'min_contrast_std': 5,  # LOWERED from 10 - detect lower contrast icons
    'min_fill_ratio': 0.05,  # LOWERED from 0.1 - detect sparser icons
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
