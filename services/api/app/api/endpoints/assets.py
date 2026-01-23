import shutil
import os
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import deps
from app.models import Asset, User, Project
from app.db.session import AsyncSessionLocal

router = APIRouter()

UPLOAD_DIR = "/app/static/uploads"
# Ensure exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=dict)
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Upload a file loosely associated with a project.
    For MVP, stores locally in static/uploads.
    """
    # Verify project access (if strictness needed)
    # For now, just allow authenticated users to upload to any project they know ID of?
    # Better: check if user owns project / is admin.
    
    # 1. Validate File
    # simple check
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    # 2. Generate Path
    file_ext = os.path.splitext(file.filename)[1]
    asset_id = uuid.uuid4()
    storage_name = f"{asset_id}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, storage_name)
    
    # 3. Save File
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # MISSION 20: Seamless Tile Conversion
        # Automatically convert to 2x2 mirror tile
        try:
            from PIL import Image, ImageOps
            img = Image.open(file_path).convert("RGBA")
            w, h = img.size
            if w > 0 and h > 0:
                canvas = Image.new("RGBA", (w * 2, h * 2))
                # TL: Orig
                canvas.paste(img, (0, 0))
                # TR: Mirror X
                mx = ImageOps.mirror(img)
                canvas.paste(mx, (w, 0))
                # BL: Mirror Y
                my = ImageOps.flip(img)
                canvas.paste(my, (0, h))
                # BR: Mirror XY
                mxy = ImageOps.flip(mx)
                canvas.paste(mxy, (w, h))
                
                canvas.save(file_path)
                print(f"DEBUG: Converted {file.filename} to seamless tile")
        except Exception as se:
            print(f"WARN: Seamless conversion failed: {se}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
        
    # 4. Create Asset Record
    # We need a valid project UUID.
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID")

    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_uuid))
    project = result.scalars().first()
    if not project:
         raise HTTPException(status_code=404, detail="Project not found")

    new_asset = Asset(
        id=asset_id,
        project_id=project_uuid,
        type="image", # detect mime type later
        url=f"/static/uploads/{storage_name}",
        meta={"original_name": file.filename, "content_type": file.content_type}
    )
    
    db.add(new_asset)
    await db.commit()
    await db.refresh(new_asset)
    
    return {
        "id": str(new_asset.id),
        "url": new_asset.url,
        "filename": file.filename
    }

@router.get("/{asset_id}")
async def get_asset(
    asset_id: str,
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Retrieve asset info.
    """
    try:
        uuid_obj = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    result = await db.execute(select(Asset).where(Asset.id == uuid_obj))
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    return asset
