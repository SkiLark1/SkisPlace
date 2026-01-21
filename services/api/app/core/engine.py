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
        
    # 3. Create Overlay Layer
    color_hex = parameters.get("color", "#CCCCCC")
    overlay = Image.new("RGBA", (width, height), color_hex)
    
    # 4. Composite
    # We want to blend the overlay onto the original ONLY where the mask is white.
    # And we want to preserve the original texture (luminance).
    
    # Simple Alpha Composite with Mask:
    # Result = Original * (1-Mask) + (Original Blend Overlay) * Mask
    
    # Let's try "Overlay" blend mode logic manually or just alpha blend
    # Alpha blend is easiest for V1.
    
    # Create a composite image where we apply the color
    # To keep texture, we can use the original image's "L" channel as alpha for the overlay?
    # Or just simple alpha blending with the gradient mask.
    
    # Let's give the overlay itself some transparency so it looks like a "tint"
    overlay.putalpha(150) # Semi-transparent color
    
    # Create a composite of Original + Overlay
    tinted = Image.alpha_composite(original, overlay)
    
    # Now merge Tinted and Original using the Gradient Mask
    # result = original where mask is black, tinted where mask is white
    result = Image.composite(tinted, original, mask)
    
    # 5. Save
    # Convert back to RGB to save as JPG
    result.convert("RGB").save(output_path, quality=85)
    return True
