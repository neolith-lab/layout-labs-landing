"""
Configuration settings for the Raster to SVG converter
"""

# OCR Settings
OCR_CONFIG = {
    'tesseract_config': '--oem 3 --psm 6',
    'min_confidence': 60,
    'use_easyocr': True,  # Fallback to EasyOCR for better accuracy
    'languages': ['en'],
    # Font size normalization settings
    'normalize_font_sizes': True,  # Enable font size standardization
    'font_size_cluster_tolerance': 0.35,  # 35% tolerance for clustering similar sizes
    'min_font_size': 6,   # Minimum font size in points
    'max_font_size': 200, # Maximum font size in points
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
    # Font embedding strategy:
    # 'google_fonts' - Use @import for Google Fonts (requires internet to view)
    # 'web_safe' - Use web-safe font fallbacks only (works offline, approximate look)
    # 'both' - Include both Google Fonts import AND web-safe fallbacks (recommended)
    # 'embedded' - Download and embed font files as base64 (largest file, fully portable)
    'font_embedding': 'both',
    # Whether to try embedding fonts as base64 (makes SVG self-contained but larger)
    'embed_font_files': False,
    # Text rendering mode:
    # 'svg' - Render text as SVG text elements (scalable but may have font issues)
    # 'image' - Render text as rasterized images (guaranteed font appearance, not scalable)
    'text_rendering': 'image',
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
