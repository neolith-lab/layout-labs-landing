import os
import csv
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.neighbors import NearestNeighbors
from tqdm import tqdm # For progress bar

# Import our config
from anchors import ANCHOR_CONFIG

FONT_DIR = "google_fonts"
IMG_SIZE = 64
FONT_SIZE = 48
# "Rag" is a good string because it has a capital, a round letter, and a descender (g)
# This captures more "vibe" than a single letter.
RENDER_TEXT = "Rag" 

def font_to_vector(font_path):
    """
    Renders the text to a flattened numpy array representing the font's visual style.
    """
    try:
        # Create white background image
        image = Image.new("L", (IMG_SIZE, IMG_SIZE), 255) 
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype(font_path, FONT_SIZE)
        except OSError:
            return None # Skip broken fonts

        # Draw text. Positioning (5,0) works well for 'Rag' at size 48/64
        draw.text((5, 0), RENDER_TEXT, font=font, fill=0)
        
        # Convert to numpy array (0-255) and normalize to (0-1)
        arr = np.array(image).flatten() / 255.0
        return arr
    except Exception as e:
        return None

def main():
    print(f"Scanning '{FONT_DIR}'...")
    all_files = [f for f in os.listdir(FONT_DIR) if f.endswith(".ttf")]
    
    # --- 1. Vectorize the Anchors ---
    anchor_vectors = []
    anchor_names = []
    anchor_labels = []
    
    print("Processing Anchors (The 50 Representatives)...")
    for filename, label in ANCHOR_CONFIG.items():
        path = os.path.join(FONT_DIR, filename)
        if os.path.exists(path):
            vec = font_to_vector(path)
            if vec is not None:
                anchor_vectors.append(vec)
                anchor_names.append(filename)
                anchor_labels.append(label)
        else:
            # It's okay if a few are missing, but we warn the user
            print(f"Warning: Anchor {filename} not found. Did you run download_fonts.py?")

    if not anchor_vectors:
        print("Error: No anchors found. Please run download_fonts.py first.")
        return

    # --- 2. Train the Nearest Neighbor Model ---
    # We fit the model on our known anchor styles
    X = np.array(anchor_vectors)
    nbrs = NearestNeighbors(n_neighbors=1, algorithm='ball_tree').fit(X)

    # --- 3. Map the Rest of the Library ---
    results = []
    
    print("Mapping the unknown fonts...")
    for filename in tqdm(all_files):
        # If it's an anchor, we just record it as itself
        if filename in ANCHOR_CONFIG:
            results.append([filename, ANCHOR_CONFIG[filename], "ANCHOR (Self)", 0.0])
            continue
            
        path = os.path.join(FONT_DIR, filename)
        vec = font_to_vector(path)
        
        if vec is not None:
            # Find the single closest anchor
            distances, indices = nbrs.kneighbors([vec])
            
            closest_idx = indices[0][0]
            dist = distances[0][0] # The "confidence" (lower is better)
            
            closest_anchor_name = anchor_names[closest_idx]
            assigned_style = anchor_labels[closest_idx]
            
            results.append([filename, assigned_style, closest_anchor_name, round(dist, 4)])

    # --- 4. Export to CSV ---
    output_file = "final_font_mapping.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Font Filename", "Assigned Category", "Closest Visual Match", "Distance Score"])
        writer.writerows(results)
        
    print(f"\nSuccess! Mapping saved to {output_file}")
    print("Check 'Distance Score' column: Lower numbers (e.g. < 15.0) mean a very strong visual match.")

if __name__ == "__main__":
    main()