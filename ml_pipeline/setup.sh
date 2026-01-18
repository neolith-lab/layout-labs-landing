#!/bin/bash
# Setup script for ML Pipeline
# Run: bash setup.sh

set -e

echo "======================================"
echo "ML Pipeline Setup"
echo "======================================"

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
python_major=$(echo "$python_version" | cut -d'.' -f1)
python_minor=$(echo "$python_version" | cut -d'.' -f2)
echo "Python version: $python_version"

if [[ "$python_major" -lt 3 ]] || [[ "$python_major" -eq 3 && "$python_minor" -lt 9 ]]; then
    echo "Error: Python 3.9+ required (found $python_version)"
    exit 1
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Detect GPU
echo ""
echo "Detecting GPU..."

if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected"
    GPU_TYPE="cuda"
elif [[ "$(uname)" == "Darwin" ]] && [[ "$(uname -m)" == "arm64" ]]; then
    echo "Apple Silicon detected (MPS)"
    GPU_TYPE="mps"
else
    echo "No GPU detected, using CPU"
    GPU_TYPE="cpu"
fi

# Install PyTorch
echo ""
echo "Installing PyTorch..."

if [ "$GPU_TYPE" == "cuda" ]; then
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
elif [ "$GPU_TYPE" == "mps" ]; then
    pip install torch torchvision
else
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
fi

# Install main requirements
echo ""
echo "Installing requirements..."
pip install -r ml_pipeline/requirements.txt

# Install SAM
echo ""
echo "Installing Segment Anything..."

# Try SAM 2 first
pip install sam2 2>/dev/null || {
    echo "SAM 2 not available, installing SAM 1..."
    pip install git+https://github.com/facebookresearch/segment-anything.git
}

# Install CLIP
echo ""
echo "Installing CLIP..."
pip install git+https://github.com/openai/CLIP.git 2>/dev/null || {
    echo "OpenAI CLIP not available, using transformers..."
    pip install transformers
}

# Install LaMa
echo ""
echo "Installing inpainting..."
pip install simple-lama-inpainting 2>/dev/null || {
    echo "simple-lama not available, will use OpenCV fallback"
}

# Install PaddleOCR
echo ""
echo "Installing PaddleOCR..."
pip install paddlepaddle paddleocr 2>/dev/null || {
    echo "PaddleOCR failed, installing EasyOCR as fallback..."
    pip install easyocr
}

# Download SAM model
echo ""
echo "Downloading SAM model checkpoint..."

mkdir -p ~/.cache/sam_checkpoints

SAM_CHECKPOINT="$HOME/.cache/sam_checkpoints/sam_vit_h_4b8939.pth"
if [ ! -f "$SAM_CHECKPOINT" ]; then
    echo "Downloading SAM ViT-H checkpoint (2.4GB)..."
    curl -L -o "$SAM_CHECKPOINT" \
        "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
else
    echo "SAM checkpoint already exists"
fi

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "To use:"
echo "  source venv/bin/activate"
echo "  python -m ml_pipeline.cli input.png -o output.svg"
echo ""
echo "For help:"
echo "  python -m ml_pipeline.cli --help"
echo ""
