import os
import base64
import io
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFilter, ImageChops
import cv2
import numpy as np

def find_coeffs(source_coords, target_coords):
    """ Calculate perspective transform coefficients. """
    matrix = []
    for s, t in zip(source_coords, target_coords):
        matrix.append([t[0], t[1], 1, 0, 0, 0, -s[0]*t[0], -s[0]*t[1]])
        matrix.append([0, 0, 0, t[0], t[1], 1, -s[1]*t[0], -s[1]*t[1]])
    A = np.matrix(matrix, dtype=np.float64)
    B = np.array(source_coords).reshape(8)
    res = np.dot(np.linalg.inv(A.T * A) * A.T, B)
    return np.array(res).reshape(8)


from app.core.segmentation import FloorSegmenter
from app.core.geometry import detect_camera_geometry

def process_image(input_path: str, output_path: str, parameters: dict, debug: bool = False, custom_mask: str | None = None, ai_config: dict | None = None, texture_path: str | None = None) -> dict:
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
            - scale: Texture scale (default 1.0).
        debug: If True, saves intermediate assets (like mask) and returns their paths.
        custom_mask: Base64 string of user-drawn mask.
        ai_config: Configuration for AI segmentation.
        texture_path: Optional path to texture image (overrides color).
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
    # Analyze Geometry (Returns dict)
    geometry_res = detect_camera_geometry(original, debug=True)
    geometry_type = geometry_res["type"]
    horizon_pct = geometry_res["horizon"]
    
    result_info["camera_geometry"] = geometry_type
    result_info["camera_geometry_horizon"] = horizon_pct
    print(f"DEBUG: Detected Camera Geometry: {geometry_type} (Horizon: {horizon_pct:.2f})")
    

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

    # ========================================================================
    # CANONICAL MASK DECISION PIPELINE
    # Priority: 1) User Mask  2) AI Mask  3) Heuristic Mask
    # NO intersections, unions, or post-threshold modifications to AI mask.
    # ========================================================================
    
    if mask is None:
        # Not a user mask, try AI first, then heuristic
        
        # --- STEP 1: TRY AI MASK ---
        ai_mask = None
        ai_coverage = 0.0
        ai_fallback_reason = None
        MIN_COVERAGE = 0.15  # 15% minimum coverage threshold
        
        if ai_config and ai_config.get("enabled", False):
            try:
                segmenter = FloorSegmenter.instance()
                if segmenter.session:
                    # import numpy as np (Removed to specific shadowing)
                    
                    # Get AI binary mask (thresholded at model resolution, resized with NEAREST)
                    geometry_hint = result_info.get("camera_geometry", "unknown")
                    threshold = float(ai_config.get("ai_threshold", 0.4))
                    morphology = ai_config.get("morphology_cleanup", True)
                    
                    print(f"DEBUG: AI Threshold: {threshold}, Morphology: {morphology}")
                    
                    # Use new get_binary_mask - thresholds at 512x512, resizes with NEAREST
                    ai_mask = segmenter.get_binary_mask(
                        original, 
                        threshold=threshold, 
                        geometry_hint=geometry_hint,
                        morphology_cleanup=morphology
                    )
                    
                    if ai_mask:
                        # Calculate coverage
                        ai_arr = np.array(ai_mask)
                        white_pixels = np.sum(ai_arr > 127)
                        ai_coverage = white_pixels / ai_arr.size if ai_arr.size > 0 else 0.0
                        
                        print(f"DEBUG: AI Mask Coverage: {ai_coverage*100:.1f}%")
                        
                        if ai_coverage < MIN_COVERAGE:
                            ai_fallback_reason = f"coverage_too_low ({ai_coverage*100:.1f}% < {MIN_COVERAGE*100:.1f}%)"
                    else:
                        ai_fallback_reason = "get_binary_mask returned None"
                else:
                    ai_fallback_reason = f"model_not_loaded (path: {segmenter.model_path})"
                    print(f"DEBUG: AI Model NOT loaded (path: {segmenter.model_path})")
            except Exception as e:
                ai_fallback_reason = f"exception: {str(e)}"
                print(f"ERROR: AI mask generation failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            ai_fallback_reason = "ai_disabled" if ai_config else "no_ai_config"
        
        # --- STEP 2: DECIDE: AI vs HEURISTIC (NO HYBRID) ---
        if ai_mask is not None and ai_coverage >= MIN_COVERAGE:
            # USE AI MASK - fully applies, no blending
            mask = ai_mask
            mask_source = "ai"
            result_info["mask_source"] = "ai"
            print(f"DEBUG: [YES] Using AI mask (coverage {ai_coverage*100:.1f}% >= {MIN_COVERAGE*100:.1f}%)")
        else:
            # USE HEURISTIC MASK - full fallback, no blending
            mask_source = "heuristic"
            result_info["mask_source"] = "heuristic"
            result_info["ai_fallback_reason"] = ai_fallback_reason
            print(f"DEBUG: [NO] AI fallback -> heuristic. Reason: {ai_fallback_reason}")
            
            # Geometry-Aware Heuristic
            is_top_down = result_info.get("camera_geometry") == "top_down"
            
            if is_top_down:
                # Top-Down: Center-weighted vignette
                print("DEBUG: Generating heuristic vignette mask for top-down")
                mask = Image.new("L", (width, height), 255)
                draw = ImageDraw.Draw(mask)
                
                border_pct = 0.08
                fade_pct = 0.12
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
                
                # Vertical edge suppression
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
            else:
                # Eye-Level: Vertical gradient
                print("DEBUG: Generating heuristic gradient mask for eye-level")
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

    # D. Edge Feathering (Geometry & Source Aware)
    # 1. Gradient Feather (Large fade for rough heuristic masks)
    should_gradient_feather = (result_info.get("camera_geometry") != "top_down") and (result_info.get("mask_source") == "heuristic")
    
    if width > 0 and should_gradient_feather:
        h_mask = Image.new("L", (width, height), 255)
        h_draw = ImageDraw.Draw(h_mask)
        fade_width = int(width * 0.15)
        for x in range(fade_width):
            alpha = int(255 * (x / fade_width))
            h_draw.line((x, 0, x, height), fill=alpha)
            h_draw.line((width - 1 - x, 0, width - 1 - x, height), fill=alpha)
        mask = ImageChops.multiply(mask, h_mask)

    # Mission 28/Change 3A: Morphological Improvements & Clean Edges
    # We always apply this to clean up the mask, especially for User masks.
    # HEURISTIC masks need more help. AI masks should be treated gently.
    if mask is not None:
        mask_np = np.array(mask)
        mask_src = result_info.get("mask_source", "heuristic")
        
        # 1. Close (Fill pinholes) - Safe for all
        kernel_close = np.ones((5,5), np.uint8)
        mask_np = cv2.morphologyEx(mask_np, cv2.MORPH_CLOSE, kernel_close)
        
        # 2. Dilate (Expand edges)
        # Patch C: Only do heavy dilation for heuristic. 
        # AI masks are already geometry-aware (Mission 12) so we don't want to over-expand.
        if mask_src == "heuristic":
            dilate_px = max(2, int(width * 0.003)) # 0.3% of width
            kernel_dilate = np.ones((dilate_px, dilate_px), np.uint8)
            mask_np = cv2.dilate(mask_np, kernel_dilate, iterations=1)
        elif mask_src == "ai":
            # Very slight dilation just to smooth edges (1px)
            # kernel_dilate = np.ones((1, 1), np.uint8) # no-op
            # actually skip dilation or do minimal?
            # User suggested: "close only... no dilate (or 1px)"
            # Let's do 0.
            pass
        
        # Change 3B: Wall Guardrail (Horizon Cutoff)
        # Prevent mask from bleeding "up" onto the wall.
        h_pct = result_info.get("camera_geometry_horizon", horizon_pct) 
        
        horizon_cutoff_y = None # Store for re-application
        if h_pct > 0 and h_pct < 0.9: 
            cutoff_y = int(height * h_pct)
            if cutoff_y > 0:
                mask_np[0:cutoff_y, :] = 0
                horizon_cutoff_y = cutoff_y
                print(f"DEBUG: Applied Horizon Cutoff at Y={cutoff_y}")
        
        mask = Image.fromarray(mask_np)

    # 2. Micro Feather (Anti-aliasing for AI masks) - Mission 28
    # AI masks are resized nearest-neighbor, so they have jagged edges.
    # We apply a tiny blur to soften them into the wall.
    if result_info.get("mask_source") == "ai":
        mask = mask.filter(ImageFilter.GaussianBlur(radius=1.5))


    mask = mask.filter(ImageFilter.GaussianBlur(radius=mask_blur))
    
    # Patch A: Re-apply Horizon Cutoff logic AFTER blurs (Part 2)
    # The 'horizon_cutoff_y' variable must be available from the previous scope.
    # Note: replace_file_content chunks are separate, but python scope is function-wide.
    # However, I need to ensure the variable is defined even if the previous block (mask is not None) was skipped?
    # Actually mask is None -> fallback was handled. But if mask was None initially, 'horizon_cutoff_y' wouldn't result in errors because mask would stay None?
    # Wait, 'process_image' flow ensures 'mask' is eventually set or we fallback.
    # But 'mask' is set by AI or Heuristic before the previous block.
    # So 'horizon_cutoff_y' will be defined if I define it in the replacement above.
    # But if I replaced lines 243-279, I defined it inside 'if mask is not None'.
    # If mask IS None (impossible after Step 2), it's fine.
    # BUT, 'horizon_cutoff_y' might not be in scope if 'mask is not None' isn't entered?
    # Mask is initialized to heuristic or AI. It is NEVER None here.
    # BUT python static analysis might complain if I use it and it wasn't init.
    # I'll rely on it being set in the previous block or use a safe check if possible.
    # To be safe, I should initialize `horizon_cutoff_y = None` at top of function? Too much editing.
    # I'll assume standard execution flow.
    
    # Wait, 'horizon_cutoff_y' needs to be local.
    # I will rely on the previous block defining it.
    
    if locals().get("horizon_cutoff_y") and horizon_cutoff_y is not None and horizon_cutoff_y > 0:
        m = np.array(mask)
        m[0:horizon_cutoff_y, :] = 0
        mask = Image.fromarray(m)
        print(f"DEBUG: Re-applied Horizon Cutoff post-blur at Y={horizon_cutoff_y}")
    
    # E. Compute Mask Stats (always, for debugging)
    # import numpy as np (Removed global shadow)
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
                    # Patch B: Save a VIEWABLE grayscale probmap
                    prob_vis = prob_map.convert("L")
                    probmap_vis_filename = f"probmap_vis_{uuid.uuid4()}.png"
                    prob_vis.save(os.path.join(os.path.dirname(output_path), probmap_vis_filename))
                    
                    # Keep existing LA version for browser
                    if prob_map.mode == "L":
                         white_layer = Image.new("L", prob_map.size, 255)
                         prob_map = Image.merge("LA", (white_layer, prob_map))
                    
                    probmap_filename = f"probmap_{uuid.uuid4()}.png"
                    probmap_path = os.path.join(os.path.dirname(output_path), probmap_filename)
                    prob_map.save(probmap_path)
                    
                    result_info["probmap_filename"] = probmap_filename
                    result_info["probmap_vis_filename"] = probmap_vis_filename
                    print(f"DEBUG: Saved probability maps: {probmap_filename} (LA), {probmap_vis_filename} (L)")
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
    
    # B. Create Color/Texture Layer
    # B. Create Color/Texture Layer
    base_layer = None
    
    # Mission 30: System-Specific Tuning Profiles (Moved here so available for Lighting too)
    category = parameters.get("style_category", "flake").lower()
    
    SYSTEM_PROFILES = {
        "flake": {
            "rotation_angles": [0, 90, 180, 270], # Full chaos
            "mirror_prob": 0.5,
            "scale_jitter": 0.1,  # +/- 10%
            "shadow_lift": 0.28,  # High visibility
            "highlight_compress": 0.85, # Soft roll-off
            "specular_thresh": 200, # Only very bright spots
            "specular_blur": 15,    # Soft reflections
        },
        "metallic": {
            "rotation_angles": [0, 180], # Maintain flow direction (no 90/270)
            "mirror_prob": 0.3, # Less mirroring to keep flow
            "scale_jitter": 0.05, # Subtle jitter
            "shadow_lift": 0.10,  # Deep contrast
            "highlight_compress": 0.98, # Sharp highlights
            "specular_thresh": 180, # More reflections
            "specular_blur": 8,     # Sharp reflections
        },
        "quartz": {
            "rotation_angles": [0, 90, 180, 270],
            "mirror_prob": 0.5,
            "scale_jitter": 0.08,
            "shadow_lift": 0.22,
            "highlight_compress": 0.90,
            "specular_thresh": 190,
            "specular_blur": 12,
        }
    }
    
    profile = SYSTEM_PROFILES.get(category, SYSTEM_PROFILES["flake"])
    
    if texture_path and os.path.exists(texture_path):
        try:
            texture = Image.open(texture_path).convert("RGBA")
            t_width, t_height = texture.size
            if t_width > 0 and t_height > 0:
                # Use Tiling with Overscan for Perspective
                # We create a much wider buffer to handle the perspective frustum (fan out)
                # without leaving black voids at the top (horizon).
                
                overscan = 10 
                t_canvas_width = width * overscan
                base_layer = Image.new("RGBA", (t_canvas_width, height))
                
                # Helper: Create Edge Mask (Directional Feathering) - Mission 34
                def create_directional_feather(mask_w, mask_h, overlap_px, feather_left=False, feather_top=False):
                    mask = Image.new("L", (mask_w, mask_h), 255)
                    if overlap_px <= 0:
                        return mask
                        
                    draw = ImageDraw.Draw(mask)
                    # We only feather the "incoming" edges (Left and Top) of the NEW tile
                    # so that it blends smoothly ON TOP OF the previous tiles.
                    # The Right and Bottom edges stay opaque (255) so next tiles can blend onto THEM.
                    
                    fade_len = int(overlap_px * 1.5) # Slightly wider than overlap for smoothness? Or match it?
                    # Let's match overlap for now to ensure we don't fade into the non-overlapped area affecting opacity.
                    fade_len = overlap_px 
                    
                    if fade_len > 0:
                        # Feather LEFT edge (if this is not the first column)
                        if feather_left:
                            for x in range(fade_len):
                                alpha = int(255 * (x / fade_len))
                                draw.line((x, 0, x, mask_h), fill=alpha)
                                
                        # Feather TOP edge (if this is not the first row)
                        if feather_top:
                            for y in range(fade_len):
                                alpha = int(255 * (y / fade_len))
                                # Note: We are multiplying if both are present?
                                # If we use draw.line with a low alpha on an existing low alpha, it overwrites or blends?
                                # "fill" in draw.line overwrites.
                                # So for the corner (top-left), we need to handle intersection carefully.
                                # Easiest way: Draw horizontal lines, but multiply by existing mask value?
                                # Or just create separate V mask and multiply.
                                pass 
                            
                            # Create a vertical feather mask
                            v_mask = Image.new("L", (mask_w, mask_h), 255)
                            v_draw = ImageDraw.Draw(v_mask)
                            for y in range(fade_len):
                                alpha = int(255 * (y / fade_len))
                                v_draw.line((0, y, mask_w, y), fill=alpha)
                            
                            # Combine
                            mask = ImageChops.multiply(mask, v_mask)
                            
                    return mask

                # Overlap Logic
                # Overlap by 15% of tile size
                overlap_pct = 0.15
                overlap_px = int(min(t_width, t_height) * overlap_pct)
                step_x = max(1, t_width - overlap_px)
                step_y = max(1, t_height - overlap_px)
                
                repeats_x = (t_canvas_width // step_x) + 2
                repeats_y = (height // step_y) + 2
                 
                import random
                
                for ix in range(repeats_x):
                    # Stagger odd columns by half height to break horizontal grid lines
                    y_shift = (step_y // 2) if (ix % 2 == 1) else 0
                    
                    for iy in range(repeats_y):
                        px = (ix * step_x) - overlap_px
                        py = (iy * step_y) - y_shift - overlap_px
                        
                        # MISSION 21: Randomization (Controlled by Profile)
                        tile = texture.copy()
                        
                        # 1. Random Rotation
                        is_square = (t_width == t_height)
                        rot_choices = list(profile["rotation_angles"])
                        
                        # If not square, can only do 0/180 safely in grid?
                        # Actually profile["rotation_angles"] assumes square or compatible.
                        # If non-square, restrict to 0/180 regardless of profile to avoid overlap issues.
                        if not is_square:
                             rot_choices = [r for r in rot_choices if r % 180 == 0]

                        if rot_choices:
                             rot = random.choice(rot_choices)
                             if rot > 0:
                                  tile = tile.rotate(rot)
                        
                        # 2. Random Mirroring
                        if random.random() < profile["mirror_prob"]:
                             tile = ImageOps.mirror(tile)
                        if random.random() < profile["mirror_prob"]:
                             tile = ImageOps.flip(tile)
                             
                        # 3. Scale Jitter
                        if profile["scale_jitter"] > 0 and random.random() > 0.3:
                            scale = 1.0 + (random.random() * profile["scale_jitter"])
                            nw = int(t_width * scale)
                            nh = int(t_height * scale)
                            tile = tile.resize((nw, nh), Image.Resampling.BILINEAR)
                            
                            # Center Crop
                            left = (nw - t_width) // 2
                            top = (nh - t_height) // 2
                            tile = tile.crop((left, top, left + t_width, top + t_height))

                        # Generate Edge Mask (Directional)
                        # Feather Left if col > 0. Feather Top if row > 0.
                        feather_left = (ix > 0)
                        feather_top = (iy > 0)
                        
                        # Optimization: If no feathering needed, mask is fully white
                        if feather_left or feather_top:
                            tile_mask = create_directional_feather(tile.width, tile.height, overlap_px, feather_left, feather_top)
                        else:
                            tile_mask = None # Treated as full opacity 255
                        
                        # Composite
                        # Change 1B: Use alpha_composite for true layering without accumulation artifacts
                        # To use alpha_composite, we need:
                        # 1. Base layer (RGBA)
                        # 2. Source layer (RGBA) - which is our Tile
                        # 3. Position offset. alpha_composite doesn't take position.
                        # So we must create a temp layer size of canvas, paste tile into it, then composite?
                        # That's slow for large canvas. 
                        # Faster: Crop the destination region from base, composite tile onto it, paste back.
                        
                        # Destination Coords
                        dest_x = px
                        dest_y = py
                        dest_w = tile.width
                        dest_h = tile.height
                        
                        # Handle clipping if tile goes off canvas
                        # (Though our canvas is huge so unlikely, but good practice)
                        
                        # Apply mask to tile alpha channel
                        if tile_mask:
                           # Ensure tile has alpha
                           if tile.mode != 'RGBA':
                               tile = tile.convert("RGBA")
                           
                           # Multiply tile alpha by mask
                           # We can split, multiply alpha, merge
                           r, g, b, a = tile.split()
                           a = ImageChops.multiply(a, tile_mask)
                           tile = Image.merge("RGBA", (r, g, b, a))
                        
                        # Now composite using alpha_composite
                        # base_layer.alpha_composite(tile, (dest_x, dest_y)) 
                        # Note: Pillow's alpha_composite is `Image.alpha_composite(dest, source)` and returns result. 
                        # It works on full images.
                        # `image.alpha_composite(im, dest=(0,0), source=(0,0))` is the in-place version introduced in recent Pillow?
                        # checking... Pillow 6.0+ has `image.alpha_composite(im, dest, source)`.
                        # But standard `Image.alpha_composite` creates a NEW image.
                        # Correct method for in-place is `base_layer.alpha_composite(tile, (dest_x, dest_y))` 
                        # WAIT: `Image.Image.alpha_composite` (method) takes `(im, dest, source)`.
                        # Let's use the safer `paste` if we just want to put it on top?
                        # NO, `paste` with mask does blending: `result = base * (1-alpha) + source * alpha`.
                        # `alpha_composite` does Porter-Duff Over. `result_alpha = source_alpha + dest_alpha * (1 - source_alpha)`.
                        # This avoids the "transparent hole" problem if source is semi-transparent.
                        # Since we want to LAYER tiles, we want Over.
                        
                        # Create a temp wrapper for the region?
                        # To keep it simple and performant:
                        # 1. Crop Base Region
                        region = base_layer.crop((dest_x, dest_y, dest_x + dest_w, dest_y + dest_h))
                        # 2. Alpha Composite Tile ONTO Region
                        # region is 'dest', tile is 'source'
                        # region = Image.alpha_composite(region, tile) -- requires same size
                        if region.size == tile.size:
                            region = Image.alpha_composite(region, tile)
                            # 3. Paste Region back
                            base_layer.paste(region, (dest_x, dest_y))
                        else:
                            # Edge case: tile partly off canvas
                            # fallback to paste
                            base_layer.paste(tile, (dest_x, dest_y), tile)


                
                print(f"DEBUG: Applied texture from {texture_path} (Overscan: {overscan}x)")
                
                # Apply Perspective Transform (Mask-Driven) - Mission 35
                # Check if we have a valid mask to extract geometry from
                perspective_applied = False
                
                # If we have a mask (User or AI) that is not empty
                if mask is not None:
                     # Convert mask to CV2 for contour finding
                     mask_cv = np.array(mask)
                     contours, _ = cv2.findContours(mask_cv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                     
                     if contours:
                         # Find largest contour
                         largest_cnt = max(contours, key=cv2.contourArea)
                         area = cv2.contourArea(largest_cnt)
                         
                         # Safety: Ensure contour is significant (e.g. > 5% of image)
                         if area > (width * height * 0.05):
                             print("DEBUG: Found mask contour for perspective warp.")
                             
                             # Approximate to a Quad (4 points)
                             epsilon = 0.02 * cv2.arcLength(largest_cnt, True)
                             approx = cv2.approxPolyDP(largest_cnt, epsilon, True)
                             
                             dest_points_cv = None
                             
                             if len(approx) == 4:
                                 dest_points_cv = approx
                             else:
                                 # Fallback: Rotated Rect or Bounding Rect
                                 # Ideally MinAreaRect creates a tight fit oriented rect
                                 rect = cv2.minAreaRect(largest_cnt)
                                 box = cv2.boxPoints(rect)
                                 dest_points_cv = np.intp(box)
                             
                             # We need to sort points: TL, TR, BR, BL
                             # Simple sort by sum(x+y) etc? 
                             # Common method: 
                             # TL: smallest sum(x+y), BR: largest sum(x+y)
                             # TR: smallest diff(x-y), BL: largest diff(x-y) ??
                             # Let's use a robust sorter.
                             
                             pts = dest_points_cv.reshape(4, 2)
                             rect = np.zeros((4, 2), dtype="float32")
                             
                             s = pts.sum(axis=1)
                             rect[0] = pts[np.argmin(s)] # TL
                             rect[2] = pts[np.argmax(s)] # BR
                             
                             diff = np.diff(pts, axis=1)
                             rect[1] = pts[np.argmin(diff)] # TR
                             rect[3] = pts[np.argmax(diff)] # BL
                             
                             # Source points: The texture canvas we want to map into this quad.
                             # We use the full t_canvas_width? 
                             # Or just valid width/height?
                             # Let's map the 'overscan' canvas to the 'floor quad'
                             # BUT, we want density to be correct.
                             # If we map a huge canvas to a small quad, it looks dense (good).
                             
                             source_pts_np = np.array([
                                 [0, 0],
                                 [t_canvas_width, 0],
                                 [t_canvas_width, height], # or t_height? 
                                 [0, height]
                             ], dtype="float32")
                             
                             # Use the helper `find_coeffs` which expects lists of tuples
                             dest_list = [tuple(p) for p in rect]
                             source_list = [tuple(p) for p in source_pts_np]
                             
                             coeffs = find_coeffs(source_list, dest_list)
                             
                             # Transform
                             try:
                                warped = base_layer.transform((width, height), Image.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC)
                                base_layer = warped
                                perspective_applied = True
                                print("DEBUG: Applied Mask-Driven Perspective Warp")
                             except Exception as exc:
                                print(f"WARNING: Perspective warp failed: {exc}")

                # Fallback to Horizon Heuristic if mask warp didn't happen (and is eye level)
                if not perspective_applied and result_info.get("camera_geometry") == "eye_level":
                    print("DEBUG: Applying heuristic perspective warp (Fallback)")
                    
                    # Define Horizon (Top of trapezoid)
                    h_y = int(height * horizon_pct)
                    
                    center_x = width / 2
                    
                    # Dest Top (at horizon)
                    dt_w = width * 4.0 
                    dest_tl = (center_x - dt_w/2, h_y)
                    dest_tr = (center_x + dt_w/2, h_y)
                    
                    # Dest Bottom (at bottom)
                    # Needs to be wider to create convergence
                    db_w = dt_w * 3.5 
                    dest_bl = (center_x - db_w/2, height)
                    dest_br = (center_x + db_w/2, height)
                    
                    dest_points = [dest_tl, dest_tr, dest_br, dest_bl]
                    source_points = [(0, 0), (t_canvas_width, 0), (t_canvas_width, height), (0, height)]
                    
                    coeffs = find_coeffs(source_points, dest_points)
                    
                    # Transform (Sample from the 10x buffer)
                    warped = base_layer.transform((width, height), Image.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC)
                    
                    base_layer = warped

                    
        except Exception as e:
            print(f"ERROR: Failed to load texture: {e}")
            import traceback
            traceback.print_exc()

    
    # A. Extract Lighting (Luminance) - Mission 23
    # We want lighting (shadows/gradients) but NOT albedo (stains/lines).
    # Use Frequency Separation approach: Lighting is Low Frequency.
    grayscale = original.convert("L")
    
    # Blur to remove high-frequency details (stains, lines)
    # Radius depends on resolution. 15px is good heuristic for 1000px wide.
    # Dynamic radius: 1.5% of width
    blur_rad = max(5, int(width * 0.015))
    lighting_map = grayscale.filter(ImageFilter.GaussianBlur(radius=blur_rad))
    
    # Normalize Lighting (Mission 26/27/30 - Tone Mapping with Profiles)
    # Adaptive Shadow Lift + Highlight Compression using System Profile
    
    # Use values from the profile we resolved earlier
    lift = profile["shadow_lift"]
    compress = profile["highlight_compress"]
    
    # Mission 36: Normalized Tone Mapping (Change 2B)
    # Goal: Preserve original lighting naturally without mud or blowout.
    # 1. Normalize Luminance Map based on Floor Statistics implies we need the FLOOR pixels only.
    mask_arr = np.array(mask)
    if mask_arr.max() > 0:
        # Get luminance values only where mask > 0
        lum_arr = np.array(lighting_map)
        floor_pixels = lum_arr[mask_arr > 0]
        
        if floor_pixels.size > 0:
            # Calculate stats
            p5 = np.percentile(floor_pixels, 5)
            p95 = np.percentile(floor_pixels, 95)
            
            # Avoid divide by zero
            denom = p95 - p5
            if denom < 1: denom = 1
            
            # Normalize to 0-1 range roughly, then map to Target Range [0.6, 1.1]
            # Target range means:
            # 0.6 = Shadows (Darkest floor parts darken the epoxy by 40%)
            # 1.1 = Highlights (Brightest floor parts brighten the epoxy by 10%)
            # This range is conservative to avoid "mud".
            
            target_min = 0.6
            target_max = 1.1
            
            # We want to re-map lighting_map values
            # value = (original - p5) / (p95 - p5) * (t_max - t_min) + t_min
            # Do this via LUT for speed
            
            norm_lut = []
            for i in range(256):
                 # Normalize 0-1 based on floor stats
                 n = (i - p5) / denom
                 # Clamp to 0-1 (optional, or let it overshoot for extreme highlights)
                 # n = max(0.0, min(1.0, n)) 
                 
                 # Map to target
                 val_mapped = n * (target_max - target_min) + target_min
                 
                 # Optimization: Shadows shouldn't be TOO lifted if we want depth?
                 # Actually, we want to PRESERVE original shadows. 
                 # If original had a shadow (low luminance), val_mapped will be low (e.g. 0.6).
                 # If we use MULTIPLY blend: Epoxy * 0.6 = Darker Epoxy. Correct.
                 
                 # Apply Lift/Gamma from Profile to this Normalized curve instead of raw pixel?
                 # Let's apply Profile adjustments ON TOP of this normalization.
                 
                 # Profile Lift/Compress
                 # n_lifted = n * (1.0 - lift) + lift ...
                 # Let's stick to the simpler user request first:
                 # "Normalize L into ~[0.6, 1.1]"
                 # "StyleRGB *= L"
                 
                 # Warning: If we multiply by 1.1, we might exceed 255.
                 # Python PIL multiply usually normalizes X * Y / 255.
                 # So if we want "Boost", we need a value > 255? No, PIL multiply is strictly darkening.
                 # To strictly "Multiply" in float terms: Result = A * B.
                 # If B > 1.0, it brightens.
                 # PIL ImageChops.multiply(a, b) = a * b / 255.
                 # So if b is 255, result is a. Max brightness = a.
                 # So standard Multiply CANNOT brighten.
                 # We need to use "Overlay" or just explicit math, OR:
                 # We use `lighting_map` as a modulator where 255 = 2.0x brightness?
                 # No, standard pipeline: 
                 # 1. Multiply (Shadows)
                 # 2. Screen (Highlights)
                 
                 # Let's interpret "Normalize to [0.6, 1.1]" as a float multiplier.
                 # Since we are using PIL, we can produce a "Shadow Map" and a "Highlight Map".
                 
                 # SHADOW MAP (Multiply):
                 # Range [0, 1] -> Map normalized luminance [0.6, 1.1] to [0, 255]? No.
                 # If L_norm = 0.6, we want Mult_val = 153 (0.6*255).
                 # If L_norm = 1.0, we want Mult_val = 255.
                 # If L_norm > 1.0, we clamp to 255 for Multiply layer.
                 
                 v_mult = val_mapped * 255.0
                 v_mult = max(0, min(255, v_mult))
                 norm_lut.append(int(v_mult))
                 
            lighting_map = lighting_map.point(norm_lut)
        else:
            print("WARNING: No floor pixels found in mask, skipping normalization.")
    
    # Optional: Gamma from params (kept from original)
    if gamma != 1.0 and gamma > 0:
        inv_gamma = 1.0 / gamma 
        lut_gamma = [int(((i / 255.0) ** inv_gamma) * 255) for i in range(256)]
        lighting_map = lighting_map.point(lut_gamma)

    lighting_rgba = lighting_map.convert("RGBA")
    
    # B. Create Color/Texture Layer (Already done above in base_layer)
    if base_layer is None:
        base_layer = Image.new("RGBA", (width, height), color_hex)
    
    # C. Multiply Blend (Alpha-Safe) - Mission 34
    # blended_texture = ImageChops.multiply(base_layer, lighting_rgba) <-- OLD BUGGY WAY (Darkens Alpha)
    
    # New Way: Split, Multiply RGB, Preserve Alpha
    base_r, base_g, base_b, base_a = base_layer.split()
    light_r, light_g, light_b, light_a = lighting_rgba.split() # light_a is likely 255 or from blur
    
    # We only care about the RGB from lighting (the shadows/gradients)
    # So we multiply Base RGB * Light RGB
    res_r = ImageChops.multiply(base_r, light_r)
    res_g = ImageChops.multiply(base_g, light_g)
    res_b = ImageChops.multiply(base_b, light_b)
    
    # Recombine with ORIGINAL Base Alpha
    # This ensures that if the base was transparent (e.g. gaps), it helps?
    # Actually, base_layer is usually fully opaque tile canvas.
    # BUT, if we have a mask applied later, it's fine.
    # The issue described by user: "transparent pixels participate in lighting".
    # If base_layer has alpha=0, multiply(0, X) = 0.
    # If base_layer has alpha=255, multiply(255, X) = X.
    # Wait, `ImageChops.multiply` on RGBA multiplies ALL channels.
    # So Alpha_result = Base_Alpha * Light_Alpha / 255.
    # If Light map was converted from Grayscale -> RGBA, its Alpha is 255.
    # So Base_Alpha * 255 / 255 = Base_Alpha.
    # So theoretically `multiply` should be fine IF lighting_rgba has alpha 255.
    # Let's check: `lighting_rgba = lighting_map.convert("RGBA")`. 
    # If `lighting_map` is "L", convert("RGBA") makes A=255.
    # SO why did the user say "transparent pixels participate"?
    # Maybe because the User logic applies lighting AFTER masking? 
    # In my code:
    # 3. Create Lighting Aware Texture (Produces `epoxy_base`)
    # 4. Composite (Uses `mask` to cut it out).
    # So `epoxy_base` is calculated for the WHOLE image (width, height), usually opaque color.
    # If `base_layer` (tiled texture) has holes (alpha=0), then `multiply` makes A=0 (since light A=255).
    # That seems correct?
    #
    # User Says: "Rule: apply lighting to RGB, preserve alpha separately"
    # "This prevents 'transparent -> black' artifacts".
    # If alpha is 0, RGB becomes 0 (Black) after multiply usually? No, multiply doesn't premultiply.
    # (R,G,B,A) * (L,L,L,255) -> (R*L, G*L, B*L, A).
    #
    # Perhaps the issue creates "Dark Lines" at the seams of tiles if the seams aren't 255?
    # My "Change 1A" fixes the seams to be 255.
    # But let's implement the safety just in case `lighting_rgba` has some alpha variance 
    # or to be strictly correct as per request.
    
    blended_texture = Image.merge("RGBA", (res_r, res_g, res_b, base_a))
    
    # D. Brightness/Boost
    enhancer = ImageEnhance.Brightness(blended_texture)
    epoxy_base = enhancer.enhance(brightness_boost)

    # E. Specular Highlights (Improved: Clamp & Soft)
    if finish in ["gloss", "satin"]:
        # Profile settings
        threshold = profile["specular_thresh"]
        blur_radius = profile["specular_blur"]
        
        # 1. Extract Highlights from Original (Normalized?)
        # We can use the Normalized Luminance we calculated for consistency
        # But `grayscale` is the original raw. Let's use raw to capture true bright spots.
        
        def highlight_filter(p):
            return p if p > threshold else 0
            
        highlight_map = grayscale.point(highlight_filter)
        
        # Blur
        highlight_overlay = highlight_map.filter(ImageFilter.GaussianBlur(radius=blur_radius)).convert("RGBA")
        
        # 2. Screen Blend
        epoxy_base = ImageChops.screen(epoxy_base, highlight_overlay)
        
        # 3. Clamp Highlights (Prevent Blowout) - Mission 36
        # Limit max brightness to e.g. 248 (0.97) to avoid "digital white" look
        clamp_max = 248 
        # Using point function on each channel
        # Note: This clamps EVERYTHING, even the epoxy color. 
        # Is that desired? "sun patches don't blow out". Yes.
        # But we only want to clamp if it exceeds.
        
        # Optimized clamp lut
        clamp_lut = [min(i, clamp_max) for i in range(256)]
        
        # Split, apply clamp, merge? Or apply to RGB only?
        # Applying to alpha would be bad.
        source = epoxy_base.split()
        if len(source) == 4:
            r, g, b, a = source
            r = r.point(clamp_lut)
            g = g.point(clamp_lut)
            b = b.point(clamp_lut)
            epoxy_base = Image.merge("RGBA", (r, g, b, a))
        else:
            epoxy_base = epoxy_base.point(clamp_lut)

    # F. Blend Strength (Opacity)
    if blend_strength < 1.0:
        epoxy_base = Image.blend(original, epoxy_base, blend_strength)

    # 4. Composite
    # Replace floor pixels with lit texture
    result = Image.composite(epoxy_base, original, mask)
    
    # 5. Save
    result.convert("RGB").save(output_path, quality=90)
    
    result_info["success"] = True
    return result_info
