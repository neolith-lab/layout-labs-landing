#!/usr/bin/env python3
"""
Test script to verify ML pipeline installation
"""

import sys

def check_import(module_name, package_name=None):
    """Check if a module can be imported"""
    package_name = package_name or module_name
    try:
        __import__(module_name)
        print(f"  ✓ {package_name}")
        return True
    except ImportError as e:
        print(f"  ✗ {package_name}: {e}")
        return False

def main():
    print("=" * 50)
    print("ML Pipeline Installation Check")
    print("=" * 50)
    
    all_ok = True
    
    # Core dependencies
    print("\n1. Core dependencies:")
    all_ok &= check_import("torch", "PyTorch")
    all_ok &= check_import("torchvision")
    all_ok &= check_import("numpy")
    all_ok &= check_import("cv2", "OpenCV")
    all_ok &= check_import("PIL", "Pillow")
    all_ok &= check_import("svgwrite")
    
    # Check device
    print("\n2. Compute device:")
    try:
        import torch
        if torch.cuda.is_available():
            print(f"  ✓ CUDA available: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            print("  ✓ MPS (Apple Silicon) available")
        else:
            print("  ⚠ Using CPU (slower)")
    except Exception as e:
        print(f"  ✗ Device check failed: {e}")
    
    # SAM
    print("\n3. Segmentation (SAM):")
    sam_ok = False
    try:
        from sam2.build_sam import build_sam2
        print("  ✓ SAM 2")
        sam_ok = True
    except ImportError:
        try:
            from segment_anything import sam_model_registry
            print("  ✓ SAM 1 (fallback)")
            sam_ok = True
        except ImportError:
            print("  ✗ SAM not installed")
    all_ok &= sam_ok
    
    # CLIP
    print("\n4. Classification (CLIP):")
    clip_ok = False
    try:
        import clip
        print("  ✓ OpenAI CLIP")
        clip_ok = True
    except ImportError:
        try:
            from transformers import CLIPModel
            print("  ✓ Transformers CLIP (fallback)")
            clip_ok = True
        except ImportError:
            print("  ✗ CLIP not installed")
    all_ok &= clip_ok
    
    # Inpainting
    print("\n5. Inpainting (LaMa):")
    inpaint_ok = False
    try:
        from simple_lama_inpainting import SimpleLama
        print("  ✓ simple-lama-inpainting")
        inpaint_ok = True
    except ImportError:
        print("  ⚠ LaMa not installed (will use OpenCV fallback)")
        inpaint_ok = True  # Not critical, has fallback
    
    # OCR
    print("\n6. OCR:")
    ocr_ok = False
    try:
        from paddleocr import PaddleOCR
        print("  ✓ PaddleOCR")
        ocr_ok = True
    except ImportError:
        try:
            import easyocr
            print("  ✓ EasyOCR (fallback)")
            ocr_ok = True
        except ImportError:
            print("  ✗ No OCR library installed")
    all_ok &= ocr_ok
    
    # SAM checkpoint
    print("\n7. SAM checkpoint:")
    from pathlib import Path
    checkpoint_dir = Path.home() / ".cache" / "sam_checkpoints"
    checkpoints = [
        "sam_vit_h_4b8939.pth",
        "sam_vit_l_0b3195.pth", 
        "sam_vit_b_01ec64.pth",
        "sam2_hiera_large.pt",
    ]
    checkpoint_found = False
    for ckpt in checkpoints:
        if (checkpoint_dir / ckpt).exists():
            print(f"  ✓ Found: {ckpt}")
            checkpoint_found = True
            break
    if not checkpoint_found:
        print("  ⚠ No checkpoint found (will download on first use)")
    
    # Summary
    print("\n" + "=" * 50)
    if all_ok:
        print("✓ All critical components installed!")
        print("\nReady to use:")
        print("  python -m ml_pipeline.cli input.png -o output.svg")
    else:
        print("✗ Some components missing")
        print("\nRun setup script:")
        print("  bash ml_pipeline/setup.sh")
    print("=" * 50)
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
