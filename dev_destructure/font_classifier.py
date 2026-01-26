import argparse
import albumentations as A
import csv
import cv2
from dataclasses import dataclass
import huggingface_hub
import numpy as np
import onnxruntime as ort
import os
import yaml
import logging

from PIL import Image
from train import CutMax, ResizeWithPad

logger = logging.getLogger(__name__)

CONFIG_PATH = huggingface_hub.hf_hub_download(
    repo_id="storia/font-classify-onnx", filename="model_config.yaml"
)
MODEL_PATH = huggingface_hub.hf_hub_download(
    repo_id="storia/font-classify-onnx", filename="model.onnx"
)
MAPPING_PATH = "google_fonts_mapping.tsv"


@dataclass
class FontPrediction:
    """Result of font classification"""
    font_name: str
    font_version: str
    confidence: float
    raw_probabilities: np.ndarray = None


class FontClassifier:
    """Font classifier using ONNX model from Storia"""
    
    def __init__(self, config_path: str = None, model_path: str = None, mapping_path: str = None):
        """
        Initialize font classifier
        
        Args:
            config_path: Path to model config YAML (optional, uses default if None)
            model_path: Path to ONNX model (optional, uses default if None)
            mapping_path: Path to Google Fonts mapping TSV (optional, uses default if None)
        """
        self.config_path = config_path or CONFIG_PATH
        self.model_path = model_path or MODEL_PATH
        self.mapping_path = mapping_path or MAPPING_PATH
        
        # Load config
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        self.input_size = self.config["size"]
        
        # Load Google Fonts mapping
        self.google_font_mapping = {}
        with open(self.mapping_path, "r") as f:
            tsv_file = csv.reader(f, delimiter="\t")
            for i, row in enumerate(tsv_file):
                if i > 0:
                    filename, font_name, version = row
                    self.google_font_mapping[filename] = (font_name, version)
        
        # Initialize ONNX session
        self.session = ort.InferenceSession(self.model_path)
        
        # Setup image transform pipeline
        self.transform = A.Compose([
            A.Lambda(image=CutMax(1024)),
            A.Lambda(image=ResizeWithPad((self.input_size, self.input_size))),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        
        logger.info("FontClassifier initialized successfully")
    
    def predict(self, image: np.ndarray) -> FontPrediction:
        """
        Predict font from image
        
        Args:
            image: Input image as numpy array (BGR or RGB format)
        
        Returns:
            FontPrediction object with font name, version, and confidence
        """
        # Ensure image is in RGB format
        if len(image.shape) == 2:
            # Grayscale to RGB
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            # RGBA to RGB
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        elif image.shape[2] == 3:
            # Assume BGR, convert to RGB
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Apply transforms
        transformed = self.transform(image=image)["image"]
        
        # Move the channel dimension to the front
        transformed = np.transpose(transformed, (2, 0, 1))
        
        # Add a dummy batch dimension
        transformed = np.expand_dims(transformed, 0)
        
        # Run inference
        logits = self.session.run(None, {"input": transformed})[0][0]
        probs = softmax(logits)
        
        # Get prediction
        predicted_idx = probs.argmax(0)
        predicted_classname = self.config["classnames"][predicted_idx]
        confidence = float(probs[predicted_idx])
        
        # Get font name and version from mapping
        font_info = self.google_font_mapping.get(predicted_classname, (predicted_classname, ""))
        font_name = font_info[0]
        font_version = font_info[1] if len(font_info) > 1 else ""
        
        return FontPrediction(
            font_name=font_name,
            font_version=font_version,
            confidence=confidence,
            raw_probabilities=probs
        )
    
    def predict_batch(self, images: list) -> list:
        """
        Predict fonts for multiple images
        
        Args:
            images: List of numpy arrays (images)
        
        Returns:
            List of FontPrediction objects
        """
        return [self.predict(img) for img in images]


# Singleton instance
_font_classifier_instance = None


def get_font_classifier() -> FontClassifier:
    """Get singleton instance of font classifier"""
    global _font_classifier_instance
    if _font_classifier_instance is None:
        _font_classifier_instance = FontClassifier()
    return _font_classifier_instance


def parse_args():
    # Create an argument parser
    parser = argparse.ArgumentParser(
        description="Inference with pretrained model from Storia"
    )
    parser.add_argument(
        "--data_folder",
        type=str,
        default="sample_data/output",
        help="Path to images to run inference on",
    )
    args = parser.parse_args()
    return args


def softmax(x):
    """Computes softmax values for each sets of scores in x."""
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=0)  # axis=0 for 2d array case


def main(args):
    classifier = get_font_classifier()

    for image_file in os.listdir(args.data_folder):
        image_path = os.path.join(args.data_folder, image_file)
        image = Image.open(image_path).convert("RGB")
        image = np.array(image)

        prediction = classifier.predict(image)

        print(
            image_file,
            prediction.font_name,
            prediction.font_version,
            prediction.confidence,
        )


if __name__ == "__main__":
    args = parse_args()

    main(args)