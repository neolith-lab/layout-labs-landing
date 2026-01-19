# Google Fonts Embedding in SVG

## Overview
The SVG generator now automatically embeds Google Fonts to ensure text renders correctly on any system, even if the fonts aren't installed locally.

## How It Works

### 1. Font Detection
- The font classifier identifies fonts in the source image
- Detected fonts (e.g., "Bebas Neue", "Sofia Sans Extra Condensed") are stored in each `TextElement`

### 2. Font Collection
- Before generating the SVG, all unique fonts from text elements are collected
- Duplicates are removed to minimize the number of font requests

### 3. Font Embedding
A `<style>` element is added to the SVG with an `@import` declaration:

```xml
<svg>
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue:wght@300;400;600;700&family=Sofia+Sans+Extra+Condensed:wght@300;400;600;700');
    </style>
  </defs>
  <text font-family="Bebas Neue, Arial, Helvetica, sans-serif">...</text>
</svg>
```

### 4. Font Weights
The following weights are included for each font:
- 300 (Light)
- 400 (Regular/Normal)
- 600 (Semi-Bold)
- 700 (Bold)

This ensures both normal and bold text render correctly.

### 5. Fallback Fonts
Each text element includes fallback fonts:
```
"Bebas Neue, Arial, Helvetica, sans-serif"
```

If Google Fonts fail to load (no internet, API down, etc.), the text will fall back to Arial, then Helvetica, then the system's default sans-serif font.

## Benefits

✅ **Universal Rendering**: Text displays correctly on any device, regardless of installed fonts
✅ **No Installation Required**: Fonts load automatically from Google's CDN
✅ **Cached Performance**: Google Fonts are cached by browsers for fast loading
✅ **Graceful Degradation**: Fallback fonts ensure text is always readable
✅ **Small File Size**: Fonts are loaded externally, keeping SVG file size small

## Requirements

⚠️ **Internet Connection**: The viewing device needs internet to load Google Fonts
⚠️ **Google Fonts Availability**: Only works for fonts available on Google Fonts

## Example Output

For an infographic using fonts like:
- CAR MANUFACTURING PROCESS → Bebas Neue (37pt)
- Virtual tests,30 models → Sofia Sans Extra Condensed (15pt)
- TECHNOLOGY IN → Bebas Neue (22pt)

The SVG will include:
```xml
<svg xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue:wght@300;400;600;700&family=Sofia+Sans+Extra+Condensed:wght@300;400;600;700');
    </style>
  </defs>
  
  <g id="layer_text">
    <text font-family="Bebas Neue, Arial, Helvetica, sans-serif" font-size="37px">
      CAR MANUFACTURING PROCESS
    </text>
    <text font-family="Sofia Sans Extra Condensed, Arial, Helvetica, sans-serif" font-size="15px">
      Virtual tests,30 models
    </text>
  </g>
</svg>
```

## Offline Usage

If you need the SVG to work offline, you would need to:
1. Download the font files
2. Convert them to base64
3. Embed them directly in the SVG using `@font-face` with `data:` URIs

This significantly increases file size but enables offline viewing.
