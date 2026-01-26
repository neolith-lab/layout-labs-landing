# Font Size Standardization Guide

## Overview

The font size calculation system ensures that text elements are sized consistently relative to the overall image dimensions. This prevents issues where the same visual text appears with different font sizes due to slight variations in bounding box detection.

## How It Works

### 1. Font Size Estimation

The system calculates font sizes based on bounding box height:

```python
# Adjust for multi-line text (based on OCR newlines)
line_height = bbox_height / num_lines

# Account for line spacing (typically 1.2x font size)
char_height = line_height / 1.2

# Base font size (at 72 DPI)
base_font_size = int(char_height)
```

### 2. Clustering-Based Normalization

Font sizes are then **clustered** to group similar sizes together:

```python
# Two sizes are "similar" if within 25% of each other
tolerance = 0.25

# Example: sizes [14, 15, 16, 28, 30] would cluster as:
# Cluster 1: [14, 15, 16] -> 15pt (median)
# Cluster 2: [28, 30] -> 29pt (median)
```

This ensures text that visually appears the same size gets exactly the same font size value.

### 3. Configuration

You can customize font size calculation in `config.py`:

```python
OCR_CONFIG = {
    # Enable/disable normalization
    'normalize_font_sizes': True,
    
    # Tolerance for clustering similar sizes (25% = sizes within 25% are grouped)
    'font_size_cluster_tolerance': 0.25,
    
    # Min/max bounds
    'min_font_size': 6,
    'max_font_size': 200,
}
```

## Example

For an infographic with these text elements:

| Text | Raw Size | Cluster | Normalized |
|------|----------|---------|------------|
| "TECHNOLOGY IN MANUFACTURING" | 32pt | A | 30pt |
| "SUSTAINABILITY IN AUTOMOTIVE" | 28pt | A | 30pt |
| "Robotics: Precision assembly" | 15pt | B | 15pt |
| "Recycled Materials" | 14pt | B | 15pt |
| "Electric Car Production" | 16pt | B | 15pt |
| "Renewable Energy" | 14pt | B | 15pt |

All the body text (14-16pt) clusters together and gets normalized to **15pt**.
All the headings (28-32pt) cluster together and get normalized to **30pt**.

## Benefits

1. **Consistency**: Same visual text gets same font size regardless of image resolution
2. **Hierarchy Preservation**: Relative importance of text elements is maintained
3. **Standardization**: Limited number of distinct font sizes (cleaner design)
4. **Multi-line Handling**: Correctly calculates font size for paragraphs
5. **Configurable**: Easily adjust tiers and reference resolution

## API Usage

### Automatic (Recommended)

Font size normalization happens automatically during text extraction:

```python
from text_extractor import TextExtractor

extractor = TextExtractor()
text_elements = extractor.extract_text_elements(image)

# Font sizes are already normalized
for elem in text_elements:
    print(f"{elem.text}: {elem.font_size}pt")
```

### Manual Control

You can disable normalization if needed:

```python
config = OCR_CONFIG.copy()
config['normalize_font_sizes'] = False

extractor = TextExtractor(config)
text_elements = extractor.extract_text_elements(image)

# Font sizes are raw estimates only
```

## Testing

Run the test script to see normalization in action:

```bash
python test_font_normalization.py
```

This will show how font sizes are calculated and normalized across different image resolutions.

## Technical Details

### Why Use Diagonal as Reference?

The diagonal dimension provides a single metric that accounts for both width and height:
- Handles both landscape and portrait orientations
- More stable than using just width or height alone
- Commonly used in screen size measurements (e.g., "27-inch monitor")

### Why 1920x1080 as Standard?

Full HD (1920x1080) is chosen as the reference because:
- Most common desktop/web resolution
- Good balance between mobile and desktop
- Industry standard for web design

### Tier Assignment Logic

Elements are assigned to tiers based on their ratio to the median font size:

```
ratio >= 2.0  → Extra Large
ratio >= 1.5  → Large
ratio >= 1.15 → Medium Large
ratio >= 0.9  → Medium (baseline)
ratio >= 0.75 → Small
ratio < 0.75  → Extra Small
```

The median is used (rather than mean) because it's more robust to outliers.

## Troubleshooting

### Problem: All text has the same font size

**Solution**: Check if you have enough variation in your original text sizes. The normalization preserves relative sizes, but if everything is similar, it will normalize to the same tier.

### Problem: Font sizes seem too small/large

**Solution**: Adjust the tier multipliers in config:

```python
'font_size_tiers': {
    'extra_large': 3.0,  # Increase for larger headings
    'large': 2.2,
    'medium_large': 1.6,
    'medium': 1.0,
    'small': 0.8,
    'extra_small': 0.6
}
```

### Problem: Need different reference resolution

**Solution**: Change the reference resolution in config:

```python
# For 4K-focused designs
'reference_resolution': (3840, 2160)

# For mobile-first designs
'reference_resolution': (1080, 1920)
```

## Future Enhancements

Potential improvements for future versions:

1. **Responsive Breakpoints**: Different normalization rules for mobile/tablet/desktop
2. **Font Family-Specific Adjustment**: Account for different x-heights across fonts
3. **Optical Sizing**: Adjust based on viewing distance assumptions
4. **Machine Learning**: Train a model to predict optimal font sizes from context
