import os
import shutil
from PIL import Image, ImageDraw
from app.core.engine import process_image

def test_epoxy_polish():
    print("Testing Epoxy Polish Parameters...")
    
    # 1. Create Synthetic Image
    # Gradient from black to white to test gamma and highlights
    width, height = 200, 200
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw vertical gradient
    for y in range(height):
        val = int(255 * (y / height))
        draw.line((0, y, width, y), fill=(val, val, val))
        
    # Add a bright spot for specular highlight testing (top right)
    draw.ellipse((150, 10, 190, 50), fill=(250, 250, 250))
    
    input_path = "test_polish_input.jpg"
    img.save(input_path)
    
    base_params = {"color": "#FF0000", "brightness_boost": 1.0} # Red

    # Test Cases
    cases = [
        ("Default (Full Strength)", {"blend_strength": 1.0, "finish": "matte"}),
        ("Half Strength", {"blend_strength": 0.5, "finish": "matte"}),
        ("High Gamma (Darker Shadows)", {"gamma": 2.2, "blend_strength": 1.0, "finish": "matte"}),
        ("Low Gamma (Brighter Shadows)", {"gamma": 0.5, "blend_strength": 1.0, "finish": "matte"}),
        ("Gloss Finish (Highlights)", {"finish": "gloss", "blend_strength": 1.0}),
    ]
    
    for name, params in cases:
        p = base_params.copy()
        p.update(params)
        output_path = f"test_polish_{name.replace(' ', '_').lower()}.jpg"
        
        print(f"Running Case: {name} -> {output_path}")
        process_image(input_path, output_path, p)
        
        # Analyze
        res = Image.open(output_path)
        pixels = res.load()
        
        # Sampling points
        # Top (Dark in original) -> expect dark red or black
        # Bottom (Bright in original) -> expect bright red
        # Bright Spot (250, 250, 250 in original) -> expect highlight in Gloss
        
        mid_y_val = pixels[100, 100] # Mid grey source
        bright_spot_val = pixels[170, 30] 
        
        print(f"  Mid Pixel: {mid_y_val}")
        print(f"  Bright Spot: {bright_spot_val}")
        
        if name == "Half Strength":
            # Original Mid is ~128 grey. Epoxy Mid is (128, 0, 0).
            # Half strength should be mix: (~128, ~64, ~64)
            if mid_y_val[1] > 20 and mid_y_val[2] > 20: 
                 print("  PASS: Colors desaturated (bleeding through original grey).")
            else:
                 print("  FAIL: Colors look fully saturated.")
                 
        if name == "Gloss Finish (Highlights)":
            # Bright spot should be VERY bright, potentially white or near white due to screen blend
            # Matte version of bright spot would be just Red (255, 0, 0) * boost
            # Gloss should add white back.
            if bright_spot_val[1] > 50 and bright_spot_val[2] > 50:
                print("  PASS: Specular highlight detected (not just pure red).")
            else:
                print("  FAIL: No specular highlight (pure red).")

    # Clean up
    # os.remove(input_path)
    print("Done.")

if __name__ == "__main__":
    test_epoxy_polish()
