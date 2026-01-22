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
from app.models import EpoxyStyle, ProjectModule
from app.api.endpoints.styles import _map_to_response, EpoxyStyleResponse
from app.core.engine import process_image

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
    mask_url: str | None = None
    mask_source: str | None = None

# --- Endpoints ---

@router.get("/styles/public", response_model=List[EpoxyStyleResponse])
async def get_public_styles(
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
    project: Any = Depends(deps.get_current_project_opt)  # Lenient - returns None if no key
):
    """
    Get available epoxy styles. Lenient endpoint for widget.
    - With valid API key/preview token: Returns project styles (or system defaults if none)
    - Without key: Returns system default styles only
    """
    styles = []

    # 1. Try Project Styles (if authenticated)
    if project:
        query = select(EpoxyStyle).where(EpoxyStyle.project_id == project.id).options(selectinload(EpoxyStyle.cover_image))
        result = await db.execute(query)
        project_styles = result.scalars().all()
        
        if project_styles:
            styles = project_styles

    # 2. Fallback to System Defaults
    if not styles:
        query = select(EpoxyStyle).where(
            EpoxyStyle.project_id == None,
            EpoxyStyle.is_system == True
        ).options(selectinload(EpoxyStyle.cover_image))
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

from app.models.module import ProjectModule, Module
from app.models.project import Project

@router.post("/preview", response_model=PreviewResponse)
async def create_preview_job(
    request: Request,
    image_id: str = Form(...),
    style_id: str = Form(...),
    custom_mask: str | None = Form(None), # Base64 encoded PNG
    debug: bool = Form(False),
    db: AsyncSession = Depends(deps.get_db),
    project_from_key: Project | None = Depends(deps.get_current_project_opt),
    project_id: str | None = Form(None), 
    module_id: str | None = Form(None),
):
    """
    Request a preview render.
    Currently assumes the 'image_id' corresponds to a file named {image_id}.* in uploads.
    """
    # Fallback to project from API Key if not provided in form
    if not project_id and project_from_key:
        project_id = str(project_from_key.id)

    print(f"DEBUG: Epoxy Preview Request. ProjectID={project_id}, StyleID={style_id}")

    try:
        # 0. Fetch Style
        try:
            uuid_obj = uuid.UUID(style_id)
        except ValueError:
             return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid style_id format"})

        query = select(EpoxyStyle).where(EpoxyStyle.id == uuid_obj)
        result = await db.execute(query)
        style = result.scalar_one_or_none()

        if not style:
             return JSONResponse(status_code=404, content={"status": "error", "message": "Style not found"})

        # 1. Fetch Module Config for AI
        ai_config = None
        if project_id:
            try:
                # Find the ProjectModule config
                print(f"DEBUG: Looking for config for project {project_id}")
                mod_query = (
                    select(ProjectModule)
                    .join(Module)
                    .where(
                        ProjectModule.project_id == uuid.UUID(project_id),
                        Module.name == "Epoxy Visualizer"
                    )
                )
                mod_result = await db.execute(mod_query)
                module_obj = mod_result.scalar_one_or_none()
                
                if module_obj:
                    if module_obj.config:
                         ai_config = module_obj.config.get("ai_segmentation", {})
                    else:
                         print("DEBUG: Module found but has no config")
                         
                    # Ensure defaults
                    if ai_config and ai_config.get("enabled"):
                        if "confidence_threshold" not in ai_config:
                            ai_config["confidence_threshold"] = 0.5
                else:
                    print("DEBUG: No ProjectModule found for this project + Epoxy Visualizer")
                            
                print(f"DEBUG: Project {project_id} AI Config: {ai_config}")
            except Exception as e:
                print(f"WARN: Failed to fetch module config: {e}")
                import traceback
                traceback.print_exc()

        # 2. Resolve Image Path (Check if exists)
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
            params = style.parameters if style.parameters else {}
            if "color" not in params:
                 params["color"] = "#a1a1aa" 

            # Call engine with debug flag and AI config
            result = process_image(input_path, output_path, params, debug=debug, custom_mask=custom_mask, ai_config=ai_config)
            
            # Handle result dict
            process_success = result.get("success", False)
            print(f"DEBUG: Process Success: {process_success}")
                 
            base_url = str(request.base_url).rstrip("/")
            result_url = ""
            mask_url = None
            
            if process_success:
                 result_url = f"{base_url}/static/uploads/{output_filename}"
                 if debug and result.get("mask_filename"):
                     mask_url = f"{base_url}/static/uploads/{result['mask_filename']}"
            else:
                 # Fallback to original
                 result_url = f"{base_url}/static/uploads/{found_file}"
                 if result.get("message"):
                     print(f"DEBUG: Processing Error: {result['message']}")
                 
        else:
             return JSONResponse(status_code=404, content={"status": "error", "message": "Image not found"})

        return PreviewResponse(
            status="success" if process_success else "error",
            result_url=result_url,
            mask_url=mask_url,
            mask_source=result.get("mask_source")
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"DEBUG: Global Endpoint Catch: {e}")
        print(tb)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e), "traceback": tb})
