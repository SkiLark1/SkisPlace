import shutil
import os
import uuid
from typing import Any, List
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, Depends, Body
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api import deps
from app.db.session import AsyncSessionLocal
from app.models import EpoxyStyle
from app.api.endpoints.styles import _map_to_response, EpoxyStyleResponse

router = APIRouter()

UPLOAD_DIR = "static/uploads"
# Ensure exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Schemas ---
class PreviewRequest(BaseModel):
    image_id: str
    style_id: str

class UploadResponse(BaseModel):
    id: str
    url: str

class PreviewResponse(BaseModel):
    status: str
    result_url: str

# --- Endpoints ---

@router.get("/styles/public", response_model=List[EpoxyStyleResponse])
async def get_public_styles(
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Get available epoxy styles.
    """
    query = select(EpoxyStyle).options(selectinload(EpoxyStyle.cover_image))
    result = await db.execute(query)
    styles = result.scalars().all()
    return [_map_to_response(s) for s in styles]

@router.post("/uploads", response_model=UploadResponse)
async def upload_image(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Upload a user image for processing.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    file_ext = os.path.splitext(file.filename)[1]
    asset_id = uuid.uuid4()
    storage_name = f"{asset_id}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, storage_name)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    # Generate absolute URL
    base_url = str(request.base_url).rstrip("/")
    # Mount is /static/uploads
    url = f"{base_url}/static/uploads/{storage_name}"

    return UploadResponse(id=str(asset_id), url=url)

@router.post("/preview", response_model=PreviewResponse)
async def create_preview_job(
    request: Request,
    image_id: str = Form(...),
    style_id: str = Form(...)
):
    """
    Request a preview render.
    Currently assumes the 'image_id' corresponds to a file named {image_id}.* in uploads.
    """
    try:
        # 1. Resolve Image Path (Check if exists)
        # Check if dir exists first
        if not os.path.exists(UPLOAD_DIR):
             print(f"DEBUG: UPLOAD_DIR {UPLOAD_DIR} does not exist. CWD: {os.getcwd()}")
             return JSONResponse(status_code=500, content={"status": "error", "message": f"Upload dir not found: {UPLOAD_DIR} in {os.getcwd()}"})

        found_file = None
        for fname in os.listdir(UPLOAD_DIR):
            if fname.startswith(image_id):
                found_file = fname
                break
                
        if not found_file:
             pass # Will handle below

        # 2. Processing
        print(f"DEBUG: Processing found_file: {found_file}")
        print(f"DEBUG: CWD: {os.getcwd()}")
        if found_file:
            input_path = os.path.join(UPLOAD_DIR, found_file)
            print(f"DEBUG: Input Path: {input_path}")
            
            # Determine output path
            output_filename = f"preview_{uuid.uuid4()}.jpg"
            output_path = os.path.join(UPLOAD_DIR, output_filename)
            print(f"DEBUG: Output Path: {output_path}")

            process_success = False
            
            # Params for engine
            params = {"color": "#a1a1aa"} 

            from app.core.engine import process_image
            process_success = process_image(input_path, output_path, params)
            print(f"DEBUG: Process Success: {process_success}")
                 
            base_url = str(request.base_url).rstrip("/")
            if process_success:
                 result_url = f"{base_url}/static/uploads/{output_filename}"
            else:
                 # Fallback to original
                 result_url = f"{base_url}/static/uploads/{found_file}"
                 
        else:
             return JSONResponse(status_code=404, content={"status": "error", "message": "Image not found"})

        return PreviewResponse(
            status="success",
            result_url=result_url
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"DEBUG: Global Endpoint Catch: {e}")
        print(tb)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e), "traceback": tb})
