import os
from PIL import Image
from app.core.engine import process_image

def test_epoxy_logic():
    # 1. Create Dummy Image (100x100, neutral grey)
    img = Image.new("RGB", (100, 100), (128, 128, 128))
    input_path = "test_input.jpg"
    output_path = "test_output.jpg"
    img.save(input_path)

    # 2. Process
    params = {"color": "#FF0000", "mask_blur": 0} # Red epoxy, no blur
    success = process_image(input_path, output_path, params)
    
    if not success:
        print("Processing failed")
        return

    # 3. Analyze Result
    result = Image.open(output_path)
    pixels = result.load()
    
    # Top pixel (0, 0) should be original grey (128, 128, 128) because mask is 0
    top_pixel = pixels[50, 5] # Middle-ish x, Top y
    print(f"Top Pixel (Should be ~128, 128, 128): {top_pixel}")
    
    # Bottom pixel (50, 95) should be Red-tinted and impacted by brightness
    # Original (128) -> Grayscale (128). Color (255, 0, 0).
    # Multiply: (128/255 * 255, 128/255 * 0, 128/255 * 0) = (128, 0, 0)
    # Brightness 1.8x -> (230, 0, 0)
    bottom_pixel = pixels[50, 95]
    print(f"Bottom Pixel (Should be Reddish): {bottom_pixel}")
    
    # Check if Top Changed
    if abs(top_pixel[0] - 128) > 5:
        print("FAIL: Top pixel changed! Mask is leaking or not applied.")
    else:
        print("PASS: Top pixel preserved.")
        
    # Check Brightness
    # 1.8x of 128 is 230.
    if bottom_pixel[0] > 200:
        print("OBSERVATION: Bottom is significantly brighter.")
    
    # Clean up
    if os.path.exists(input_path):
        os.remove(input_path)
    if os.path.exists(output_path):
        os.remove(output_path)

if __name__ == "__main__":
    test_epoxy_logic()
