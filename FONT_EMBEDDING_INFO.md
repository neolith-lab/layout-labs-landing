# Google Fonts Embedding in SVG

## Overview

When converting raster images to SVG, the detected fonts need to be properly included in the output so that text renders correctly when the SVG is viewed or edited.

## Font Embedding Strategies

### 1. Google Fonts Import (Default)

**Config:** `'font_embedding': 'google_fonts'`

```css
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue:wght@400;700');
```

**Pros:**

* Small SVG file size
* Fonts load automatically when viewed in browser

**Cons:**

* Requires internet connection
* May not work in all SVG editors (Inkscape, Illustrator)
* Can fail if Google blocks the request

### 2. Web-Safe Fallbacks

**Config:** `'font_embedding': 'web_safe'`

Maps Google Fonts to similar system fonts:

| Google Font          | Web-Safe Fallback                  |
|----------------------|------------------------------------|
| Bebas Neue           | Arial Narrow, Impact               |
| Roboto               | Arial, Helvetica                   |
| Montserrat           | Trebuchet MS, Arial                |
| Playfair Display     | Georgia, Times New Roman          |
| Open Sans            | Arial, Helvetica                   |

**Pros:**

* Works offline
* No external dependencies
* Small file size

**Cons:**

* Fonts won't look exactly the same
* Limited to what's available on the system

### 3. Both (Recommended)

**Config:** `'font_embedding': 'both'`

Includes Google Fonts import AND web-safe fallbacks:

```css
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue');

.font-bebas-neue {
    font-family: 'Bebas Neue', 'Arial Narrow', Impact, sans-serif;
}
```

**Pros:**

* Best of both worlds
* Works with internet (exact font) and without (fallback)

**Cons:**

* Slightly more CSS

### 4. Embedded Font Files (Most Portable)

**Config:** `'embed_font_files': True`

Downloads font files and embeds them as base64:

```css
@font-face {
    font-family: 'Bebas Neue';
    font-weight: 400;
    src: url('data:font/woff2;base64,d09GMg...') format('woff2');
}
```

**Pros:**

* Fully self-contained SVG
* Works everywhere, offline
* Exact font appearance

**Cons:**

* Much larger file size (50-200KB per font)
* Requires `requests` library
* Slower generation (downloads fonts)

## Configuration

In `config.py`:

```python
SVG_OUTPUT = {
    # ...other settings...
    
    # Choose strategy: 'google_fonts', 'web_safe', 'both'
    'font_embedding': 'both',
    
    # Enable font file embedding (makes SVG self-contained)
    'embed_font_files': False,  # Set to True for full portability
}
```

## Font Fallback Mapping

The system includes mappings for common Google Fonts:

### Sans-Serif

* **Roboto** → Arial, Helvetica
* **Open Sans** → Arial, Helvetica
* **Montserrat** → Trebuchet MS, Arial
* **Bebas Neue** → Arial Narrow, Impact
* **Poppins** → Arial, Helvetica
* **Inter** → Arial, Helvetica
* **Oswald** → Arial Narrow, Arial

### Serif

* **Playfair Display** → Georgia, Times New Roman
* **Merriweather** → Georgia, Times New Roman
* **Lora** → Georgia, Times New Roman

### Monospace

* **Roboto Mono** → Courier New, Courier
* **Fira Code** → Courier New, Courier

## Troubleshooting

### Fonts not showing in SVG viewer

1. **Try a browser**: Open SVG in Chrome/Firefox (best Google Fonts support)
2. **Enable embedding**: Set `'embed_font_files': True`
3. **Check internet**: Google Fonts requires internet connection

### Fonts look different in Inkscape/Illustrator

These apps may not support @import. Solutions:

1. Enable `'embed_font_files': True`
2. Install the fonts locally on your system
3. Use "Convert text to paths" in the editor (loses editability)

### Large SVG file size

If using embedded fonts, file size increases significantly. Options:

1. Use `'font_embedding': 'web_safe'` for smaller files
2. Only embed critical fonts
3. Accept the tradeoff for portability

## Programmatic Usage

```python
from svg_generator import SVGGenerator
from config import SVG_OUTPUT

# Configure for embedded fonts
config = SVG_OUTPUT.copy()
config['embed_font_files'] = True

generator = SVGGenerator(config)
generator.generate_layered_svg(...)
```

## Future Improvements

1. **Local font caching**: Cache downloaded fonts to avoid re-downloading
2. **Subset fonts**: Only include characters actually used (smaller files)
3. **Convert to paths**: Option to convert text to vector paths (no font needed)
4. **Variable fonts**: Support for variable font weights
