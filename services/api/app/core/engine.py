import os
from PIL import Image, ImageEnhance, ImageOps, ImageDraw

def process_image(input_path: str, output_path: str, parameters: dict, debug: bool = False) -> dict:
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
        
    Returns:
        dict: {"success": bool, "mask_filename": str|None, "message": str}
    """
    result_info = {"success": False, "mask_filename": None, "message": ""}

    # 1. Load Image
    try:
        original = Image.open(input_path).convert("RGBA")
    except Exception as e:
        print(f"Error opening image: {e}")
        result_info["message"] = f"Error opening image: {e}"
        return result_info
        
    width, height = original.size
    
    # 2. Generate Mask (Heuristic)
    # Parameters for Mask
    mask_start = float(parameters.get("mask_start", 0.45)) # 0.0 to 1.0 (Top to Bottom)
    mask_end = float(parameters.get("mask_end", 1.0)) # 0.0 to 1.0
    mask_blur = int(parameters.get("mask_blur", 5))
    mask_falloff = float(parameters.get("mask_falloff", 1.0)) # Exponent: 1.0=Linear, >1.0=Convex (Slow start), <1.0=Concave
    
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    
    # Calculate Y coordinates
    start_y = int(height * mask_start)
    end_y = int(height * mask_end)
    
    # Ensure sane definition
    if end_y > start_y:
        for y in range(start_y, height):
            # Calculate normalized position t (0.0 at Start, 1.0 at End)
            if y >= end_y:
                t = 1.0
            else:
                t = (y - start_y) / (end_y - start_y)
            
            # Apply Falloff Curve
            # alpha = 255 * (t ^ power)
            alpha_val = int(255 * (t ** mask_falloff))
            draw.line((0, y, width, y), fill=alpha_val)
            
    # Edge Feathering
    from PIL import ImageFilter, ImageChops
    if width > 0:
        h_mask = Image.new("L", (width, height), 255)
        h_draw = ImageDraw.Draw(h_mask)
        fade_width = int(width * 0.15)
        for x in range(fade_width):
            alpha = int(255 * (x / fade_width))
            h_draw.line((x, 0, x, height), fill=alpha)
            h_draw.line((width - 1 - x, 0, width - 1 - x, height), fill=alpha)
        mask = ImageChops.multiply(mask, h_mask)

    mask = mask.filter(ImageFilter.GaussianBlur(radius=mask_blur))
    
    if debug:
        try:
            import uuid
            mask_filename = f"mask_{uuid.uuid4()}.png"
            mask_path = os.path.join(os.path.dirname(output_path), mask_filename)
            mask.save(mask_path)
            result_info["mask_filename"] = mask_filename
        except Exception as e:
            print(f"Failed to save debug mask: {e}")

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
