import numpy as np
from PIL import Image, ImageFilter, ImageOps

def detect_camera_geometry(image: Image.Image, debug: bool = False) -> str:
    """
    Analyzes the image to determine if it is 'eye_level' (perspective shot with walls)
    or 'top_down' (flat lay of floor).
    
    Heuristic:
    1. Resize to small working scale.
    2. Compute vertical gradients (detect horizontal edges).
    3. Project gradients horizontally to find "Horizon Lines".
    4. If a strong horizon line exists in [20% - 70%] of height, assume Eye Level.
    5. If edge distribution is uniform or scattered, assume Top Down.
    """
    try:
        # 1. Resize for speed and noise reduction
        # 256x256 is enough for macro geometry
        work_img = image.copy().convert("L")
        work_img = ImageOps.exif_transpose(work_img)
        work_img = work_img.resize((256, 256), Image.Resampling.BILINEAR)
        
        # 2. Blur slightly to ignore texture (we want structure)
        work_img = work_img.filter(ImageFilter.GaussianBlur(radius=2))
        
        # 3. Compute Vertical Gradient (Sobel-ish) using Numpy
        # taking difference between row i and row i+1
        img_arr = np.array(work_img, dtype=np.float32)
        
        # Standard Sobel Y Kernel approximation: [-1, -2, -1], [0,0,0], [1, 2, 1]
        # Or just simple diff axis=0
        # Simple diff:
        grad_y = np.abs(np.diff(img_arr, axis=0))
        
        # 4. Project horizontally (Sum absolutes across columns)
        # Shape: (255, 256) -> Sum -> (255,)
        row_energy = np.sum(grad_y, axis=1)
        
        # Normalize
        if np.max(row_energy) > 0:
            row_energy = row_energy / np.max(row_energy)
        
        # 5. Peak Analysis
        # Eye-level typically has a specific "Horizon" where wall meets floor.
        # This looks like 1 or 2 strong peaks.
        # Top-down typically has uniform texture (many small peaks or noise).
        
        # Define Horizon Search Region: 15% to 75% from top
        h_start = int(256 * 0.15)
        h_end = int(256 * 0.75)
        
        valid_region = row_energy[h_start:h_end]
        
        # Metric A: Max Peak Strength in region
        peak_strength = np.max(valid_region) if valid_region.size > 0 else 0
        
        # Metric B: "Peakedness" (Max / Mean)
        # If mean is high (noisy texture), peakedness is low.
        # If mean is low (flat wall/floor) and max is high (edge), peakedness is high.
        mean_energy = np.mean(valid_region) if valid_region.size > 0 else 0.001
        peakedness = peak_strength / (mean_energy + 0.001)
        
        # Thresholds derived from heuristics
        # Strong horizon usually > 2.5 peakedness and > 0.3 relative strength (if normalized against global max)
        # Note: Lowered from 3.0 to 2.5 to catch more eye-level images
        
        is_eye_level = False
        
        # If we have a distinct line (lowered threshold)
        if peakedness > 2.5 and peak_strength > 0.3:
            is_eye_level = True
        # Secondary check: very strong peak even with lower peakedness
        elif peakedness > 1.8 and peak_strength > 0.6:
            is_eye_level = True
            
        if debug:
            print(f"DEBUG: Geometry Detection | Peak: {peak_strength:.2f} | Peakedness: {peakedness:.2f} | Verdict: {'Eye Level' if is_eye_level else 'Top Down'}")
            
        return "eye_level" if is_eye_level else "top_down"
        
    except Exception as e:
        print(f"WARN: Geometry detection failed: {e}")
        return "top_down" # Safe default
