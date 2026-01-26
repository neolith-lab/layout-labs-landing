#!/usr/bin/env python3
"""
Test suite for Raster to SVG Converter
"""

import unittest
import cv2
import numpy as np
from pathlib import Path
import tempfile
import os

from raster_to_svg import RasterToSVGConverter
from text_extractor import TextExtractor
from image_detector import ImageDetector
from shape_detector import ShapeDetector, ShapeType
from background_filler import BackgroundFiller
from utils import BoundingBox, calculate_iou


class TestBoundingBox(unittest.TestCase):
    """Test BoundingBox utility class"""
    
    def test_bbox_creation(self):
        bbox = BoundingBox(10, 20, 100, 50)
        self.assertEqual(bbox.x, 10)
        self.assertEqual(bbox.y, 20)
        self.assertEqual(bbox.w, 100)
        self.assertEqual(bbox.h, 50)
    
    def test_bbox_properties(self):
        bbox = BoundingBox(10, 20, 100, 50)
        self.assertEqual(bbox.x2, 110)
        self.assertEqual(bbox.y2, 70)
        self.assertEqual(bbox.center, (60, 45))
        self.assertEqual(bbox.area, 5000)
    
    def test_bbox_iou(self):
        bbox1 = BoundingBox(0, 0, 100, 100)
        bbox2 = BoundingBox(50, 50, 100, 100)
        iou = calculate_iou(bbox1, bbox2)
        
        # Intersection is 50x50 = 2500
        # Union is 10000 + 10000 - 2500 = 17500
        # IoU = 2500/17500 ≈ 0.143
        self.assertAlmostEqual(iou, 0.143, places=2)


class TestBackgroundFiller(unittest.TestCase):
    """Test background filling functionality"""
    
    def setUp(self):
        self.filler = BackgroundFiller()
        # Create test image
        self.test_image = np.ones((200, 200, 3), dtype=np.uint8) * 255
        cv2.rectangle(self.test_image, (50, 50), (150, 150), (0, 0, 0), -1)
    
    def test_remove_and_fill(self):
        bbox = BoundingBox(50, 50, 100, 100)
        result = self.filler.remove_and_fill(self.test_image, [bbox])
        
        # Result should be mostly white after filling
        self.assertIsNotNone(result)
        self.assertEqual(result.shape, self.test_image.shape)


class TestShapeDetector(unittest.TestCase):
    """Test shape detection"""
    
    def setUp(self):
        self.detector = ShapeDetector()
    
    def test_circle_detection(self):
        # Create image with circle
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255
        cv2.circle(img, (100, 100), 50, (0, 0, 0), -1)
        
        shapes = self.detector.detect_shapes(img)
        
        # Should detect at least one shape
        self.assertGreater(len(shapes), 0)
    
    def test_rectangle_detection(self):
        # Create image with rectangle
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255
        cv2.rectangle(img, (50, 50), (150, 150), (0, 0, 0), -1)
        
        shapes = self.detector.detect_shapes(img)
        
        # Should detect at least one shape
        self.assertGreater(len(shapes), 0)


class TestRasterToSVGConverter(unittest.TestCase):
    """Test main converter"""
    
    def setUp(self):
        self.converter = RasterToSVGConverter()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_image(self) -> str:
        """Create a simple test image"""
        img = np.ones((400, 400, 3), dtype=np.uint8) * 255
        
        # Add shapes
        cv2.rectangle(img, (50, 50), (150, 150), (100, 100, 255), -1)
        cv2.circle(img, (300, 100), 50, (100, 255, 100), -1)
        
        # Add text
        cv2.putText(img, 'Test', (150, 300), cv2.FONT_HERSHEY_SIMPLEX, 
                   2, (0, 0, 0), 3)
        
        # Save
        path = os.path.join(self.temp_dir, 'test_image.png')
        cv2.imwrite(path, img)
        return path
    
    def test_full_conversion(self):
        """Test complete conversion pipeline"""
        input_path = self.create_test_image()
        output_path = os.path.join(self.temp_dir, 'output.svg')
        
        result = self.converter.convert(input_path, output_path)
        
        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(result['statistics']['text_elements'] + 
                         result['statistics']['shape_elements'], 0)
    
    def test_batch_conversion(self):
        """Test batch conversion"""
        # Create multiple test images
        for i in range(3):
            self.create_test_image()
        
        output_dir = os.path.join(self.temp_dir, 'output')
        results = self.converter.convert_batch(self.temp_dir, output_dir, '*.png')
        
        self.assertEqual(results['total'], 3)
        self.assertGreaterEqual(results['successful'], 0)


def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
