import os
import base64
import io
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFilter, ImageChops
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
                    import numpy as np
                    
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
            print(f"DEBUG: ✓ Using AI mask (coverage {ai_coverage*100:.1f}% >= {MIN_COVERAGE*100:.1f}%)")
        else:
            # USE HEURISTIC MASK - full fallback, no blending
            mask_source = "heuristic"
            result_info["mask_source"] = "heuristic"
            result_info["ai_fallback_reason"] = ai_fallback_reason
            print(f"DEBUG: ✗ AI fallback → heuristic. Reason: {ai_fallback_reason}")
            
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
    # Only feather heuristics. AI and User masks should be sharp.
    should_feather = (result_info.get("camera_geometry") != "top_down") and (result_info.get("mask_source") == "heuristic")
    
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
    
    # B. Create Color/Texture Layer
    base_layer = None
    
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
                
                # Helper: Create Noise Mask for Edge Blending
                def create_edge_mask(mask_w, mask_h, overlap_px):
                    mask = Image.new("L", (mask_w, mask_h), 255)
                    if overlap_px <= 0:
                        return mask
                        
                    draw = ImageDraw.Draw(mask)
                    # Create linear gradient fade at edges
                    fade_len = int(overlap_px * 1.5)
                    if fade_len > 0:
                        # Horizontal fades
                        for x in range(fade_len):
                            alpha = int(255 * (x / fade_len))
                            draw.line((x, 0, x, mask_h), fill=alpha)
                            draw.line((mask_w - 1 - x, 0, mask_w - 1 - x, mask_h), fill=alpha)
                        # Vertical fades
                        v_mask = Image.new("L", (mask_w, mask_h), 255)
                        v_draw = ImageDraw.Draw(v_mask)
                        for y in range(fade_len):
                            alpha = int(255 * (y / fade_len))
                            v_draw.line((0, y, mask_w, y), fill=alpha)
                            v_draw.line((0, mask_h - 1 - y, mask_w, mask_h - 1 - y), fill=alpha)
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
                        
                        # MISSION 21: Randomization
                        # Randomize each tile to break repetition
                        tile = texture.copy()
                        
                        # 1. Random Rotation (only if square or 180)
                        is_square = (t_width == t_height)
                        rot_choices = [0, 180]
                        if is_square:
                            rot_choices.extend([90, 270])
                        
                        rot = random.choice(rot_choices)
                        if rot > 0:
                             tile = tile.rotate(rot)
                        
                        # 2. Random Mirroring
                        if random.random() > 0.5:
                             tile = ImageOps.mirror(tile) # Flip L/R
                        if random.random() > 0.5:
                             tile = ImageOps.flip(tile)   # Flip T/B
                             
                        # 3. Scale Jitter (Zoom in 0-10% to add variation without gaps)
                        if random.random() > 0.3: # Apply to 70% of tiles
                            scale = 1.0 + (random.random() * 0.1)
                            nw = int(t_width * scale)
                            nh = int(t_height * scale)
                            tile = tile.resize((nw, nh), Image.Resampling.BILINEAR)
                            
                            # Center Crop
                            left = (nw - t_width) // 2
                            top = (nh - t_height) // 2
                            tile = tile.crop((left, top, left + t_width, top + t_height))

                        # Generate Edge Mask for Blending
                        tile_mask = create_edge_mask(tile.width, tile.height, overlap_px)
                        
                        # Paste with Mask (Alpha Blending)
                        base_layer.paste(tile, (px, py), mask=tile_mask)

                
                print(f"DEBUG: Applied texture from {texture_path} (Overscan: {overscan}x)")
                
                # Apply Perspective Transform if Eye Level
                if result_info.get("camera_geometry") == "eye_level":
                    print("DEBUG: Applying perspective warp to texture")
                    
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
    
    # Normalize Lighting (Mission 24/25 - Tone Mapping)
    # Adaptive Shadow Lift based on Material Category
    # Flake needs flat/bright lighting to show texture.
    # Metallic needs deep contrasts (liquid look).
    category = parameters.get("style_category", "flake").lower()
    
    lifts = {
        "metallic": 30, # Deep shadows
        "quartz": 70,   # Balanced
        "flake": 80,    # Bright shadows (visibility)
    }
    shadow_lift = lifts.get(category, 64)
    
    scale = (255.0 - shadow_lift) / 255.0
    
    def normalize_lighting(p):
        # Linear compression: lifts black from 0 to shadow_lift
        return int(p * scale + shadow_lift)
    
    lighting_map = lighting_map.point(normalize_lighting)
    
    # Optional: Gamma from params
    if gamma != 1.0 and gamma > 0:
        inv_gamma = 1.0 / gamma 
        lut = [int(((i / 255.0) ** inv_gamma) * 255) for i in range(256)]
        lighting_map = lighting_map.point(lut)

    lighting_rgba = lighting_map.convert("RGBA")
    
    # B. Create Color/Texture Layer (Already done above in base_layer)
    if base_layer is None:
        base_layer = Image.new("RGBA", (width, height), color_hex)
    
    # C. Multiply Blend (Apply Lighting to Texture)
    # Texture * Lighting
    blended_texture = ImageChops.multiply(base_layer, lighting_rgba)
    
    # D. Brightness/Boost
    # Boost contrast/brightness of the final surface
    enhancer = ImageEnhance.Brightness(blended_texture)
    epoxy_base = enhancer.enhance(brightness_boost)

    # E. Specular Highlights (Optional)
    # Gated by finish.
    if finish in ["gloss", "satin"]:
        # Extract highlights from original grayscale (Sharp reflections)
        # We WANT sharp reflections (high freq), so use original grayscale.
        threshold = 180 if finish == "gloss" else 200
        
        def highlight_filter(p):
            return p if p > threshold else 0
            
        highlight_map = grayscale.point(highlight_filter)
        
        blur_radius = 10 if finish == "gloss" else 20
        highlight_overlay = highlight_map.filter(ImageFilter.GaussianBlur(radius=blur_radius)).convert("RGBA")
        
        # Add highlights
        epoxy_base = ImageChops.screen(epoxy_base, highlight_overlay)

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
