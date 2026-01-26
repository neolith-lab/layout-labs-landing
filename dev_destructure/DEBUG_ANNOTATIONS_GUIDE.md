# Debug Image Annotations Guide

## 🎨 Color Coding

### **RED Boxes = KEEP**
Images/icons that will be included in the final SVG output

### **GREEN Boxes = FILTER**
Container-like regions that are filtered out (will be detected separately as containers)

---

## 📊 Label Format

```
KEEP #18: Photo
34x34 | clr:768 | fill:70% | s:3
```

### Line 1: Detection Info
- **`KEEP #18`** or **`FILTER #3`** - Status and detection number
- **`Photo`** or **`Icon`** or **`Container`** - Element type

### Line 2: Metrics
All metrics are used in the container filtering heuristics:

| Metric | Meaning | Example | Container Behavior |
|--------|---------|---------|-------------------|
| **`34x34`** | Width × Height in pixels | 34×34 pixels | Larger = more likely container |
| **`clr:768`** | Unique color count | 768 unique colors | <250 colors = likely container |
| **`fill:70%`** | Fill ratio (uniform area) | 70% is one color | >70% uniform = likely container |
| **`s:3`** | Container score | 3 points | ≥35 points = filtered as container |

---

## 🎯 Score Breakdown (Max 110 points) - UPDATED

The container score is calculated from 4 heuristics:

### 1. **Size Heuristic** (0-35 points)
- If area > 8% of total image → +up to 35 points
- **Calculation**: `min(35, int((area_ratio - 0.08) * 280))`
- **Example**: Large card taking 15% of image → +35 points

### 2. **Color Uniformity** (0-20 points)
- If unique colors < 250 → +up to 20 points
- **Calculation**: `int(20 * (1 - unique_colors / 250))`
- **How `clr` is calculated**: `len(np.unique(pixels))` - counts every unique RGB combination
- **Example**: Container with 50 colors → +16 points
- **Example**: Photo with 800 colors → +0 points

### 3. **Edge Simplicity** (0-30 points) ⭐ **HIGHEST WEIGHT**
- If edge complexity < 0.4 → +up to 30 points
- **Calculation**: `int(30 * (1 - edge_complexity / 0.4))`
- **Why highest?** Edge simplicity is the strongest signal for containers!
- **Example**: Simple rectangle border (complexity 0.1) → +22 points
- **Example**: Complex icon edges (complexity 0.6) → +0 points

### 4. **Fill Ratio** (0-25 points)
- If >70% of region is uniform color → +up to 25 points
- **Calculation**: `int(25 * ((fill_ratio - 0.70) / 0.30))`
- **Example**: Container with 85% solid fill → +12 points
- **Example**: Icon with 40% fill → +0 points

### **How `s` (Score) is Calculated:**
```python
container_score = size_score + color_score + edge_score + fill_score
```

### Decision Threshold: 35 points
- **Score < 35**: KEEP as image (RED box)
- **Score ≥ 35**: FILTER as container (GREEN box)

---

## 📈 Example Interpretations

### Example 1: Small Icon (KEPT)
```
KEEP #18: Photo
34x34 | clr:768 | fill:70% | s:3
```
- **Size**: 34×34px (small, no size points)
- **Colors**: 768 unique (high diversity, no color points)
- **Fill**: 70% (at threshold, minimal fill points)
- **Score**: 3 total → **KEPT** ✓

### Example 2: Large Container (FILTERED)
```
FILTER #3: Container
293x251 | clr:84 | fill:84% | s:13
```
- **Size**: 293×251px (large, likely >8% → ~30 points)
- **Colors**: 84 unique (low diversity → ~22 points)
- **Fill**: 84% uniform (high fill → ~20 points)
- **Score**: Should be ~72 total → **FILTERED** ✓
- *(If shown as s:13, there may be debug info truncation)*

### Example 3: Medium Icon (KEPT)
```
KEEP #7: Icon
66x66 | clr:115 | fill:91% | s:17
```
- **Size**: 66×66px (medium, area ~0.5%, minimal size points)
- **Colors**: 115 unique (moderate → ~13 points)
- **Fill**: 91% (circular badge background → some fill points)
- **Score**: 17 total → **KEPT** (below 35 threshold) ✓

---

## 🔧 Tuning Guide

If filtering is incorrect:

### Too Many False Positives (icons filtered as containers):
- **Increase** `container_score_threshold` (35 → 40)
- **Increase** `container_min_unique_colors` (250 → 300)
- **Decrease** `container_size_threshold` (0.08 → 0.06)

### Too Many False Negatives (containers kept as images):
- **Decrease** `container_score_threshold` (35 → 30)
- **Decrease** `container_min_unique_colors` (250 → 200)
- **Increase** `container_size_threshold` (0.08 → 0.10)

---

## 🆕 Recent Changes (Option 2 Implementation)

### Minimum Size Lowered
```python
'min_image_size': 20,   # LOWERED from 30 → catch smaller icons
'min_icon_size': 20,    # LOWERED from 30 → detect even smaller icons
```

**Impact**: Icons as small as 20×20 pixels will now be detected
**Before**: Icons < 30px were ignored
**After**: Icons ≥ 20px will be detected

This should catch the missing small icons in the circular badges!

---

## 🐛 Debugging Tips

1. **Check the score** - If icon is filtered (GREEN) but score < 35, something is wrong
2. **Check fill ratio** - Icons in circular badges have high fill (the background circle)
3. **Check color count** - Simple line icons have low unique colors (50-150)
4. **Check size** - Very small icons (<20px) will still be missed

**Common Issue**: Icon inside circular badge detected as one large element
**Solution**: The badge background inflates the fill ratio, but low color count should compensate
