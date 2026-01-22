from app.core.engine import process_image
from PIL import Image
import os
import shutil

def verify_style_params():
    print("Verifying Style Parameter Handling...")
    
    # Setup
    input_path = "verify_input.jpg"
    output_red = "verify_output_red.jpg" 
    output_blue = "verify_output_blue.jpg"
    
    img = Image.new("RGB", (50, 50), (128, 128, 128))
    img.save(input_path)
    
    # 1. Test Red Style
    print("Testing Red Style (#FF0000)...")
    params_red = {"color": "#FF0000"}
    process_image(input_path, output_red, params_red)
    
    # 2. Test Blue Style
    print("Testing Blue Style (#0000FF)...")
    params_blue = {"color": "#0000FF"}
    process_image(input_path, output_blue, params_blue)
    
    # Analysis
    pixel_red = Image.open(output_red).load()[25, 45]
    pixel_blue = Image.open(output_blue).load()[25, 45]
    
    print(f"Red Output Pixel: {pixel_red}")
    print(f"Blue Output Pixel: {pixel_blue}")

    # Check Red (Red channel should be dominant)
    if pixel_red[0] > pixel_red[2] + 50:
        print("PASS: Red style produced reddish output.")
    else:
        print("FAIL: Red style output is not red enough.")
        
    # Check Blue (Blue channel should be dominant)
    if pixel_blue[2] > pixel_blue[0] + 50:
         print("PASS: Blue style produced bluish output.")
    else:
         print("FAIL: Blue style output is not blue enough.")

    # Cleanup
    for f in [input_path, output_red, output_blue]:
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    verify_style_params()
