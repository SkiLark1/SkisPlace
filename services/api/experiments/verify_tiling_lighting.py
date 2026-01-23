
import os
import shutil
from PIL import Image, ImageDraw, ImageChops

# Mock or import the necessary parts from engine if possible, 
# but since the changes are internal logic changes, we might want to just invoke process_image 
# or copy the logic snippets we want to test if they were standalone functions.
# However, `process_image` is a big function. 
# 
# For unit testing the logic specifically, I will recreate the tiling logic here temporarily 
# to verify "before" and "after" concepts, OR I can modify engine.py to expose the tiling logic?
# 
# Better: I will create a test that uses `process_image` with a custom texture helper that makes it obvious.

def verify_tiling_logic():
    print("--- Verifying Tiling Logic ---")
    
    # 1. Create a logical "Tile" that is solid color but transparent edges? 
    # Actually, the user problem is "double fade". 
    # Let's create a solid red tile.
    tile_size = 100
    tile = Image.new("RGBA", (tile_size, tile_size), (255, 0, 0, 255))
    
    # If we had the "bad" logic: 
    # Paste tile 1. 
    # Paste tile 2 (overlapped). 
    # If both have feathering on all sides, the overlap region is: 
    #   Tile 1 fading out + Tile 2 fading in.
    #   Sum of alphas < 255 usually, creating a dark seam (seeing background).
    
    # We want to maintain 255 alpha in the overlap.
    
    # I'll simulate the "Good" logic here to verify it works as intended concept-wise, 
    # but the real test is running `process_image` after my changes.
    pass

def test_alpha_preservation():
    print("--- Verifying Lighting Alpha Preservation ---")
    # Base: partially transparent red
    base = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    
    # Lighting: Darker (shadow)
    # If we multiply (255, 0, 0, 128) by (128, 128, 128) (50% light):
    # Old logic (multiply RGBA):
    #   R = 255 * 0.5 = 128
    #   A = 128 * 0.5 = 64  <-- THE BUG. Alpha got reduced!
    # 
    # New logic:
    #   Split RGB, A.
    #   A = 128 (preserved).
    #   R = 255 * 0.5 = 128.
    #   Result = (128, 0, 0, 128).
    
    # Let's verify the math.
    lighting = Image.new("RGBA", (100, 100), (128, 128, 128, 255))
    
    # BAD WAY (Simulating current engine behavior)
    bad_result = ImageChops.multiply(base, lighting)
    print(f"Bad Result Alpha: {bad_result.getpixel((50,50))[3]} (Expected < 128)")
    
    # GOOD WAY
    base_rgb = base.convert("RGB") # Discard alpha for math
    alpha = base.split()[3]
    
    lighting_rgb = lighting.convert("RGB")
    
    # Multiply RGB
    blended_rgb = ImageChops.multiply(base_rgb, lighting_rgb)
    
    # Recombine
    good_result = blended_rgb.convert("RGBA")
    good_result.putalpha(alpha)
    
    print(f"Good Result Alpha: {good_result.getpixel((50,50))[3]} (Expected 128)")

if __name__ == "__main__":
    test_alpha_preservation()
