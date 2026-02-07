"""
Visual Font Mapping Comparator
Creates side-by-side renderings of all Google Fonts with their mapped anchor fonts
"""

import os
import json
from PIL import Image, ImageDraw, ImageFont
import requests
from pathlib import Path

# Configuration
MAPPING_FILE = "google_fonts/font_to_anchor_mapping.json"
FONTS_DIR = "google_fonts"
OUTPUT_DIR = "font_comparison_output"
SAMPLE_TEXT = "The quick brown fox jumps over the lazy dog 0123456789"
FONT_SIZE = 32
IMAGE_WIDTH = 1400
ROW_HEIGHT = 100
FONTS_PER_PAGE = 20  # Number of font comparisons per image

def download_font_file(font_family, output_path):
    """
    Download a specific font file from Google Fonts
    """
    try:
        # Google Fonts CSS API
        css_url = f"https://fonts.googleapis.com/css?family={font_family.replace(' ', '+')}"
        css_response = requests.get(css_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        
        if css_response.status_code == 200:
            import re
            font_urls = re.findall(r'url\((https?://[^)]+\.(?:ttf|woff2))\)', css_response.text)
            
            if font_urls:
                font_url = font_urls[0]
                font_response = requests.get(font_url, timeout=10)
                
                if font_response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(font_response.content)
                    return True
    except Exception as e:
        print(f"Error downloading {font_family}: {e}")
    return False

def get_font_path(font_family, fonts_dir):
    """
    Get the path to a font file, downloading if necessary
    """
    # Try common filename patterns
    patterns = [
        font_family.replace(" ", "") + ".ttf",
        font_family.replace(" ", "") + ".woff2",
        font_family.replace(" ", "-") + ".ttf",
        font_family.replace(" ", "-") + ".woff2",
    ]
    
    for pattern in patterns:
        font_path = os.path.join(fonts_dir, pattern)
        if os.path.exists(font_path):
            return font_path
    
    # If not found, try to download
    download_path = os.path.join(fonts_dir, font_family.replace(" ", "") + ".woff2")
    if download_font_file(font_family, download_path):
        return download_path
    
    return None

def render_text_with_font(draw, text, position, font_path, font_size, color=(0, 0, 0)):
    """
    Render text with a specific font, fallback to default if font not available
    """
    try:
        if font_path and os.path.exists(font_path):
            font = ImageFont.truetype(font_path, font_size)
        else:
            # Fallback to default font
            font = ImageFont.load_default()
            text = f"[Font not available] {text}"
    except Exception as e:
        font = ImageFont.load_default()
        text = f"[Error loading font] {text}"
    
    draw.text(position, text, font=font, fill=color)
    return draw

def create_comparison_page(font_mappings_subset, fonts_dir, page_num):
    """
    Create a single comparison page with multiple font comparisons
    """
    img_height = ROW_HEIGHT * len(font_mappings_subset) + 100  # Extra space for header
    img = Image.new('RGB', (IMAGE_WIDTH, img_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw header
    header_font = ImageFont.load_default()
    draw.text((20, 20), f"Font Mapping Comparison - Page {page_num}", font=header_font, fill=(0, 0, 0))
    draw.text((20, 40), "Left: Original Font | Right: Mapped Anchor Font", font=header_font, fill=(100, 100, 100))
    draw.line([(0, 80), (IMAGE_WIDTH, 80)], fill=(200, 200, 200), width=2)
    
    y_offset = 100
    
    for original_font, anchor_font in font_mappings_subset:
        # Draw font names
        draw.text((20, y_offset), f"{original_font}", font=header_font, fill=(50, 50, 150))
        draw.text((720, y_offset), f"→ {anchor_font}", font=header_font, fill=(150, 50, 50))
        
        # Get font paths
        original_path = get_font_path(original_font, fonts_dir)
        anchor_path = get_font_path(anchor_font, fonts_dir)
        
        # Render original font
        render_text_with_font(
            draw, 
            SAMPLE_TEXT, 
            (20, y_offset + 25), 
            original_path, 
            FONT_SIZE,
            color=(0, 0, 0)
        )
        
        # Render anchor font
        render_text_with_font(
            draw, 
            SAMPLE_TEXT, 
            (720, y_offset + 25), 
            anchor_path, 
            FONT_SIZE,
            color=(100, 100, 100)
        )
        
        # Draw separator line
        draw.line([(0, y_offset + ROW_HEIGHT - 5), (IMAGE_WIDTH, y_offset + ROW_HEIGHT - 5)], 
                  fill=(230, 230, 230), width=1)
        
        y_offset += ROW_HEIGHT
    
    return img

def create_html_index(font_mapping, output_dir, total_pages):
    """
    Create an HTML index file for easy browsing
    """
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Font Mapping Visual Comparison</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        .stats {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .image-container {
            margin: 20px 0;
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
        }
        .page-nav {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        .page-nav a {
            display: block;
            margin: 5px 0;
            color: #0066cc;
            text-decoration: none;
        }
        .page-nav a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>🎨 Font Mapping Visual Comparison</h1>
    
    <div class="stats">
        <h2>Mapping Statistics</h2>
        <p><strong>Total Fonts:</strong> {total_fonts}</p>
        <p><strong>Total Pages:</strong> {total_pages}</p>
        <p><strong>Sample Text:</strong> <em>{sample_text}</em></p>
    </div>
    
    <div class="page-nav">
        <strong>Quick Navigation:</strong>
        {page_links}
    </div>
    
    {image_sections}
</body>
</html>
"""
    
    # Generate page links
    page_links = "\n".join([f'<a href="#page{i}">Page {i}</a>' for i in range(1, total_pages + 1)])
    
    # Generate image sections
    image_sections = ""
    for i in range(1, total_pages + 1):
        image_sections += f"""
    <div class="image-container" id="page{i}">
        <h3>Page {i}</h3>
        <img src="comparison_page_{i:04d}.png" alt="Font Comparison Page {i}">
    </div>
"""
    
    html_content = html_content.format(
        total_fonts=len(font_mapping),
        total_pages=total_pages,
        sample_text=SAMPLE_TEXT,
        page_links=page_links,
        image_sections=image_sections
    )
    
    with open(os.path.join(output_dir, "index.html"), 'w') as f:
        f.write(html_content)

def main():
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load font mapping
    print("Loading font mapping...")
    with open(MAPPING_FILE, 'r') as f:
        font_mapping = json.load(f)
    
    print(f"Found {len(font_mapping)} font mappings")
    
    # Convert to list of tuples
    font_pairs = list(font_mapping.items())
    
    # Split into pages
    total_pages = (len(font_pairs) + FONTS_PER_PAGE - 1) // FONTS_PER_PAGE
    print(f"Creating {total_pages} comparison pages...")
    
    for page_num in range(total_pages):
        start_idx = page_num * FONTS_PER_PAGE
        end_idx = min(start_idx + FONTS_PER_PAGE, len(font_pairs))
        
        print(f"\nGenerating page {page_num + 1}/{total_pages} (fonts {start_idx + 1}-{end_idx})...")
        
        subset = font_pairs[start_idx:end_idx]
        img = create_comparison_page(subset, FONTS_DIR, page_num + 1)
        
        output_path = os.path.join(OUTPUT_DIR, f"comparison_page_{page_num + 1:04d}.png")
        img.save(output_path)
        print(f"Saved: {output_path}")
    
    # Create HTML index
    print("\nCreating HTML index...")
    create_html_index(font_mapping, OUTPUT_DIR, total_pages)
    
    print(f"\n{'='*60}")
    print("COMPLETE!")
    print(f"{'='*60}")
    print(f"✓ Generated {total_pages} comparison images")
    print(f"✓ Output directory: {OUTPUT_DIR}/")
    print(f"✓ Open index.html in a browser to view all comparisons")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
