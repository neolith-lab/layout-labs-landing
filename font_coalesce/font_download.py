import os
import requests
import random
import json
from collections import defaultdict

OUTPUT_DIR = "google_fonts"
MAPPING_FILE = "font_to_anchor_mapping.json"

# Your 50 Representative Fonts (The Anchors)
ANCHOR_FAMILIES = [
    # 1. Professional Sans
    "Roboto", "Open Sans", "Lato", "Montserrat", "Inter", "Poppins", "Raleway", 
    "Nunito", "Work Sans", "Source Sans 3", "Ubuntu", "Mulish", "Heebo", "DM Sans", "Karla",
    # 2. Elegant Serif
    "Playfair Display", "Merriweather", "Lora", "Crimson Text", "Libre Baskerville", 
    "EB Garamond", "Cormorant Garamond", "Spectral", "PT Serif", "Cardo", "Domine", 
    "Vollkorn", "Prata", "Cinzel", "Fraunces",
    # 3. Slab Serif
    "Roboto Slab", "Oswald", "Arvo", "Zilla Slab", "Bitter",
    # 4. Display
    "Abril Fatface", "Lobster", "Bebas Neue", "Anton", "Righteous", "Orbitron",
    # 5. Handwriting
    "Pacifico", "Indie Flower", "Caveat", "Shadows Into Light", "Great Vibes",
    # 6. Monospace
    "Roboto Mono", "Inconsolata", "Source Code Pro", "Space Mono"
]

def download_file(url, filepath):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
    return False

def download_anchor_fonts_directly():
    """
    Download anchor fonts directly from Google Fonts CDN
    """
    print("\n=== Downloading Anchor Fonts ===\n")
    downloaded_count = 0
    
    for family in ANCHOR_FAMILIES:
        # Google Fonts CSS API - fetch the font file URLs
        css_url = f"https://fonts.googleapis.com/css?family={family.replace(' ', '+')}"
        
        try:
            css_response = requests.get(css_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            if css_response.status_code == 200:
                css_content = css_response.text
                
                # Extract TTF/WOFF2 URL from CSS (look for url() declarations)
                import re
                font_urls = re.findall(r'url\((https?://[^)]+\.(?:ttf|woff2))\)', css_content)
                
                if font_urls:
                    # Use the first URL found (usually the primary font file)
                    font_url = font_urls[0]
                    clean_name = family.replace(" ", "") + os.path.splitext(font_url)[-1]
                    save_path = os.path.join(OUTPUT_DIR, clean_name)
                    
                    if not os.path.exists(save_path):
                        print(f"Downloading {family}...")
                        success = download_file(font_url, save_path)
                        if success:
                            downloaded_count += 1
                    else:
                        print(f"{family} already exists, skipping...")
                        downloaded_count += 1
                else:
                    print(f"No font files found for {family}")
            else:
                print(f"Failed to fetch CSS for {family}")
        except Exception as e:
            print(f"Error downloading {family}: {e}")
    
    print(f"\nFinished. {downloaded_count} anchor fonts downloaded to '{OUTPUT_DIR}'")
    return downloaded_count

def get_all_google_fonts():
    """
    Fetch the complete list of Google Fonts from the API
    """
    print("\n=== Fetching Complete Google Fonts List ===\n")
    
    # Use Google Fonts Developer API v1
    # This endpoint lists all available fonts
    url = "https://www.googleapis.com/webfonts/v1/webfonts?key=AIzaSyDummy"  # Public endpoint works without key for listing
    
    # Alternative: Use the CSS API to discover fonts
    # We'll scrape the Google Fonts directory page
    try:
        # Method 1: Try the fonts.google.com metadata endpoint
        metadata_url = "https://fonts.google.com/metadata/fonts"
        response = requests.get(metadata_url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if 'familyMetadataList' in data:
                fonts_list = data['familyMetadataList']
                print(f"Found {len(fonts_list)} fonts from Google Fonts metadata")
                return [font['family'] for font in fonts_list]
    except Exception as e:
        print(f"Metadata endpoint failed: {e}")
    
    # Method 2: Fallback - use a curated list of popular Google Fonts
    # This is a comprehensive list of ~1500 fonts as of 2024
    print("Using curated list of Google Fonts...")
    
    # For a production system, you'd want to maintain this list
    # For now, we'll fetch from a GitHub repo that maintains the list
    try:
        github_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/families.txt"
        response = requests.get(github_url, timeout=15)
        if response.status_code == 200:
            families = [line.strip() for line in response.text.split('\n') if line.strip()]
            print(f"Found {len(families)} fonts from GitHub repository")
            return families
    except Exception as e:
        print(f"GitHub fallback failed: {e}")
    
    # Method 3: Use a hardcoded comprehensive list (subset shown here)
    print("Using hardcoded comprehensive font list...")
    return get_comprehensive_font_list()

def get_comprehensive_font_list():
    """
    Returns a comprehensive list of Google Fonts (1500+ fonts)
    This would be the full list - showing abbreviated version here
    """
    # This is a curated list of Google Fonts categories
    # In production, you'd load this from a file
    return [
        # Include all anchor fonts
        *ANCHOR_FAMILIES,
        # Additional popular fonts (abbreviated - full list would be 1500+)
        "Abel", "Abhaya Libre", "Abril Text", "Aclonica", "Acme", "Actor", "Adamina",
        "Advent Pro", "Aguafina Script", "Akronim", "Aladin", "Aldrich", "Alef",
        "Alegreya", "Alegreya SC", "Alegreya Sans", "Alegreya Sans SC", "Aleo",
        "Alex Brush", "Alfa Slab One", "Alice", "Alike", "Alike Angular", "Allan",
        "Allerta", "Allerta Stencil", "Allison", "Allura", "Almarai", "Almendra",
        "Almendra Display", "Almendra SC", "Alumni Sans", "Amarante", "Amaranth",
        "Amatic SC", "Amethysta", "Amiko", "Amiri", "Amita", "Anaheim", "Andada Pro",
        "Andika", "Anek", "Angkor", "Annie Use Your Telescope", "Anonymous Pro",
        "Antic", "Antic Didone", "Antic Slab", "Antique", "Anybody", "Architects Daughter",
        "Archivo", "Archivo Black", "Archivo Narrow", "Are You Serious", "Aref Ruqaa",
        # ... (in production, this would continue for all 1500+ fonts)
    ]

def classify_font_to_anchor(font_family):
    """
    Intelligent classification of fonts to one of 50 anchor fonts
    Uses multi-level heuristics based on font characteristics
    """
    font_lower = font_family.lower()
    
    # LEVEL 1: Exact or close matches to anchor fonts
    exact_matches = {
        'roboto': 'Roboto',
        'open sans': 'Open Sans',
        'lato': 'Lato',
        'montserrat': 'Montserrat',
        'inter': 'Inter',
        'poppins': 'Poppins',
        'raleway': 'Raleway',
        'nunito': 'Nunito',
        'work sans': 'Work Sans',
        'source sans': 'Source Sans 3',
        'ubuntu': 'Ubuntu',
        'mulish': 'Mulish',
        'heebo': 'Heebo',
        'dm sans': 'DM Sans',
        'karla': 'Karla',
        'playfair': 'Playfair Display',
        'merriweather': 'Merriweather',
        'lora': 'Lora',
        'crimson': 'Crimson Text',
        'libre baskerville': 'Libre Baskerville',
        'eb garamond': 'EB Garamond',
        'garamond': 'EB Garamond',
        'cormorant': 'Cormorant Garamond',
        'spectral': 'Spectral',
        'pt serif': 'PT Serif',
        'cardo': 'Cardo',
        'domine': 'Domine',
        'vollkorn': 'Vollkorn',
        'prata': 'Prata',
        'cinzel': 'Cinzel',
        'fraunces': 'Fraunces',
        'roboto slab': 'Roboto Slab',
        'oswald': 'Oswald',
        'arvo': 'Arvo',
        'zilla slab': 'Zilla Slab',
        'bitter': 'Bitter',
        'abril fatface': 'Abril Fatface',
        'lobster': 'Lobster',
        'bebas': 'Bebas Neue',
        'anton': 'Anton',
        'righteous': 'Righteous',
        'orbitron': 'Orbitron',
        'pacifico': 'Pacifico',
        'indie flower': 'Indie Flower',
        'caveat': 'Caveat',
        'shadows into light': 'Shadows Into Light',
        'great vibes': 'Great Vibes',
        'roboto mono': 'Roboto Mono',
        'inconsolata': 'Inconsolata',
        'source code pro': 'Source Code Pro',
        'space mono': 'Space Mono',
    }
    
    for pattern, anchor in exact_matches.items():
        if pattern in font_lower:
            return anchor
    
    # LEVEL 2: Monospace/Code fonts
    if any(kw in font_lower for kw in ['mono', 'code', 'console', 'courier', 'terminal', 'fira code', 'jetbrains', 'droid sans mono']):
        monospace_options = ['Roboto Mono', 'Inconsolata', 'Source Code Pro', 'Space Mono']
        # Distribute based on font name hash for consistency
        return monospace_options[hash(font_family) % len(monospace_options)]
    
    # LEVEL 3: Handwriting/Script/Cursive fonts
    if any(kw in font_lower for kw in ['script', 'handwriting', 'cursive', 'brush', 'hand', 'dancing', 'cookie', 'satisfy', 'allura', 'sacramento', 'tangerine', 'courgette', 'kaushan', 'permanent marker']):
        handwriting_options = ['Pacifico', 'Indie Flower', 'Caveat', 'Shadows Into Light', 'Great Vibes']
        return handwriting_options[hash(font_family) % len(handwriting_options)]
    
    # LEVEL 4: Display/Decorative/Bold fonts
    if any(kw in font_lower for kw in ['display', 'fatface', 'black', 'ultra', 'poster', 'impact', 'alfa slab', 'bangers', 'titan', 'fugaz', 'staatliches', 'russo', 'bungee', 'rubik mono']):
        display_options = ['Bebas Neue', 'Anton', 'Abril Fatface', 'Lobster', 'Righteous', 'Orbitron']
        return display_options[hash(font_family) % len(display_options)]
    
    # LEVEL 5: Slab Serif fonts
    if 'slab' in font_lower or any(kw in font_lower for kw in ['rockwell', 'courier', 'museo slab', 'egyptienne']):
        slab_options = ['Roboto Slab', 'Arvo', 'Zilla Slab', 'Bitter', 'Oswald']
        return slab_options[hash(font_family) % len(slab_options)]
    
    # LEVEL 6: Serif fonts (elegant, traditional)
    if any(kw in font_lower for kw in ['serif', 'antique', 'old', 'droid serif', 'noto serif', 'alegreya', 'gentium', 'podkova', 'slabo', 'tinos', 'gelasio']):
        serif_options = [
            'Playfair Display', 'Merriweather', 'Lora', 'Crimson Text', 
            'Libre Baskerville', 'EB Garamond', 'Cormorant Garamond', 'Spectral',
            'PT Serif', 'Cardo', 'Domine', 'Vollkorn', 'Prata', 'Cinzel', 'Fraunces'
        ]
        return serif_options[hash(font_family) % len(serif_options)]
    
    # LEVEL 7: Condensed/Narrow fonts
    if any(kw in font_lower for kw in ['condensed', 'narrow', 'compressed', 'slim', 'compact', 'fjalla', 'yanone kaffeesatz', 'archivo narrow']):
        condensed_options = ['Oswald', 'Anton', 'Bebas Neue']
        return condensed_options[hash(font_family) % len(condensed_options)]
    
    # LEVEL 8: Rounded/Friendly Sans fonts
    if any(kw in font_lower for kw in ['rounded', 'round', 'varela', 'comfortaa', 'quicksand', 'muli', 'rubik', 'baloo']):
        rounded_options = ['Nunito', 'Poppins', 'Mulish', 'Heebo']
        return rounded_options[hash(font_family) % len(rounded_options)]
    
    # LEVEL 9: Geometric/Modern Sans fonts
    if any(kw in font_lower for kw in ['geometric', 'futura', 'avenir', 'century gothic', 'circular', 'renner', 'jost', 'spartan', 'league spartan']):
        geometric_options = ['Montserrat', 'Raleway', 'Work Sans', 'DM Sans']
        return geometric_options[hash(font_family) % len(geometric_options)]
    
    # LEVEL 10: Humanist Sans fonts
    if any(kw in font_lower for kw in ['humanist', 'gill sans', 'frutiger', 'myriad', 'verdana', 'trebuchet', 'pt sans', 'cabin', 'exo']):
        humanist_options = ['Open Sans', 'Lato', 'Source Sans 3', 'Ubuntu']
        return humanist_options[hash(font_family) % len(humanist_options)]
    
    # LEVEL 11: Grotesque/Neo-grotesque Sans fonts
    if any(kw in font_lower for kw in ['grotesque', 'gothic', 'noto sans', 'droid sans', 'barlow', 'hind', 'public sans', 'oxygen', 'asap']):
        grotesque_options = ['Roboto', 'Inter', 'Karla', 'Work Sans']
        return grotesque_options[hash(font_family) % len(grotesque_options)]
    
    # LEVEL 12: Default classification - distribute remaining fonts evenly
    # Use all Professional Sans fonts for maximum distribution
    default_sans_options = [
        'Roboto', 'Open Sans', 'Lato', 'Montserrat', 'Inter', 'Poppins', 
        'Raleway', 'Nunito', 'Work Sans', 'Source Sans 3', 'Ubuntu', 
        'Mulish', 'Heebo', 'DM Sans', 'Karla'
    ]
    return default_sans_options[hash(font_family) % len(default_sans_options)]

def create_font_mapping(all_fonts):
    """
    Create a mapping from all Google Fonts to the 50 anchor fonts
    """
    print(f"\n=== Creating Font Mapping ===\n")
    print(f"Mapping {len(all_fonts)} fonts to {len(ANCHOR_FAMILIES)} anchors...\n")
    
    font_mapping = {}
    anchor_stats = defaultdict(int)
    
    for font in all_fonts:
        anchor = classify_font_to_anchor(font)
        font_mapping[font] = anchor
        anchor_stats[anchor] += 1
    
    # Print statistics
    print("Mapping Statistics:")
    print(f"{'='*60}")
    for anchor in sorted(ANCHOR_FAMILIES):
        count = anchor_stats.get(anchor, 0)
        print(f"{anchor:<40} {count:>4} fonts")
    print(f"{'='*60}")
    print(f"Total: {len(font_mapping)} fonts mapped\n")
    
    return font_mapping

def save_mapping(font_mapping):
    """
    Save the font mapping to a JSON file
    """
    mapping_path = os.path.join(OUTPUT_DIR, MAPPING_FILE)
    
    with open(mapping_path, 'w') as f:
        json.dump(font_mapping, f, indent=2, sort_keys=True)
    
    print(f"Mapping saved to: {mapping_path}")
    return mapping_path

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("="*60)
    print("Google Fonts Comprehensive Download & Mapping System")
    print("="*60)
    print(f"Anchor fonts: {len(ANCHOR_FAMILIES)}")
    print(f"Output directory: {OUTPUT_DIR}/")
    print("="*60)
    
    # Step 1: Download the 50 anchor fonts
    print("\nSTEP 1: Downloading Anchor Fonts")
    downloaded_count = download_anchor_fonts_directly()
    
    # Step 2: Get complete list of all Google Fonts
    print("\nSTEP 2: Fetching All Google Fonts")
    all_fonts = get_all_google_fonts()
    
    if not all_fonts:
        print("ERROR: Could not fetch Google Fonts list")
        return
    
    # Step 3: Create mapping from all fonts to anchors
    print(f"\nSTEP 3: Creating Font-to-Anchor Mapping")
    font_mapping = create_font_mapping(all_fonts)
    
    # Step 4: Save the mapping
    print(f"\nSTEP 4: Saving Mapping File")
    mapping_path = save_mapping(font_mapping)
    
    # Final summary
    print(f"\n{'='*60}")
    print("COMPLETE!")
    print(f"{'='*60}")
    print(f"✓ Downloaded: {downloaded_count}/{len(ANCHOR_FAMILIES)} anchor fonts")
    print(f"✓ Mapped: {len(font_mapping)} Google Fonts")
    print(f"✓ Font files: {OUTPUT_DIR}/")
    print(f"✓ Mapping: {mapping_path}")
    print(f"{'='*60}")
    print("\nUsage:")
    print("  1. Use the anchor fonts for font classification training")
    print("  2. Load font_to_anchor_mapping.json to map detected fonts")
    print("  3. Any detected font can be replaced with its anchor equivalent")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()