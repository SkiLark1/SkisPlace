
import os
import shutil
import cv2
import numpy as np
from PIL import Image, ImageDraw
from app.core.engine import process_image

def verify_phase2():
    print("--- Verifying Phase 2 (Perspective & Tone) ---")
    
    # 1. Create a Synthetic "Garage" Image
    # Dark floor with a trapezoid shape (simulating perspective)
    width, height = 400, 300
    img = Image.new("RGB", (width, height), (50, 50, 50)) # Dark Grey Background
    draw = ImageDraw.Draw(img)
    
    # Floor Polygon (Trapezoid)
    # TL, TR, BR, BL
    floor_pts = [(50, 100), (350, 100), (400, 300), (0, 300)]
    draw.polygon(floor_pts, fill=(100, 100, 100)) # Lighter grey floor (L ~ 100)
    
    # Add a "Highlight" spot on the floor to test clamping
    draw.ellipse((200, 150, 250, 200), fill=(255, 255, 255))
    
    input_path = "test_phase2_input.jpg"
    img.save(input_path)
    
    # 2. Create a "User Mask" that matches this floor exactly
    # to trigger the Mask-Driven Perspective
    mask = Image.new("L", (width, height), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.polygon(floor_pts, fill=255)
    
    # Encode mask to base64 to simulate params
    import base64
    import io
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    mask_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    
    output_path = "test_phase2_output.jpg"
    
    # 3. Process with Grid Texture (to see perspective warp)
    # Ensure we use a texture that makes perspective obvious
    # I'll create a temp grid texture
    tex_w, tex_h = 100, 100
    texture = Image.new("RGB", (tex_w, tex_h), (200, 0, 0)) # Red
    t_draw = ImageDraw.Draw(texture)
    t_draw.rectangle((5, 5, 95, 95), outline=(255, 255, 255), width=2) # White box
    texture_path = "test_grid_tex.jpg"
    texture.save(texture_path)
    
    params = {
        "color": "#AA0000",
        "style_category": "flake", # Uses default profile
        "mask_blur": 0, # Sharp edges for verification
        "blend_strength": 1.0
    }
    
    print("Running Process Image...")
    res = process_image(input_path, output_path, params, custom_mask=mask_b64, texture_path=texture_path)
    
    if res["success"]:
        print("Success!")
        # We can't easily assert "perspective correct" without CV, but we can check if it crashed.
        # And we can check if the highlight area is clamped.
        
        out_img = Image.open(output_path)
        # Check center pixel (should be red/textured)
        center_px = out_img.getpixel((200, 250))
        print(f"Center Pixel: {center_px}")
        
        # Check highlight area (originally 255, 255, 255)
        # With tone mapping, this should be preserved/clamped but not blown out if style was dark?
        # Actually epoxy is Red.
        # Highlight = Screen(Red, White) -> Near White.
        # Check if it's not (255, 255, 255) if our clamp working? 
        # Wait, clamp was to 248.
        hl_px = out_img.getpixel((225, 175))
        print(f"Highlight Area Pixel: {hl_px}")
        if hl_px[0] <= 248 and hl_px[1] <= 248 and hl_px[2] <= 248:
             print("PASS: Highlight clamped <= 248")
        else:
             print(f"FAIL: Highlight not clamped correctly ({hl_px})")
             
    else:
        print(f"Failed: {res['message']}")

if __name__ == "__main__":
    verify_phase2()
