# Container Score Calculation - Complete Reference

## 🎯 **Threshold**
```python
container_score_threshold = 35 points
```
- **Score < 35**: Region is KEPT as image/icon (RED box)
- **Score ≥ 35**: Region is FILTERED as container (GREEN box)

---

## 📊 **Score Components (Total: 110 points possible)**

### **Updated Weightage (Edge Increased):**

| Component | Max Points | Previous | Change | Why? |
|-----------|-----------|----------|--------|------|
| **Size** | 35 | 40 | -5 | Reduced to balance |
| **Color Uniformity** | 20 | 25 | -5 | Reduced to balance |
| **Edge Simplicity** ⭐ | 30 | 20 | **+10** | **INCREASED** - strongest signal! |
| **Fill Ratio** | 25 | 25 | - | Unchanged |
| **TOTAL** | 110 | 110 | - | - |

---

## 🔢 **Detailed Calculations**

### **1. Size Score (0-35 points)**
```python
area_ratio = bbox.area / total_image_area
if area_ratio > 0.08:  # More than 8% of image
    size_score = min(35, int((area_ratio - 0.08) * 280))
else:
    size_score = 0
```

**Examples:**
- 5% of image → 0 points (too small)
- 10% of image → `(0.10 - 0.08) * 280 = 5.6` → **6 points**
- 20% of image → `(0.20 - 0.08) * 280 = 33.6` → **34 points**
- 50% of image → `(0.50 - 0.08) * 280 = 117.6` → **35 points** (capped)

---

### **2. Color Uniformity Score (0-20 points)**
```python
unique_colors = len(np.unique(image_data.reshape(-1, 3), axis=0))
if unique_colors < 250:
    color_score = int(20 * (1 - unique_colors / 250))
else:
    color_score = 0
```

**How `clr` is calculated:**
1. Take all pixels in the region: `image_data.reshape(-1, 3)` → list of RGB values
2. Find unique RGB combinations: `np.unique(..., axis=0)`
3. Count them: `len(...)`
4. Display as `clr:768` (768 unique colors)

**Examples:**
- 50 unique colors → `20 * (1 - 50/250) = 20 * 0.8` → **16 points**
- 125 unique colors → `20 * (1 - 125/250) = 20 * 0.5` → **10 points**
- 250 unique colors → `20 * (1 - 250/250) = 20 * 0` → **0 points**
- 500 unique colors → **0 points** (too diverse)

---

### **3. Edge Simplicity Score (0-30 points)** ⭐ **INCREASED**
```python
edge_complexity = _calculate_edge_complexity(image_data)  # Returns 0-1
if edge_complexity < 0.4:
    edge_score = int(30 * (1 - edge_complexity / 0.4))
else:
    edge_score = 0
```

**How edge complexity is calculated:**
```python
# 1. Detect edges with Canny
edges = cv2.Canny(gray, 50, 150)

# 2. Calculate edge density
edge_density = count_edge_pixels / total_pixels

# 3. Calculate edge variance (how spread out)
edge_variance = variance_of_edge_positions / max_possible_variance

# 4. Combine
edge_complexity = (edge_density + edge_variance) / 2
```

**What it means:**
- **Low complexity (0.1)**: Edges only at borders → container
- **Medium complexity (0.3)**: Some internal detail → maybe icon
- **High complexity (0.6+)**: Edges everywhere → photo/complex icon

**Examples:**
- Edge complexity 0.1 → `30 * (1 - 0.1/0.4) = 30 * 0.75` → **22 points**
- Edge complexity 0.2 → `30 * (1 - 0.2/0.4) = 30 * 0.5` → **15 points**
- Edge complexity 0.4 → `30 * (1 - 0.4/0.4) = 30 * 0` → **0 points**
- Edge complexity 0.8 → **0 points** (too complex)

**Why highest weightage?**
- Containers always have simple, clean borders
- Icons/photos have complex internal structure
- This is the **most reliable signal** to distinguish them!

---

### **4. Fill Ratio Score (0-25 points)**
```python
fill_ratio = _calculate_fill_ratio(image_data)  # Returns 0-1
if fill_ratio > 0.70:
    fill_score = int(25 * ((fill_ratio - 0.70) / 0.30))
else:
    fill_score = 0
```

**How fill ratio is calculated:**
```python
# Use k-means clustering to find 3 dominant color groups
_, labels, centers = cv2.kmeans(pixels, k=3, ...)

# Count pixels in each cluster
cluster_counts = count_per_cluster(labels)

# Get largest cluster (most common color)
max_count = max(cluster_counts)

# Calculate ratio
fill_ratio = max_count / total_pixels
```

**What it means:**
- **High fill (90%)**: Most of region is one color → container
- **Medium fill (60%)**: Mix of colors → icon with background
- **Low fill (30%)**: Very diverse → photo

**Examples:**
- Fill ratio 0.50 → **0 points** (below threshold)
- Fill ratio 0.70 → `25 * ((0.70 - 0.70) / 0.30) = 25 * 0` → **0 points**
- Fill ratio 0.80 → `25 * ((0.80 - 0.70) / 0.30) = 25 * 0.33` → **8 points**
- Fill ratio 0.90 → `25 * ((0.90 - 0.70) / 0.30) = 25 * 0.67` → **17 points**
- Fill ratio 1.00 → `25 * ((1.00 - 0.70) / 0.30) = 25 * 1.0` → **25 points**

---

## 🧮 **Complete Example Calculations**

### **Example 1: Large Blue Container**
```
Dimensions: 293x251 (73,443 pixels)
Total image: 800x600 (480,000 pixels)
Unique colors: 84
Edge complexity: 0.15
Fill ratio: 0.84
```

**Calculations:**
1. **Size**: `73,443 / 480,000 = 0.153 (15.3%)`
   - `(0.153 - 0.08) * 280 = 20.4` → **20 points**

2. **Color**: `84 unique colors`
   - `20 * (1 - 84/250) = 20 * 0.664` → **13 points**

3. **Edge**: `0.15 complexity`
   - `30 * (1 - 0.15/0.4) = 30 * 0.625` → **19 points**

4. **Fill**: `0.84 (84% uniform)`
   - `25 * ((0.84 - 0.70) / 0.30) = 25 * 0.467` → **12 points**

**Total Score**: 20 + 13 + 19 + 12 = **64 points**
**Decision**: 64 ≥ 35 → **FILTER as container** ✓ (GREEN box)

---

### **Example 2: Small Icon**
```
Dimensions: 34x34 (1,156 pixels)
Total image: 800x600 (480,000 pixels)
Unique colors: 768
Edge complexity: 0.55
Fill ratio: 0.70
```

**Calculations:**
1. **Size**: `1,156 / 480,000 = 0.0024 (0.24%)`
   - 0.24% < 8% threshold → **0 points**

2. **Color**: `768 unique colors`
   - 768 > 250 threshold → **0 points**

3. **Edge**: `0.55 complexity`
   - 0.55 > 0.4 threshold → **0 points**

4. **Fill**: `0.70 (70% uniform)`
   - `25 * ((0.70 - 0.70) / 0.30) = 0` → **0 points**

**Total Score**: 0 + 0 + 0 + 0 = **0 points**
**Decision**: 0 < 35 → **KEEP as image** ✓ (RED box)

---

### **Example 3: Medium Icon in Circle Badge**
```
Dimensions: 66x66 (4,356 pixels)
Total image: 800x600 (480,000 pixels)
Unique colors: 115
Edge complexity: 0.42
Fill ratio: 0.91
```

**Calculations:**
1. **Size**: `4,356 / 480,000 = 0.0091 (0.91%)`
   - 0.91% < 8% threshold → **0 points**

2. **Color**: `115 unique colors`
   - `20 * (1 - 115/250) = 20 * 0.54` → **11 points**

3. **Edge**: `0.42 complexity`
   - 0.42 > 0.4 threshold → **0 points**

4. **Fill**: `0.91 (91% uniform - the blue circle)`
   - `25 * ((0.91 - 0.70) / 0.30) = 25 * 0.70` → **17 points**

**Total Score**: 0 + 11 + 0 + 17 = **28 points**
**Decision**: 28 < 35 → **KEEP as image** ✓ (RED box)

---

## 🎯 **Why Edge Weightage Was Increased**

### **Before (Edge: 20 points)**
- Size: 40, Color: 25, Edge: 20, Fill: 25
- Edge was **underweighted** compared to its importance
- Containers could slip through with high size/fill but simple edges not catching them

### **After (Edge: 30 points)**
- Size: 35, Color: 20, Edge: 30, Fill: 25
- Edge is now the **highest single heuristic**
- Reflects reality: **edge simplicity is the strongest container indicator**

### **Impact:**
```
Container with simple edges (0.15 complexity):
Before: 20 * (1 - 0.15/0.4) = 12 points
After:  30 * (1 - 0.15/0.4) = 19 points
Difference: +7 points → more likely to filter correctly!
```

---

## 📝 **Quick Reference**

| Metric | Display | Calculation | Container Behavior |
|--------|---------|-------------|-------------------|
| **Size** | `293x251` | Width × Height | Larger → higher score |
| **clr** | `clr:84` | Unique RGB combos | Fewer colors → higher score |
| **fill** | `fill:84%` | % uniform color | Higher % → higher score |
| **s** | `s:64` | Sum of 4 scores | ≥35 → filter, <35 → keep |

**Threshold**: `s:35` is the decision boundary!
