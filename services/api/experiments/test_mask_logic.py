import os
import shutil
from PIL import Image, ImageDraw
from app.core.engine import process_image

def test_mask_logic():
    print("Testing Smart Mask Logic...")
    
    # 1. Create a "Wall and Floor" Dummy Image
    width, height = 200, 200
    img = Image.new("RGB", (width, height), (200, 200, 200)) # Light Grey Wall
    draw = ImageDraw.Draw(img)
    # Draw floor darker
    draw.rectangle((0, 100, width, height), fill=(100, 100, 100))
    
    input_path = "test_mask_input.jpg"
    img.save(input_path)
    
    # We'll use a bright red epoxy to easily see the mask coverage
    base_params = {"color": "#FF0000", "blend_strength": 1.0} 

    # Test Cases
    cases = [
        ("Default (Start 0.45)", {}),
        ("High Horizon (Start 0.2)", {"mask_start": 0.2}),
        ("Low Horizon (Start 0.8)", {"mask_start": 0.8}),
        ("Fast Gradient (Falloff 0.5)", {"mask_start": 0.45, "mask_falloff": 0.5}),
        ("Slow Gradient (Falloff 2.0)", {"mask_start": 0.45, "mask_falloff": 2.0}),
        ("Heavy Blur (Blur 20)", {"mask_start": 0.45, "mask_blur": 20}),
    ]
    
    for name, params in cases:
        p = base_params.copy()
        p.update(params)
        output_path = f"test_mask_{name.split(' (')[0].replace(' ', '_').lower()}.jpg"
        
        print(f"Running Case: {name} -> {output_path}")
        # Enable debug to get the mask file
        res = process_image(input_path, output_path, p, debug=True)
        
        if res['success']:
            mask_file = res.get('mask_filename')
            if mask_file:
                print(f"  Generated Mask: {mask_file}")
                # We can analyze the mask directly if we want, but visual check is key here.
                # Let's do a simple pixel check on the OUTPUT image to see where Red starts.
                
                out_img = Image.open(output_path)
                pixels = out_img.load()
                
                # Check pixel at Y=30 (should be grey in Default, Red in High Horizon)
                y30 = pixels[100, 30]
                # Check pixel at Y=90 (should be grey in Default, Red in High Horizon)
                y90 = pixels[100, 90]
                
                if name == "High Horizon (Start 0.2)":
                    # At 0.2 (Y=40), mask starts. So Y=50 should be red-ish.
                    # Y=30 is above 0.2, so grey.
                    print(f"  Y=30 (Expect Grey): {y30}")
                    print(f"  Y=90 (Expect Red): {y90}")
                    if y90[0] > 150 and y90[1] < 100:
                         print("  PASS: Mask extended upwards correctly.")
                    else:
                         print("  FAIL: Mask did not extend upwards.")

                if name == "Low Horizon (Start 0.8)":
                    # Mask starts at 0.8 (Y=160).
                    # Y=150 should be Grey.
                    y150 = pixels[100, 150]
                    print(f"  Y=150 (Expect Grey): {y150}")
                    if abs(y150[0] - y150[1]) < 10: # Grey is R=G=B
                        print("  PASS: Mask pushed downwards correctly.")
                    else:
                        print("  FAIL: Mask started too early.")

    print("Done.")

if __name__ == "__main__":
    test_mask_logic()
