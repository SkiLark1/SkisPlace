import os
import logging
from typing import Optional
from PIL import Image, ImageOps
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

class FloorSegmenter:
    _instance = None
    
    def __init__(self):
        self.session = None
        self.model_path = os.getenv("AI_MODEL_PATH", "models/model.onnx")
        self._load_model()
        
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def _load_model(self):
        """Attempts to load the ONNX model if available."""
        try:
            import onnxruntime as ort
            if os.path.exists(self.model_path):
                logger.info(f"Loading AI Model from {self.model_path}...")
                self.session = ort.InferenceSession(self.model_path)
                logger.info("AI Model loaded successfully.")
            else:
                logger.warning(f"AI Model not found at {self.model_path}. AI segmentation will be disabled.")
        except Exception as e:
            logger.error(f"Failed to initialize ONNX Runtime: {e}")
            self.session = None

    def segment(self, image: Image.Image, confidence_threshold: float = 0.5) -> Optional[Image.Image]:
        """
        Segments the floor from the given image using the loaded ONNX model.
        Returns a binary PIL Image (L mode) where 255=Floor, 0=Background.
        Uses Softmax to respect confidence_threshold and combines multiple floor-like classes.
        """
        if not self.session:
            return None
            
        try:
            # 1. Preprocess
            # Handle orientation
            image = ImageOps.exif_transpose(image)
            
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            
            input_size = (512, 512)
            original_size = image.size
            
            # Simple Resize (Squash) - proven more robust for this model
            img = image.convert('RGB').resize(input_size, Image.Resampling.BILINEAR)
            img_data = np.array(img).astype(np.float32) / 255.0
            
            # Normalize and Transpose (HWC -> CHW)
            img_data = (img_data - mean) / std
            img_data = img_data.transpose(2, 0, 1)
            img_data = np.expand_dims(img_data, axis=0) # Add batch dim
            
            # 2. Inference
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: img_data})
            result = outputs[0][0] # [Classes, H, W]
            
            # 3. Postprocess
            # Define floor-like classes (ADE20k indices: 3=floor, 6=road, 11=sidewalk, 13=earth, 29=rug, 9=grass)
            # We default to floor, road, sidewalk, earth for robustness in garages/basements
            default_indices = "3,6,11,13"
            env_indices = os.getenv("AI_FLOOR_INDICES", default_indices)
            floor_indices = [int(x) for x in env_indices.split(",")]
            
            # Softmax to get probabilities
            # Stable Softmax: exp(x - max) / sum(exp(x - max))
            max_val = np.max(result, axis=0)
            exp_logits = np.exp(result - max_val)
            probs = exp_logits / np.sum(exp_logits, axis=0)
            
            # Sum prob of all floor-like classes
            floor_prob = np.zeros(probs[0].shape, dtype=np.float32)
            for idx in floor_indices:
                if idx < probs.shape[0]:
                    floor_prob += probs[idx]
            
            # Threshold
            binary_mask = (floor_prob > confidence_threshold).astype(np.uint8) * 255
            
            # Create PIL Image
            mask_img = Image.fromarray(binary_mask, mode='L')
            
            # Resize back to original
            mask_img = mask_img.resize(original_size, Image.Resampling.NEAREST)
            
            return mask_img
            
        except Exception as e:
            logger.error(f"AI Segmentation failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_probability_map(self, image: Image.Image) -> Optional[Image.Image]:
        """
        Returns the raw probability map (0-255) where 255 = 100% Floor confidence.
        """
        if not self.session:
            return None
            
        try:
            # 1. Preprocess
            # Handle orientation
            image = ImageOps.exif_transpose(image)
            
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            
            input_size = (512, 512)
            original_size = image.size
            
            # Simple Resize (Squash)
            img = image.convert('RGB').resize(input_size, Image.Resampling.BILINEAR)
            img_data = np.array(img).astype(np.float32) / 255.0
            
            # Normalize and Transpose (HWC -> CHW)
            img_data = (img_data - mean) / std
            img_data = img_data.transpose(2, 0, 1)
            img_data = np.expand_dims(img_data, axis=0) # Add batch dim
            
            # 2. Inference
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: img_data})
            result = outputs[0][0] # [Classes, H, W]
            
            # 3. Postprocess
            # Define floor-like classes
            default_indices = "3,6,11,13"
            env_indices = os.getenv("AI_FLOOR_INDICES", default_indices)
            floor_indices = [int(x) for x in env_indices.split(",")]
            
            # Softmax to get probabilities
            max_val = np.max(result, axis=0)
            exp_logits = np.exp(result - max_val)
            probs = exp_logits / np.sum(exp_logits, axis=0)
            
            # Sum prob of all floor-like classes
            floor_prob = np.zeros(probs[0].shape, dtype=np.float32)
            for idx in floor_indices:
                if idx < probs.shape[0]:
                    floor_prob += probs[idx]
            
            # Convert to 0-255 map
            prob_map = (floor_prob * 255).astype(np.uint8)
            prob_img = Image.fromarray(prob_map, mode='L')
            
            # Resize back to original
            prob_img = prob_img.resize(original_size, Image.Resampling.BILINEAR)
            
            return prob_img
            
        except Exception as e:
            logger.error(f"AI Probability Map failed: {e}")
            return None
