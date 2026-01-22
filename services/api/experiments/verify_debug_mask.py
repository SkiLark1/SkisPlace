from app.core.engine import process_image
from PIL import Image
import os
import shutil

def verify_debug_mask():
    print("Verifying Debug Mask Generation...")
    
    # Setup
    input_path = "debug_input.jpg"
    output_path = "debug_output.jpg"
    
    # Create dummy input
    img = Image.new("RGB", (50, 50), (128, 128, 128))
    img.save(input_path)
    
    # 1. Test Regular (Debug=False)
    print("\nTesting Debug=False...")
    res_false = process_image(input_path, output_path, {"color": "#FF0000"}, debug=False)
    
    if isinstance(res_false, dict):
         print(f"Result (False): {res_false}")
         if not res_false.get("mask_filename"):
              print("PASS: No mask returned for debug=False")
         else:
              print("FAIL: Mask returned but debug=False")
    else:
         print(f"FAIL: Unexpected return type: {type(res_false)}")

    # 2. Test Debug (Debug=True)
    print("\nTesting Debug=True...")
    res_true = process_image(input_path, output_path, {"color": "#FF0000"}, debug=True)
    
    mask_file = res_true.get("mask_filename")
    print(f"Result (True): {res_true}")
    
    if mask_file:
         print(f"Mask filename returned: {mask_file}")
         if os.path.exists(mask_file):
              print("PASS: Mask file exists on disk (relative check).")
         # Check absolute
         abs_mask_path = os.path.abspath(mask_file)
         if os.path.exists(abs_mask_path):
               print(f"PASS: Mask found at {abs_mask_path}")
         else:
               # engine saves relative to output path dirname
               # output_path is "debug_output.jpg" (CWD)
               # so mask should be in CWD
               if os.path.exists(mask_file):
                    print("PASS: Mask found in CWD")
               else:
                    print("FAIL: Mask file missing on disk")
    else:
         print("FAIL: No mask filename returned for debug=True")

    # Cleanup
    for f in [input_path, output_path, mask_file]:
        if f and os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    verify_debug_mask()
