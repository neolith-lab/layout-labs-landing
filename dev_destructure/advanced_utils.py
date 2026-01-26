"""
Advanced utilities for raster to SVG conversion
Includes additional helper functions for complex operations
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from scipy import ndimage
from skimage import morphology, measure


def detect_text_baseline(text_region: np.ndarray) -> int:
    """
    Detect the baseline of text in a region
    
    Args:
        text_region: Image region containing text
    
    Returns:
        Y-coordinate of the baseline relative to region
    """
    if len(text_region.shape) == 3:
        gray = cv2.cvtColor(text_region, cv2.COLOR_BGR2GRAY)
    else:
        gray = text_region
    
    # Threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find bottom-most pixels row by row
    row_sums = np.sum(binary, axis=1)
    
    # Find the lowest row with significant pixels
    threshold = np.max(row_sums) * 0.1
    baseline = len(row_sums) - 1
    
    for i in range(len(row_sums) - 1, -1, -1):
        if row_sums[i] > threshold:
            baseline = i
            break
    
    return baseline


def enhance_image_for_ocr(image: np.ndarray) -> np.ndarray:
    """
    Enhance image quality for better OCR results
    
    Args:
        image: Input image
    
    Returns:
        Enhanced image
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray)
    
    # Increase contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    
    # Sharpen
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    
    return sharpened


def extract_color_palette(image: np.ndarray, n_colors: int = 8) -> List[Tuple[int, int, int]]:
    """
    Extract color palette from image using k-means clustering
    
    Args:
        image: Input image
        n_colors: Number of colors to extract
    
    Returns:
        List of RGB color tuples
    """
    # Reshape image to list of pixels
    pixels = image.reshape(-1, 3).astype(np.float32)
    
    # K-means clustering
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, centers = cv2.kmeans(pixels, n_colors, None, criteria, 10,
                                    cv2.KMEANS_PP_CENTERS)
    
    # Sort by frequency
    unique, counts = np.unique(labels, return_counts=True)
    sorted_indices = np.argsort(-counts)
    
    palette = []
    for idx in sorted_indices:
        color = centers[unique[idx]].astype(int)
        palette.append(tuple(color[::-1]))  # BGR to RGB
    
    return palette


def simplify_path(points: np.ndarray, tolerance: float = 1.0) -> np.ndarray:
    """
    Simplify a path using the Ramer-Douglas-Peucker algorithm
    
    Args:
        points: Array of points
        tolerance: Simplification tolerance
    
    Returns:
        Simplified array of points
    """
    if len(points) < 3:
        return points
    
    # Use cv2.approxPolyDP for simplification
    epsilon = tolerance
    simplified = cv2.approxPolyDP(points, epsilon, closed=False)
    
    return simplified


def detect_gradients(image: np.ndarray) -> np.ndarray:
    """
    Detect color gradients in image
    
    Args:
        image: Input image
    
    Returns:
        Gradient magnitude map
    """
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    
    gradient_map = np.zeros(image.shape[:2], dtype=np.float32)
    
    # Calculate gradients for each channel
    for i in range(3):
        channel = lab[:, :, i].astype(np.float32)
        
        # Sobel gradients
        grad_x = cv2.Sobel(channel, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(channel, cv2.CV_32F, 0, 1, ksize=3)
        
        # Magnitude
        magnitude = np.sqrt(grad_x**2 + grad_y**2)
        gradient_map += magnitude
    
    # Normalize
    gradient_map = cv2.normalize(gradient_map, None, 0, 255, cv2.NORM_MINMAX)
    
    return gradient_map.astype(np.uint8)


def find_connected_components(binary_image: np.ndarray, 
                             min_size: int = 50) -> List[np.ndarray]:
    """
    Find connected components in binary image
    
    Args:
        binary_image: Binary input image
        min_size: Minimum component size
    
    Returns:
        List of component masks
    """
    # Label connected components
    labeled = measure.label(binary_image)
    
    components = []
    for region in measure.regionprops(labeled):
        if region.area >= min_size:
            # Create mask for this component
            mask = (labeled == region.label).astype(np.uint8) * 255
            components.append(mask)
    
    return components


def calculate_skeleton(binary_image: np.ndarray) -> np.ndarray:
    """
    Calculate morphological skeleton of binary image
    
    Args:
        binary_image: Binary input image
    
    Returns:
        Skeleton image
    """
    # Normalize to 0-1
    binary = (binary_image > 0).astype(np.uint8)
    
    # Calculate skeleton
    skeleton = morphology.skeletonize(binary)
    
    return (skeleton * 255).astype(np.uint8)


def fit_bezier_curve(points: np.ndarray, n_control_points: int = 4) -> np.ndarray:
    """
    Fit a Bezier curve to a set of points
    
    Args:
        points: Array of points
        n_control_points: Number of control points
    
    Returns:
        Array of control points for Bezier curve
    """
    # Simple implementation: select evenly spaced points
    if len(points) < n_control_points:
        return points
    
    indices = np.linspace(0, len(points) - 1, n_control_points, dtype=int)
    control_points = points[indices]
    
    return control_points


def remove_small_objects(binary_image: np.ndarray, min_size: int = 64) -> np.ndarray:
    """
    Remove small objects from binary image
    
    Args:
        binary_image: Binary input image
        min_size: Minimum object size to keep
    
    Returns:
        Cleaned binary image
    """
    # Normalize to boolean
    binary = (binary_image > 0).astype(bool)
    
    # Remove small objects
    cleaned = morphology.remove_small_objects(binary, min_size=min_size)
    
    return (cleaned * 255).astype(np.uint8)


def fill_holes(binary_image: np.ndarray) -> np.ndarray:
    """
    Fill holes in binary image
    
    Args:
        binary_image: Binary input image
    
    Returns:
        Image with holes filled
    """
    # Use morphological closing
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    closed = cv2.morphologyEx(binary_image, cv2.MORPH_CLOSE, kernel)
    
    # Fill remaining holes using flood fill
    filled = closed.copy()
    h, w = filled.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(filled, mask, (0, 0), 255)
    filled_inv = cv2.bitwise_not(filled)
    result = closed | filled_inv
    
    return result


def estimate_rotation_angle(image: np.ndarray) -> float:
    """
    Estimate rotation angle of document/infographic
    
    Args:
        image: Input image
    
    Returns:
        Rotation angle in degrees
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Hough line transform
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
    
    if lines is None or len(lines) == 0:
        return 0.0
    
    # Calculate dominant angle
    angles = []
    for rho, theta in lines[:, 0]:
        angle = theta * 180 / np.pi
        # Normalize to [-45, 45]
        if angle > 45:
            angle -= 90
        elif angle < -45:
            angle += 90
        angles.append(angle)
    
    # Return median angle
    return np.median(angles)


def deskew_image(image: np.ndarray, angle: Optional[float] = None) -> np.ndarray:
    """
    Deskew (straighten) an image
    
    Args:
        image: Input image
        angle: Rotation angle (auto-detect if None)
    
    Returns:
        Deskewed image
    """
    if angle is None:
        angle = estimate_rotation_angle(image)
    
    # Get image center
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    
    # Rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Rotate
    rotated = cv2.warpAffine(image, M, (w, h), 
                            flags=cv2.INTER_CUBIC,
                            borderMode=cv2.BORDER_REPLICATE)
    
    return rotated
