import shutil
import os
import uuid
from typing import Any
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

UPLOAD_DIR = "/app/static/uploads"
# Ensure exists (redundant if main.py does it, but safe)
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/preview")
async def create_preview(
    request: Request,
    image: UploadFile = File(...),
    style_id: str = Form(...)
) -> Any:
    """
    Generate a preview. 
    1. Save uploaded image.
    2. (Future) Process image with style.
    3. Return URL to result.
    """
    if not image.filename:
        raise HTTPException(status_code=400, detail="No filename")

    # 1. Save Image
    file_ext = os.path.splitext(image.filename)[1]
    asset_id = uuid.uuid4()
    storage_name = f"{asset_id}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, storage_name)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    # 2. Generate URL
    # Construct absolute URL based on request base_url
    # Expected mount in main.py is "/static/uploads"
    # request.base_url returns e.g. "http://localhost:8000/"
    base_url = str(request.base_url).rstrip("/")
    result_url = f"{base_url}/static/uploads/{storage_name}"

    return {
        "status": "success",
        "result_url": result_url,
        "style_id": style_id
    }
