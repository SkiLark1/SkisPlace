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

    def _preprocess_for_segmentation(self, image: Image.Image) -> Image.Image:
        """
        Applies brightness conditioning to handle overexposed images.
        Tunable via env vars:
            - AI_AUTOCONTRAST: "1" to enable (default)
            - AI_BRIGHTNESS_GAMMA: float (default 1.0, >1.0 darkens midtones)
            - AI_BRIGHT_THRESHOLD: float (default 0.75) - mean luminance above this triggers adjustment
        """
        img = image.convert("RGB")
        
        enable_autocontrast = os.getenv("AI_AUTOCONTRAST", "1") == "1"
        gamma = float(os.getenv("AI_BRIGHTNESS_GAMMA", "1.2"))
        bright_threshold = float(os.getenv("AI_BRIGHT_THRESHOLD", "0.75"))
        
        # Analyze luminance
        grayscale = img.convert("L")
        pixels = np.array(grayscale).astype(np.float32) / 255.0
        mean_lum = np.mean(pixels)
        p95_lum = np.percentile(pixels, 95)
        
        is_bright = mean_lum > bright_threshold or p95_lum > 0.95
        
        if is_bright:
            logger.debug(f"Bright image detected (mean={mean_lum:.2f}, p95={p95_lum:.2f}). Applying conditioning.")
            
            # Apply autocontrast
            if enable_autocontrast:
                img = ImageOps.autocontrast(img, cutoff=1)
            
            # Apply gamma darkening (gamma > 1.0 darkens midtones)
            if gamma != 1.0 and gamma > 0:
                inv_gamma = 1.0 / gamma
                lut = [int(((i / 255.0) ** inv_gamma) * 255) for i in range(256)]
                img = img.point(lut * 3)  # Apply LUT to R, G, B channels
        
        return img

    def _letterbox_resize(self, image: Image.Image, target_size: tuple = (512, 512)) -> tuple:
        """
        Resize image preserving aspect ratio, padding with gray (128).
        Returns (resized_image, padding_info) where padding_info = (left, top, right, bottom).
        """
        img = image.convert("RGB")
        orig_w, orig_h = img.size
        target_w, target_h = target_size
        
        # Calculate scale to fit
        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        # Resize
        resized = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        
        # Pad
        pad_left = (target_w - new_w) // 2
        pad_top = (target_h - new_h) // 2
        pad_right = target_w - new_w - pad_left
        pad_bottom = target_h - new_h - pad_top
        
        # Create padded image with gray background
        padded = Image.new("RGB", target_size, (128, 128, 128))
        padded.paste(resized, (pad_left, pad_top))
        
        return padded, (pad_left, pad_top, new_w, new_h)
    
    def _undo_letterbox(self, mask: Image.Image, padding_info: tuple, original_size: tuple) -> Image.Image:
        """
        Undo letterbox padding and resize mask back to original size.
        padding_info = (left, top, content_w, content_h)
        """
        left, top, content_w, content_h = padding_info
        
        # Crop out the padded region
        cropped = mask.crop((left, top, left + content_w, top + content_h))
        
        # Resize to original
        return cropped.resize(original_size, Image.Resampling.NEAREST)

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
            image = ImageOps.exif_transpose(image)
            image = self._preprocess_for_segmentation(image)  # Brightness conditioning
            
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            
            input_size = (512, 512)
            original_size = image.size
            
            img = image.resize(input_size, Image.Resampling.BILINEAR)
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

    def get_binary_mask(self, image: Image.Image, threshold: float = 0.4, 
                        geometry_hint: str = "unknown", morphology_cleanup: bool = True) -> Optional[Image.Image]:
        """
        Returns a binary mask (0 or 255) for floor regions.
        
        CRITICAL: Thresholds at MODEL resolution (512x512), then resizes with NEAREST.
        This preserves AI output quality without BILINEAR artifacts.
        
        Args:
            image: Input image
            threshold: Probability threshold (0-1) for floor classification
            geometry_hint: "top_down" uses letterbox resize, else squash
            morphology_cleanup: If True, remove tiny islands and fill small holes
        """
        if not self.session:
            return None
            
        try:
            # 1. Preprocess
            image = ImageOps.exif_transpose(image)
            image = self._preprocess_for_segmentation(image)
            
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            
            input_size = (512, 512)
            original_size = image.size
            
            # Geometry-aware resize
            use_letterbox = geometry_hint == "top_down"
            padding_info = None
            
            if use_letterbox:
                img, padding_info = self._letterbox_resize(image, input_size)
            else:
                img = image.resize(input_size, Image.Resampling.BILINEAR)
            
            img_data = np.array(img).astype(np.float32) / 255.0
            img_data = (img_data - mean) / std
            img_data = img_data.transpose(2, 0, 1)
            img_data = np.expand_dims(img_data, axis=0)
            
            # 2. Inference
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: img_data})
            result = outputs[0][0]
            
            # 3. Get floor probability at MODEL RESOLUTION
            default_indices = "3,6,11,13"
            env_indices = os.getenv("AI_FLOOR_INDICES", default_indices)
            floor_indices = [int(x) for x in env_indices.split(",")]
            
            max_val = np.max(result, axis=0)
            exp_logits = np.exp(result - max_val)
            probs = exp_logits / np.sum(exp_logits, axis=0)
            
            floor_prob = np.zeros(probs[0].shape, dtype=np.float32)
            for idx in floor_indices:
                if idx < probs.shape[0]:
                    floor_prob += probs[idx]
            
            # 4. THRESHOLD AT MODEL RESOLUTION (512x512)
            # Mission 29: Dual Threshold Logic ("Confidence Edge")
            # a. Core Mask (High Confidence)
            thresh_core = threshold
            mask_core = (floor_prob >= thresh_core)
            
            # b. Soft Mask (Low Confidence - for expansion)
            thresh_edge = threshold * 0.6 # e.g. 0.3 if thresh=0.5
            mask_soft = (floor_prob >= thresh_edge)
            
            # c. Grow Core into Soft
            # Dilate core to find adjacent candidates
            from scipy import ndimage
            structure_growth = ndimage.generate_binary_structure(2, 2) # Connectivity 2 (8-neighbors)
            # Dilate core by ~15 pixels (at 512px) to jump gaps to shadows
            mask_core_grown = ndimage.binary_dilation(mask_core, structure=structure_growth, iterations=15)
            
            # Final = Core OR (Soft AND Grown)
            # We keep everything in Core.
            # We add pixels from Soft Mask ONLY if they are near the Core.
            binary_bool = mask_core | (mask_soft & mask_core_grown)
            
            # 5. Optional morphology cleanup (at model resolution)
            if morphology_cleanup:
                # Remove small islands (opening = erode then dilate)
                structure = ndimage.generate_binary_structure(2, 1)
                binary_bool = ndimage.binary_opening(binary_bool, structure=structure, iterations=2)
                
                # Fill small holes (closing = dilate then erode)
                binary_bool = ndimage.binary_closing(binary_bool, structure=structure, iterations=2)
                
            # Mission 28: Edge Coverage Fix
            # Dilate final mask by small amount (3px) to ensure wall contact
            # This fixes "1px gap" issues.
            binary_bool = ndimage.binary_dilation(binary_bool, structure=ndimage.generate_binary_structure(2, 1), iterations=2)
                
            binary_mask = binary_bool.astype(np.uint8) * 255
            
            mask_img = Image.fromarray(binary_mask, mode='L')
            
            # 6. RESIZE WITH NEAREST (preserves binary edges)
            if use_letterbox and padding_info:
                mask_img = self._undo_letterbox(mask_img, padding_info, original_size)
            else:
                mask_img = mask_img.resize(original_size, Image.Resampling.NEAREST)
            
            return mask_img
            
        except Exception as e:
            logger.error(f"AI Binary Mask failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_probability_map(self, image: Image.Image, geometry_hint: str = "unknown") -> Optional[Image.Image]:
        """
        Returns the raw probability map (0-255) where 255 = 100% Floor confidence.
        Uses letterbox resizing for top_down images to preserve aspect ratio.
        """
        if not self.session:
            return None
            
        try:
            # 1. Preprocess
            image = ImageOps.exif_transpose(image)
            image = self._preprocess_for_segmentation(image)  # Brightness conditioning
            
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            
            input_size = (512, 512)
            original_size = image.size
            
            # Geometry-aware resize selection
            use_letterbox = geometry_hint == "top_down"
            padding_info = None
            
            if use_letterbox:
                logger.debug("Using letterbox resize for top-down image")
                img, padding_info = self._letterbox_resize(image, input_size)
            else:
                logger.debug("Using squash resize for eye-level image")
                img = image.resize(input_size, Image.Resampling.BILINEAR)
            
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
            if use_letterbox and padding_info:
                prob_img = self._undo_letterbox(prob_img, padding_info, original_size)
            else:
                prob_img = prob_img.resize(original_size, Image.Resampling.BILINEAR)
            
            return prob_img
            
        except Exception as e:
            logger.error(f"AI Probability Map failed: {e}")
            return None
