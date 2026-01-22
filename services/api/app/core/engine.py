import os
from PIL import Image, ImageEnhance, ImageOps, ImageDraw

def process_image(input_path: str, output_path: str, parameters: dict):
    """
    Process the image to apply a simulated epoxy finish.
    
    Args:
        input_path: Path to source image.
        output_path: Path to save result.
        parameters: Style parameters (e.g., {'color': '#C0C0C0', 'finish': 'gloss'}).
    """
    # 1. Load Image
    try:
        original = Image.open(input_path).convert("RGBA")
    except Exception as e:
        print(f"Error opening image: {e}")
        return False
        
    width, height = original.size
    
    # 2. Generate Mask (Heuristic)
    # Strategy: 
    # - Floors are usually at the bottom.
    # - Create a vertical gradient mask (transparent at top, opaque at bottom).
    
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    
    # Linear Gradient from 50% height (0) to 100% height (255)
    start_y = int(height * 0.45)
    for y in range(start_y, height):
        # linear ramp 0 -> 255
        alpha = int(255 * ((y - start_y) / (height - start_y)))
        draw.line((0, y, width, y), fill=alpha)
        
    # 2.5. Edge Feathering (Phase 3.3c)
    from PIL import ImageFilter, ImageChops
    
    # A. Horizontal Vignette (Fade out left/right edges)
    # This prevents the "cutout" look near walls.
    if width > 0:
        h_mask = Image.new("L", (width, height), 255)
        h_draw = ImageDraw.Draw(h_mask)
        fade_width = int(width * 0.15) # 15% fade on each side
        for x in range(fade_width):
            alpha = int(255 * (x / fade_width))
            # Left side (0 -> 255)
            h_draw.line((x, 0, x, height), fill=alpha)
            # Right side (255 -> 0)
            h_draw.line((width - 1 - x, 0, width - 1 - x, height), fill=alpha)
        
        # Multiply vertical mask by horizontal mask
        mask = ImageChops.multiply(mask, h_mask)

    # B. Gaussian Blur to soften all edges
    mask = mask.filter(ImageFilter.GaussianBlur(radius=5))
        
    # 3. Create Lighting-Aware Epoxy Texture
    color_hex = parameters.get("color", "#a1a1aa") # Default Metallic Grey
    
    # A. Extract Luminance (Grayscale)
    # This captures the shadows and lighting of the original floor
    grayscale = original.convert("L").convert("RGBA")
    
    # B. Create Color Layer
    color_layer = Image.new("RGBA", (width, height), color_hex)
    
    # C. Multiply Blend: Color * Luminance
    # This "dyes" the floor with the epoxy color while keeping shadows dark.
    # We must use ImageChops for blending.
    from PIL import ImageChops
    # Multiply requires RGB or RGBA. Both are RGBA here.
    blended_texture = ImageChops.multiply(color_layer, grayscale)
    
    # D. Gamma/Brightness Correction
    # Multiply is subtractive (darkens). Epoxy is glossy/bright.
    # We boost brightness to simulate the reflective nature and counter the multiply darkening.
    enhancer = ImageEnhance.Brightness(blended_texture)
    epoxy_finish = enhancer.enhance(1.8) # 1.8x brightness (tuned for plausible glossy look)

    # 4. Composite
    # Blend the new "Epoxy Finish" onto the Original using the Floor Mask
    # Result = Original (where mask=0) + EpoxyFinish (where mask=255)
    result = Image.composite(epoxy_finish, original, mask)
    
    # 5. Save
    # Convert back to RGB to save as JPG
    result.convert("RGB").save(output_path, quality=85)
    return True
