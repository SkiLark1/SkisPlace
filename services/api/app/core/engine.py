import os
import base64
import io
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFilter, ImageChops

from app.core.segmentation import FloorSegmenter
from app.core.geometry import detect_camera_geometry

def process_image(input_path: str, output_path: str, parameters: dict, debug: bool = False, custom_mask: str | None = None, ai_config: dict | None = None) -> dict:
    """
    Process the image to apply a simulated epoxy finish.
    
    Args:
        input_path: Path to source image.
        output_path: Path to save result.
        parameters: Style parameters.
            - color: Hex color (default: #a1a1aa)
            - blend_strength: 0.0 to 1.0 (default 1.0). How much epoxy vs original.
            - gamma: 0.1 to 5.0 (default 1.0). Adjusts contrast of floor texture under epoxy.
            - brightness_boost: Multiplier (default 1.8). Replaces old hardcoded 1.8.
            - finish: 'gloss', 'satin', 'matte' (default 'gloss').
        debug: If True, saves intermediate assets (like mask) and returns their paths.
        custom_mask: Base64 string of user-drawn mask.
        ai_config: Configuration for AI segmentation.
            - enabled: bool
            - confidence_threshold: float

    Returns:
        dict: {"success": bool, "mask_filename": str|None, "message": str, "mask_source": str}
    """
    result_info = {"success": False, "mask_filename": None, "message": "", "mask_source": "heuristic", "camera_geometry": "unknown"}

    # 1. Load Image
    try:
        original = Image.open(input_path).convert("RGBA")
    except Exception as e:
        print(f"Error opening image: {e}")
        result_info["message"] = f"Error opening image: {e}"
        return result_info
        
    width, height = original.size
    
    # Analyze Geometry
    geometry = detect_camera_geometry(original, debug=True)
    result_info["camera_geometry"] = geometry
    print(f"DEBUG: Detected Camera Geometry: {geometry}")
    

    # 2. Generate Mask
    mask = None
    mask_source = "heuristic" # Default assumption

    # Extract common parameters
    mask_blur = int(parameters.get("mask_blur", 5))

    # A. Custom Mask (User Refinement - Highest Priority)
    if custom_mask:
        try:
            # Decode Base64 (starts with "data:image/png;base64,...")
            if "," in custom_mask:
                header, encoded = custom_mask.split(",", 1)
            else:
                encoded = custom_mask
            
            mask_data = base64.b64decode(encoded)
            user_mask = Image.open(io.BytesIO(mask_data)).convert("L")
            
            # Resize to match original if needed
            if user_mask.size != (width, height):
                user_mask = user_mask.resize((width, height), Image.Resampling.LANCZOS)
            
            mask = user_mask
            print("DEBUG: Using custom user mask")
            result_info["mask_source"] = "user"
            mask_source = "user"
        except Exception as e:
            print(f"ERROR: Failed to process custom mask: {e}")
            # Fallback to heuristic
            mask = None

    # B. Base Heuristic Mask (If no user mask)
    if mask is None:
        result_info["mask_source"] = "heuristic"
        mask_source = "heuristic"
        
        # Geometry-Aware Base
        is_top_down = result_info.get("camera_geometry") == "top_down"
        
        if is_top_down:
            # Top-Down: AI-first strategy (NOT full white)
            print("DEBUG: Top-Down geometry detected - using AI-first strategy")
            ai_mask_used = False
            
            # Try AI mask directly for top-down
            if ai_config and ai_config.get("enabled", False):
                try:
                    geometry_hint = "top_down"
                    # Check if AI model is actually loaded
                    segmenter = FloorSegmenter.instance()
                    if not segmenter.session:
                        print(f"DEBUG: AI Model NOT loaded (path: {segmenter.model_path})")
                    else:
                        # Use stricter threshold for top-down
                        min_floor_prob = float(ai_config.get("min_floor_prob", 0.4))
                        prob_map = segmenter.get_probability_map(original, geometry_hint=geometry_hint)
                        
                        if prob_map:
                            import numpy as np
                            # Apply stricter threshold for top-down
                            threshold_255 = int(min_floor_prob * 255)
                            print(f"DEBUG: Top-Down AI - Using min_floor_prob threshold: {min_floor_prob} ({threshold_255}/255)")
                            mask = prob_map.point(lambda p: 255 if p >= threshold_255 else 0)
                            result_info["mask_source"] = "ai_direct"
                            ai_mask_used = True
                            print("DEBUG: Top-Down AI mask applied directly")
                except Exception as e:
                    print(f"DEBUG: Top-Down AI mask failed: {e}")
            
            # Fallback: Center-weighted vignette (not full white)
            if not ai_mask_used:
                print("DEBUG: Top-Down fallback - using center-weighted vignette")
                mask = Image.new("L", (width, height), 255)
                draw = ImageDraw.Draw(mask)
                
                # Create vignette: fade to 0 near edges
                border_pct = 0.08  # 8% border kill zone
                fade_pct = 0.12   # 12% fade zone
                
                border_x = int(width * border_pct)
                border_y = int(height * border_pct)
                fade_x = int(width * fade_pct)
                fade_y = int(height * fade_pct)
                
                # Horizontal edge suppression
                for x in range(border_x + fade_x):
                    if x < border_x:
                        alpha = 0
                    else:
                        alpha = int(255 * ((x - border_x) / fade_x))
                    draw.line((x, 0, x, height), fill=alpha)
                    draw.line((width - 1 - x, 0, width - 1 - x, height), fill=alpha)
                
                # Vertical edge suppression (multiply with existing)
                v_mask = Image.new("L", (width, height), 255)
                v_draw = ImageDraw.Draw(v_mask)
                for y in range(border_y + fade_y):
                    if y < border_y:
                        alpha = 0
                    else:
                        alpha = int(255 * ((y - border_y) / fade_y))
                    v_draw.line((0, y, width, y), fill=alpha)
                    v_draw.line((0, height - 1 - y, width, height - 1 - y), fill=alpha)
                
                mask = ImageChops.multiply(mask, v_mask)
                result_info["mask_source"] = "heuristic_vignette"
        else:
            # Eye-Level: Vertical Gradient
            mask_start = float(parameters.get("mask_start", 0.45))
            mask_end = float(parameters.get("mask_end", 1.0))
            mask_falloff = float(parameters.get("mask_falloff", 1.0))
            
            mask = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(mask)
            
            start_y = int(height * mask_start)
            end_y = int(height * mask_end)
            
            if end_y > start_y:
                for y in range(start_y, height):
                    if y >= end_y:
                        t = 1.0
                    else:
                        t = (y - start_y) / (end_y - start_y)
                    
                    alpha_val = int(255 * (t ** mask_falloff))
                    draw.line((0, y, width, y), fill=alpha_val)

    # C. AI Refinement (If enabled and not user mask)
    # Skip if mask_source is already AI-based (ai_direct, etc.)
    if mask_source == "heuristic" or mask_source == "heuristic_vignette":
        if ai_config and ai_config.get("enabled", False):
            try:
                import numpy as np
                from scipy import ndimage
                
                confidence = float(ai_config.get("confidence_threshold", 0.5))
                
                # Geometry-aware min_floor_prob_to_keep threshold
                geometry_hint = result_info.get("camera_geometry", "unknown")
                is_top_down = geometry_hint == "top_down"
                
                # Stricter threshold for top-down to prevent over-prediction
                default_min_floor_prob = 0.45 if is_top_down else 0.25
                min_floor_prob = float(ai_config.get("min_floor_prob_to_keep", default_min_floor_prob))
                
                print(f"DEBUG: Attempting AI Refinement. Removal Confidence: {confidence}, Min Floor Prob: {min_floor_prob} (geometry: {geometry_hint})")
                
                # Get raw probability map (0-255) - Pass geometry hint for letterbox/squash selection
                prob_map = FloorSegmenter.instance().get_probability_map(original, geometry_hint=geometry_hint)
                
                if prob_map:
                    # Calculate keep threshold: max of confidence-based and min_floor_prob
                    confidence_threshold_255 = int((1.0 - confidence) * 255)
                    min_floor_threshold_255 = int(min_floor_prob * 255)
                    
                    # Use the STRICTER (higher) of the two thresholds
                    keep_threshold = max(confidence_threshold_255, min_floor_threshold_255)
                    keep_threshold = max(1, min(254, keep_threshold))
                
                    print(f"DEBUG: AI Refinement - Keeping pixels with Floor Prob >= {keep_threshold}/255")
                    
                    # Create binary refinement mask: White = Keep, Black = Remove
                    refinement_mask = prob_map.point(lambda p: 255 if p >= keep_threshold else 0)
                    
                    # --- SANITY CHECK ---
                    ai_arr = np.array(refinement_mask)
                    total_pixels = ai_arr.size
                    white_pixels = np.sum(ai_arr > 127)
                    coverage = white_pixels / total_pixels if total_pixels > 0 else 0.0
                    
                    print(f"DEBUG: AI Mask Coverage: {coverage*100:.1f}%")
                    
                    # Coverage Thresholds
                    MIN_COVERAGE = 0.08  # 8%
                    
                    if coverage < MIN_COVERAGE:
                        # AI mask is too small - use Hybrid Fallback
                        print(f"DEBUG: AI coverage too low ({coverage*100:.1f}% < {MIN_COVERAGE*100:.1f}%). Using Hybrid Fallback (Union).")
                        
                        # Hybrid = Union of heuristic base and AI mask
                        base_arr = np.array(mask)
                        combined_arr = np.maximum(base_arr, ai_arr)
                        mask = Image.fromarray(combined_arr.astype(np.uint8), mode="L")
                        result_info["mask_source"] = "ai_hybrid_fallback"
                    else:
                        # Apply AI refinement normally
                        # First, Apply Largest Connected Component Filter
                        binary_mask = (ai_arr > 127).astype(np.uint8)
                        labeled, num_features = ndimage.label(binary_mask)
                        
                        if num_features > 1:
                            component_sizes = ndimage.sum(binary_mask, labeled, range(1, num_features + 1))
                            largest_label = np.argmax(component_sizes) + 1
                            binary_mask = (labeled == largest_label).astype(np.uint8)
                            refinement_mask = Image.fromarray((binary_mask * 255).astype(np.uint8), mode="L")
                            print(f"DEBUG: Connected Component Filter: Kept largest of {num_features} regions.")
                        
                        # Combine: Final = Base * Refinement
                        mask = ImageChops.multiply(mask, refinement_mask)
                        result_info["mask_source"] = "ai_refined"
                        
                    print("DEBUG: AI Refinement step complete")
                else:
                    print("DEBUG: AI Segmentation returned no probability map")
            except Exception as e:
                print(f"ERROR: AI Refinement failed: {e}")
                import traceback
                traceback.print_exc()

    # D. Edge Feathering (Geometry & Source Aware)
    # Apply feathering if it's Eye-Level AND (Heuristic OR AI-Refined)
    # Don't feather Top-Down or Custom User masks.
    should_feather = (result_info.get("camera_geometry") != "top_down") and (result_info.get("mask_source") != "user")
    
    if width > 0 and should_feather:
        h_mask = Image.new("L", (width, height), 255)
        h_draw = ImageDraw.Draw(h_mask)
        fade_width = int(width * 0.15)
        for x in range(fade_width):
            alpha = int(255 * (x / fade_width))
            h_draw.line((x, 0, x, height), fill=alpha)
            h_draw.line((width - 1 - x, 0, width - 1 - x, height), fill=alpha)
        mask = ImageChops.multiply(mask, h_mask)

    mask = mask.filter(ImageFilter.GaussianBlur(radius=mask_blur))
    
    # E. Compute Mask Stats (always, for debugging)
    import numpy as np
    mask_arr = np.array(mask)
    result_info["mask_stats"] = {
        "mean": float(np.mean(mask_arr)),
        "min": int(np.min(mask_arr)),
        "max": int(np.max(mask_arr)),
        "pct_white": float(np.sum(mask_arr >= 250) / mask_arr.size * 100),
        "pct_black": float(np.sum(mask_arr <= 5) / mask_arr.size * 100)
    }
    print(f"DEBUG: Mask Stats - Mean: {result_info['mask_stats']['mean']:.1f}, White%: {result_info['mask_stats']['pct_white']:.1f}%, Black%: {result_info['mask_stats']['pct_black']:.1f}%")
    
    if debug:
        try:
            import uuid
            # Save final mask
            mask_filename = f"mask_{uuid.uuid4()}.png"
            mask_path = os.path.join(os.path.dirname(output_path), mask_filename)
            mask.save(mask_path)
            result_info["mask_filename"] = mask_filename
            
            # Save probability map if AI was used
            if ai_config and ai_config.get("enabled", False):
                geometry_hint = result_info.get("camera_geometry", "unknown")
                prob_map = FloorSegmenter.instance().get_probability_map(original, geometry_hint=geometry_hint)
                if prob_map:
                    probmap_filename = f"probmap_{uuid.uuid4()}.png"
                    probmap_path = os.path.join(os.path.dirname(output_path), probmap_filename)
                    prob_map.save(probmap_path)
                    result_info["probmap_filename"] = probmap_filename
                    print(f"DEBUG: Saved probability map: {probmap_filename}")
        except Exception as e:
            print(f"Failed to save debug assets: {e}")

    # 3. Create Lighting-Aware Epoxy Texture
    # Parameters
    color_hex = parameters.get("color", "#a1a1aa")
    blend_strength = float(parameters.get("blend_strength", 1.0))
    gamma = float(parameters.get("gamma", 1.0))
    brightness_boost = float(parameters.get("brightness_boost", 1.8))
    finish = parameters.get("finish", "gloss").lower()

    # A. Extract Luminance
    grayscale = original.convert("L")
    
    # Apply Gamma Correction to Luminance
    # Gamma < 1.0 brightens shadows, Gamma > 1.0 darkens shadows/increases contrast
    # We do 1/gamma because PIL behaves that way? No, standard formula is V_out = V_in ^ gamma
    # To brighten midtones (gamma correction), conventionally gamma < 1.0 in some tools, but usually "Gamma Correction"
    # implies V_linear ^ (1/gamma).
    # Let's stick to standard ImageOps or custom LUT if needed.
    # ImageOps.autocontrast might be too much.
    # We'll use a simple point lookup for gamma.
    if gamma != 1.0 and gamma > 0:
        # p_out = 255 * (p_in / 255) ^ (1/gamma) 
        # If gamma is 2.2, we want to darken.
        inv_gamma = 1.0 / gamma
        lut = [int(((i / 255.0) ** inv_gamma) * 255) for i in range(256)]
        grayscale = grayscale.point(lut * 4 if grayscale.mode == 'RGBA' else lut)

    grayscale_rgba = grayscale.convert("RGBA")
    
    # B. Create Color Layer
    color_layer = Image.new("RGBA", (width, height), color_hex)
    
    # C. Multiply Blend
    blended_texture = ImageChops.multiply(color_layer, grayscale_rgba)
    
    # D. Brightness/Boost
    enhancer = ImageEnhance.Brightness(blended_texture)
    epoxy_base = enhancer.enhance(brightness_boost)

    # E. Specular Highlights (Optional)
    # Gated by finish.
    if finish in ["gloss", "satin"]:
        # Extract highlights from original grayscale
        # Threshold: Only take pixels > X
        threshold = 180 if finish == "gloss" else 200
        
        # Create a mask for highlights
        # 1. Take grayscale
        # 2. Point op to zero out below threshold
        def highlight_filter(p):
            return p if p > threshold else 0
            
        highlight_map = grayscale.point(highlight_filter)
        
        # Blur the highlights to make them "bloom"
        blur_radius = 10 if finish == "gloss" else 20
        highlight_overlay = highlight_map.filter(ImageFilter.GaussianBlur(radius=blur_radius)).convert("RGBA")
        
        # Add highlights to epoxy_base using Screen or Add
        # Screen is safer (doesn't clip as harshly)
        epoxy_base = ImageChops.screen(epoxy_base, highlight_overlay)

    # F. Blend Strength (Opacity of the Epoxy Effect)
    # We blend the "Epoxy Result" with the "Original Image" (Unmodified)
    # HOWEVER, we only want to affect the area within the MASK.
    # So we calculate the Full Epoxy Layer, then Composite.
    # BUT, if blend_strength < 1.0, the "Epoxy Layer" itself should be partially transparent 
    # revealing the original floor underneath, BEFORE masking.
    
    if blend_strength < 1.0:
        # Interpolate between Original and EpoxyBase
        # We need original as RGBA
        epoxy_base = Image.blend(original, epoxy_base, blend_strength)

    # 4. Composite
    # Result = Original * (1-Mask) + EpoxyBase * Mask
    result = Image.composite(epoxy_base, original, mask)
    
    # 5. Save
    result.convert("RGB").save(output_path, quality=85)
    
    result_info["success"] = True
    return result_info
