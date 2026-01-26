#!/bin/bash
# Quick commands for Modal deployment

# Setup (run once)
echo "Setting up Modal..."
pip install modal
modal token new

# Test deployment
echo "Testing deployment..."
python test_deployment.py

# Single file conversion
echo "Converting single file..."
modal run main.py \
  --input-path ../dev_destructure/input.png \
  --output-path output.svg

# Single file with debug
modal run main.py \
  --input-path ../dev_destructure/input.png \
  --output-path output.svg \
  --debug

# Batch conversion
modal run main.py \
  --input-path ../dev_destructure/sample_data \
  --output-path ./output \
  --batch \
  --pattern "*.png"

# Custom OCR confidence
modal run main.py \
  --input-path image.png \
  --output-path output.svg \
  --ocr-confidence 70

# View logs
modal app logs raster-to-svg-converter

# Stop app
modal app stop raster-to-svg-converter

# List apps
modal app list
