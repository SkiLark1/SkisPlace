from typing import Any, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api import deps
from app.models import EpoxyStyle, User, Asset
from app.db.session import AsyncSessionLocal

router = APIRouter()

# --- Schemas ---
class StyleTextureMaps(BaseModel):
    albedo: Optional[str] = None
    normal: Optional[str] = None
    roughness: Optional[str] = None
    metalness: Optional[str] = None
    ao: Optional[str] = None

class EpoxyStyleCreate(BaseModel):
    name: str
    category: str = "General"
    cover_image_id: Optional[str] = None
    project_id: Optional[uuid.UUID] = None
    texture_maps: StyleTextureMaps = StyleTextureMaps()
    parameters: dict = {}

class EpoxyStyleResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    is_system: bool
    project_id: Optional[uuid.UUID] = None
    cover_image_url: Optional[str] = None
    texture_maps: dict
    parameters: dict
    
    class Config:
        from_attributes = True

# --- Endpoints ---

@router.post("/", response_model=EpoxyStyleResponse)
async def create_style(
    style_in: EpoxyStyleCreate,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Create a new Epoxy Style.
    If project_id is provided, creates a Project Style (is_system=False).
    If no project_id, creates a System Style (is_system=True) - Admin only (implicit).
    """
    # 1. Validate Cover Image
    cover_uuid = None
    if style_in.cover_image_id:
        try:
            cover_uuid = uuid.UUID(style_in.cover_image_id)
            # Check exist
            res = await db.execute(select(Asset).where(Asset.id == cover_uuid))
            if not res.scalars().first():
                 raise HTTPException(status_code=400, detail="Cover image asset not found")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cover image UUID")

    # 2. Determine System vs Project
    is_system = False
    if style_in.project_id:
        is_system = False
        # Limit checking: ensure project exists? 
        # For now we rely on FK constraint or simple success. 
    else:
        # If no project, assume System Style (Admin)
        is_system = True

    # 3. Create Record
    new_style = EpoxyStyle(
        name=style_in.name,
        category=style_in.category,
        is_system=is_system, 
        project_id=style_in.project_id,
        cover_image_id=cover_uuid,
        texture_maps=style_in.texture_maps.model_dump(exclude_none=True),
        parameters=style_in.parameters
    )
    
    db.add(new_style)
    await db.commit()
    await db.refresh(new_style)
    
    # Reload for relationships
    # manual fetch because clean return
    return await _fetch_style_response(db, new_style.id)


@router.get("/", response_model=List[EpoxyStyleResponse])
async def list_styles(
    category: Optional[str] = None,
    db: AsyncSession = Depends(deps.get_db),
    # Public or Admin? Let's make this one public-ish or authenticated.
    # If "Admin Management", assume auth required.
    current_user: User = Depends(deps.get_current_active_user),
):
    query = select(EpoxyStyle).options(selectinload(EpoxyStyle.cover_image))
    if category:
        query = query.where(EpoxyStyle.category == category)
    
    result = await db.execute(query)
    styles = result.scalars().all()
    
    return [_map_to_response(s) for s in styles]

@router.get("/public", response_model=List[EpoxyStyleResponse])
async def list_public_styles(
    db: AsyncSession = Depends(deps.get_db),
    project: Any = Depends(deps.verify_public_origin), # Enforce API Key
    debug: bool = False
):
    """
    Publicly accessible styles for the visualizer.
    Returns Project Styles if they exist; otherwise returns System Styles.
    """
    # 1. Try to get Project Styles
    query = select(EpoxyStyle).where(
        EpoxyStyle.project_id == project.id
    ).options(selectinload(EpoxyStyle.cover_image))
    
    result = await db.execute(query)
    project_styles = result.scalars().all()
    
    if project_styles:
        return [_map_to_response(s) for s in project_styles]
        
    # 2. Fallback to System Styles
    query_sys = select(EpoxyStyle).where(
        EpoxyStyle.is_system == True
    ).options(selectinload(EpoxyStyle.cover_image))
    
    result_sys = await db.execute(query_sys)
    system_styles = result_sys.scalars().all()
    
    return [_map_to_response(s) for s in system_styles]


# --- Helpers ---

def _map_to_response(style: EpoxyStyle):
    return EpoxyStyleResponse(
        id=style.id,
        name=style.name,
        category=style.category,
        is_system=style.is_system,
        # Flatten URL
        cover_image_url=style.cover_image.url if style.cover_image else None,
        texture_maps=style.texture_maps or {},
        parameters=style.parameters or {}
    )

async def _fetch_style_response(db: AsyncSession, style_id: uuid.UUID):
    query = select(EpoxyStyle).where(EpoxyStyle.id == style_id).options(selectinload(EpoxyStyle.cover_image))
    result = await db.execute(query)
    style = result.scalars().first()
    return _map_to_response(style)
