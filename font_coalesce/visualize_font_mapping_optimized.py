"""
Optimized Visual Font Mapping Comparator
Creates side-by-side renderings using web-based font rendering
Generates a responsive HTML page with live font comparisons
"""

import json
import os
from collections import defaultdict

MAPPING_FILE = "google_fonts/font_to_anchor_mapping.json"
OUTPUT_FILE = "font_comparison_interactive.html"

def generate_interactive_html(font_mapping):
    """
    Generate an interactive HTML page with Google Fonts CDN
    This approach is much faster and doesn't require downloading fonts
    """
    
    # Group fonts by their anchor
    anchor_groups = defaultdict(list)
    for original_font, anchor_font in font_mapping.items():
        anchor_groups[anchor_font].append(original_font)
    
    # Get unique fonts for Google Fonts API
    all_fonts = set(font_mapping.keys()) | set(font_mapping.values())
    
    # Generate Google Fonts import URL
    # Split into chunks to avoid URL length limits
    font_chunks = []
    chunk = []
    for font in sorted(all_fonts):
        chunk.append(font)
        if len(chunk) >= 50:  # Limit to 50 fonts per URL
            font_chunks.append(chunk)
            chunk = []
    if chunk:
        font_chunks.append(chunk)
    
    font_imports = []
    for chunk in font_chunks:
        fonts_param = "|".join([f.replace(" ", "+") for f in chunk])
        font_imports.append(f'https://fonts.googleapis.com/css?family={fonts_param}')
    
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Font Mapping Visual Comparison - Interactive</title>
    
    <!-- Google Fonts Import -->
    {font_import_links}
    
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        header p {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }}
        
        .stat-box {{
            text-align: center;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .stat-box .number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-box .label {{
            color: #666;
            margin-top: 5px;
        }}
        
        .controls {{
            padding: 20px 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .controls label {{
            font-weight: 600;
            margin-right: 10px;
        }}
        
        .controls input, .controls select {{
            padding: 8px 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }}
        
        .controls input:focus, .controls select:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        #sampleText {{
            flex: 1;
            min-width: 300px;
        }}
        
        #fontSize {{
            width: 80px;
        }}
        
        .anchor-section {{
            margin: 30px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .anchor-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .anchor-header h2 {{
            font-size: 1.8em;
        }}
        
        .anchor-header .count {{
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
        }}
        
        .comparison-grid {{
            padding: 20px;
        }}
        
        .comparison-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
            margin: 10px 0;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .comparison-row:hover {{
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        
        .font-sample {{
            padding: 15px;
            background: white;
            border-radius: 6px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }}
        
        .font-sample.original {{
            border-left: 4px solid #4CAF50;
        }}
        
        .font-sample.anchor {{
            border-left: 4px solid #FF9800;
        }}
        
        .font-name {{
            font-size: 0.85em;
            color: #666;
            margin-bottom: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .font-sample.original .font-name {{
            color: #4CAF50;
        }}
        
        .font-sample.anchor .font-name {{
            color: #FF9800;
        }}
        
        .rendered-text {{
            font-size: 24px;
            color: #333;
            line-height: 1.5;
            word-wrap: break-word;
        }}
        
        .filter-info {{
            padding: 20px 30px;
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            margin: 20px 30px;
            border-radius: 8px;
        }}
        
        @media (max-width: 768px) {{
            .comparison-row {{
                grid-template-columns: 1fr;
            }}
            
            header h1 {{
                font-size: 1.8em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎨 Font Mapping Visual Comparison</h1>
            <p>Interactive comparison of {total_fonts} Google Fonts mapped to {total_anchors} anchor fonts</p>
        </header>
        
        <div class="stats">
            <div class="stat-box">
                <div class="number">{total_fonts}</div>
                <div class="label">Total Fonts</div>
            </div>
            <div class="stat-box">
                <div class="number">{total_anchors}</div>
                <div class="label">Anchor Fonts</div>
            </div>
            <div class="stat-box">
                <div class="number">{avg_per_anchor}</div>
                <div class="label">Avg Fonts/Anchor</div>
            </div>
        </div>
        
        <div class="controls">
            <label for="sampleText">Sample Text:</label>
            <input type="text" id="sampleText" value="The quick brown fox jumps over the lazy dog 0123456789">
            
            <label for="fontSize">Font Size:</label>
            <input type="number" id="fontSize" value="24" min="12" max="72">
            
            <label for="filterAnchor">Filter by Anchor:</label>
            <select id="filterAnchor">
                <option value="">All Anchors</option>
                {anchor_options}
            </select>
        </div>
        
        <div id="content">
            {anchor_sections}
        </div>
    </div>
    
    <script>
        // Update sample text in real-time
        document.getElementById('sampleText').addEventListener('input', function(e) {{
            const newText = e.target.value;
            document.querySelectorAll('.rendered-text').forEach(el => {{
                el.textContent = newText;
            }});
        }});
        
        // Update font size in real-time
        document.getElementById('fontSize').addEventListener('input', function(e) {{
            const newSize = e.target.value + 'px';
            document.querySelectorAll('.rendered-text').forEach(el => {{
                el.style.fontSize = newSize;
            }});
        }});
        
        // Filter by anchor
        document.getElementById('filterAnchor').addEventListener('change', function(e) {{
            const selectedAnchor = e.target.value;
            document.querySelectorAll('.anchor-section').forEach(section => {{
                if (selectedAnchor === '' || section.dataset.anchor === selectedAnchor) {{
                    section.style.display = 'block';
                }} else {{
                    section.style.display = 'none';
                }}
            }});
        }});
    </script>
</body>
</html>
"""
    
    # Generate font import links
    font_import_links = "\n    ".join([
        f'<link href="{url}" rel="stylesheet">'
        for url in font_imports
    ])
    
    # Generate anchor options
    anchor_options = "\n                ".join([
        f'<option value="{anchor}">{anchor} ({len(fonts)} fonts)</option>'
        for anchor, fonts in sorted(anchor_groups.items(), key=lambda x: -len(x[1]))
    ])
    
    # Generate anchor sections
    anchor_sections = []
    for anchor_font in sorted(anchor_groups.keys(), key=lambda x: -len(anchor_groups[x])):
        mapped_fonts = sorted(anchor_groups[anchor_font])
        
        comparisons = []
        for original_font in mapped_fonts:
            comparison_html = f"""
            <div class="comparison-row">
                <div class="font-sample original">
                    <div class="font-name">Original: {original_font}</div>
                    <div class="rendered-text" style="font-family: '{original_font}', sans-serif;">
                        The quick brown fox jumps over the lazy dog 0123456789
                    </div>
                </div>
                <div class="font-sample anchor">
                    <div class="font-name">Anchor: {anchor_font}</div>
                    <div class="rendered-text" style="font-family: '{anchor_font}', sans-serif;">
                        The quick brown fox jumps over the lazy dog 0123456789
                    </div>
                </div>
            </div>
"""
            comparisons.append(comparison_html)
        
        section_html = f"""
        <div class="anchor-section" data-anchor="{anchor_font}">
            <div class="anchor-header">
                <h2>{anchor_font}</h2>
                <div class="count">{len(mapped_fonts)} fonts mapped</div>
            </div>
            <div class="comparison-grid">
                {"".join(comparisons)}
            </div>
        </div>
"""
        anchor_sections.append(section_html)
    
    # Calculate stats
    total_fonts = len(font_mapping)
    total_anchors = len(anchor_groups)
    avg_per_anchor = round(total_fonts / total_anchors, 1)
    
    # Fill template
    html_content = html_template.format(
        font_import_links=font_import_links,
        total_fonts=total_fonts,
        total_anchors=total_anchors,
        avg_per_anchor=avg_per_anchor,
        anchor_options=anchor_options,
        anchor_sections="\n        ".join(anchor_sections)
    )
    
    return html_content

def main():
    print("Loading font mapping...")
    with open(MAPPING_FILE, 'r') as f:
        font_mapping = json.load(f)
    
    print(f"Found {len(font_mapping)} font mappings")
    print("Generating interactive HTML comparison...")
    
    html_content = generate_interactive_html(font_mapping)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n{'='*60}")
    print("COMPLETE!")
    print(f"{'='*60}")
    print(f"✓ Generated interactive comparison")
    print(f"✓ Output file: {OUTPUT_FILE}")
    print(f"✓ Open in browser to view live font comparisons")
    print(f"✓ Features:")
    print(f"  - Live sample text editing")
    print(f"  - Adjustable font size")
    print(f"  - Filter by anchor font")
    print(f"  - {len(font_mapping)} font pairs rendered")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
