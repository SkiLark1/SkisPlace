from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.db.base import Base
from app.models.project import Project, ProjectDomain, ApiKey
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectDomainCreate,
    ProjectDomainResponse,
)
from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeySecret
from app.schemas.module import ProjectModuleCreate, ProjectModuleUpdate, ProjectModuleResponse
from app.core.security import generate_api_key, hash_api_key
from app.models.module import ProjectModule, Module

router = APIRouter()

# --- Projects ---

@router.get("/", response_model=List[ProjectResponse])
async def read_projects(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    client_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve projects.
    """
    query = select(Project).options(selectinload(Project.domains)).offset(skip).limit(limit)
    
    if client_id:
        query = query.where(Project.client_id == client_id)
        
    result = await db.execute(query)
    projects = result.scalars().all()
    return projects

@router.post("/", response_model=ProjectResponse)
async def create_project(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_in: ProjectCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create new project.
    """
    # Slug generation if not provided is handled by frontend or could be here. 
    # For now assuming frontend provides it or we default to name-based?
    # Let's keep it simple: if slug missing, default to name lowercased (basic)
    slug = project_in.slug
    if not slug:
        slug = project_in.name.lower().replace(" ", "-")

    project = Project(
        client_id=project_in.client_id,
        name=project_in.name,
        slug=slug,
        config=project_in.config,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    # Refresh with domains for response model
    # (Although fresh project has no domains, but good practice for consistency)
    
    # Manually construct response to completely bypass Pydantic/SQLAlchemy relationship loading conflicts
    return ProjectResponse(
        id=project.id,
        client_id=project.client_id,
        name=project.name,
        slug=project.slug,
        config=project.config,
        created_at=project.created_at,
        updated_at=project.updated_at,
        domains=[] 
    )

@router.get("/{project_id}", response_model=ProjectResponse)
async def read_project(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get project by ID.
    """
    query = select(Project).where(Project.id == project_id).options(selectinload(Project.domains))
    result = await db.execute(query)
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    project_update: ProjectUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a project.
    """
    query = select(Project).where(Project.id == project_id).options(selectinload(Project.domains))
    result = await db.execute(query)
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.add(project)
    await db.commit()
    await db.refresh(project)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project

from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings

@router.get("/{project_id}/preview-token")
async def get_preview_token(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Generate a short-lived preview token for testing.
    """
    # Verify project exists
    query = select(Project).where(Project.id == project_id)
    result = await db.execute(query)
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Access Control: Ensure user has access (for now just logged in, consistent with other endpoints)
    
    expires_delta = timedelta(minutes=10)
    expire = datetime.utcnow() + expires_delta
    
    to_encode = {
        "sub": str(project_id),
        "type": "preview",
        "exp": expire
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return {
        "token": encoded_jwt,
        "expires_at": expire
    }

# --- Domains ---

@router.post("/{project_id}/domains", response_model=ProjectDomainResponse)
async def create_domain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    domain_in: ProjectDomainCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Add a domain to a project.
    """
    # Check project exists
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    domain = ProjectDomain(
        project_id=project_id,
        domain=domain_in.domain,
        verified=False # Always start unverified
    )
    db.add(domain)
    try:
        await db.commit()
        await db.refresh(domain)
    except Exception as e:
        # Likely unique constraint violation
        await db.rollback()
        raise HTTPException(status_code=400, detail="Domain already exists")
        
    return domain

@router.delete("/{project_id}/domains/{domain_id}", response_model=ProjectDomainResponse)
async def delete_domain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    domain_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Remove a domain from a project.
    """
    query = select(ProjectDomain).where(
        ProjectDomain.id == domain_id,
        ProjectDomain.project_id == project_id
    )
    result = await db.execute(query)
    domain = result.scalars().first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    await db.delete(domain)
    await db.commit()
    return domain

# --- API Keys ---

@router.post("/{project_id}/api-keys", response_model=ApiKeySecret)
async def create_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    key_in: ApiKeyCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a new API key for a project.
    """
    # Check project exists
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Generate key
    raw_key = generate_api_key()
    hashed_key = hash_api_key(raw_key)
    prefix = raw_key[:10] # e.g. "sk_live_12"

    api_key = ApiKey(
        project_id=project_id,
        key_hash=hashed_key,
        prefix=prefix,
        name=key_in.name,
        scopes=key_in.scopes,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    # Return the secret key ONLY once
    return ApiKeySecret(
        id=api_key.id,
        project_id=api_key.project_id,
        prefix=api_key.prefix,
        name=api_key.name,
        scopes=api_key.scopes,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        key=raw_key # The full secret
    )

@router.get("/{project_id}/api-keys", response_model=List[ApiKeyResponse])
async def read_api_keys(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    List API keys for a project.
    """
    query = select(ApiKey).where(ApiKey.project_id == project_id).offset(skip).limit(limit)
    result = await db.execute(query)
    keys = result.scalars().all()
    return keys

@router.delete("/{project_id}/api-keys/{key_id}", response_model=ApiKeyResponse)
async def delete_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    key_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Revoke an API key.
    """
    query = select(ApiKey).where(
        ApiKey.id == key_id,
        ApiKey.project_id == project_id
    )
    result = await db.execute(query)
    api_key = result.scalars().first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")

    await db.delete(api_key)
    await db.commit()
    return api_key

# --- Modules ---

@router.get("/{project_id}/modules", response_model=List[ProjectModuleResponse])
async def read_project_modules(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List modules enabled for a project.
    """
    query = select(ProjectModule).where(ProjectModule.project_id == project_id).options(selectinload(ProjectModule.module))
    result = await db.execute(query)
    modules = result.scalars().all()
    return modules

@router.post("/{project_id}/modules", response_model=ProjectModuleResponse)
async def enable_project_module(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    module_in: ProjectModuleCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Enable a module for a project.
    """
    # Check if already enabled
    query = select(ProjectModule).where(
        ProjectModule.project_id == project_id,
        ProjectModule.module_id == module_in.module_id
    )
    result = await db.execute(query)
    existing = result.scalars().first()
    if existing:
        if not existing.enabled:
            existing.enabled = True
            if module_in.config:
                existing.config = module_in.config
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            # Reload relationship
            query = select(ProjectModule).where(ProjectModule.id == existing.id).options(selectinload(ProjectModule.module))
            result = await db.execute(query)
            return result.scalars().first()
        return existing

    # Create new
    pm = ProjectModule(
        project_id=project_id,
        module_id=module_in.module_id,
        config=module_in.config or {},
        enabled=True
    )
    db.add(pm)
    await db.commit()
    await db.refresh(pm)
    
    # Reload with module details
    query = select(ProjectModule).where(ProjectModule.id == pm.id).options(selectinload(ProjectModule.module))
    result = await db.execute(query)
    return result.scalars().first()

@router.patch("/{project_id}/modules/{system_module_id}", response_model=ProjectModuleResponse)
async def update_project_module(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    system_module_id: UUID, 
    module_update: ProjectModuleUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update project module config or status using System Module ID.
    """
    query = select(ProjectModule).where(
        ProjectModule.project_id == project_id,
        ProjectModule.module_id == system_module_id
    )
    result = await db.execute(query)
    pm = result.scalars().first()
    
    if not pm:
        raise HTTPException(status_code=404, detail="Module not enabled for this project")

    update_data = module_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pm, field, value)

    db.add(pm)
    await db.commit()
    await db.refresh(pm)
    
    # Reload with module details
    query = select(ProjectModule).where(ProjectModule.id == pm.id).options(selectinload(ProjectModule.module))
    result = await db.execute(query)
    return result.scalars().first()

@router.delete("/{project_id}/modules/{system_module_id}", response_model=ProjectModuleResponse)
async def disable_project_module(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    system_module_id: UUID, # System Module ID
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Disable (remove) a module from a project.
    """
    query = select(ProjectModule).where(
        ProjectModule.project_id == project_id,
        ProjectModule.module_id == system_module_id
    ).options(selectinload(ProjectModule.module))
    
    result = await db.execute(query)
    pm = result.scalars().first()
    
    if not pm:
        raise HTTPException(status_code=404, detail="Module not found on project")

    # Snapshot data before deletion/expiration
    response = ProjectModuleResponse.model_validate(pm)

    await db.delete(pm)
    await db.commit()
    
    return response


# --- Styles (Project Scoped) ---

from app.models.epoxy_style import EpoxyStyle
from app.api.endpoints.styles import EpoxyStyleResponse, _map_to_response

@router.get("/{project_id}/styles", response_model=List[EpoxyStyleResponse])
async def read_project_styles(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List custom styles for a project.
    """
    # Verify project exists/access
    project = await db.get(Project, project_id)
    if not project:
         raise HTTPException(status_code=404, detail="Project not found")

    query = select(EpoxyStyle).where(EpoxyStyle.project_id == project_id).options(selectinload(EpoxyStyle.cover_image))
    result = await db.execute(query)
    styles = result.scalars().all()
    
    return [_map_to_response(s) for s in styles]

@router.delete("/{project_id}/styles/{style_id}", response_model=EpoxyStyleResponse)
async def delete_project_style(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    style_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete a project-specific style. 
    Does not allow deleting system styles (which have null project_id).
    """
    # Find style ensuring it belongs to project
    query = select(EpoxyStyle).where(
        EpoxyStyle.id == style_id,
        EpoxyStyle.project_id == project_id
    ).options(selectinload(EpoxyStyle.cover_image))
    
    result = await db.execute(query)
    style = result.scalars().first()
    
    if not style:
        # Check if it exists but is system?
        check_q = select(EpoxyStyle).where(EpoxyStyle.id == style_id)
        res = await db.execute(check_q)
        if res.scalars().first():
             raise HTTPException(status_code=403, detail="Cannot delete system style or style from another project")
        raise HTTPException(status_code=404, detail="Style not found")

    response = _map_to_response(style)
    
    await db.delete(style)
    await db.commit()
    
    return response

@router.post("/{project_id}/styles/import-defaults", response_model=List[EpoxyStyleResponse])
async def import_project_defaults(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Import/Copy system default styles into this project.
    This allows the project to start with a full set of styles that override the defaults.
    """
    # Verify project
    project = await db.get(Project, project_id)
    if not project:
         raise HTTPException(status_code=404, detail="Project not found")

    # Fetch System Styles
    query = select(EpoxyStyle).where(
        EpoxyStyle.is_system == True
    ).options(selectinload(EpoxyStyle.cover_image))
    
    result = await db.execute(query)
    system_styles = result.scalars().all()
    
    if not system_styles:
        return []

    new_styles = []
    for sys_style in system_styles:
        # Check if already exists (optional, but good to avoid dupes on multi-click)
        # For now, simplistic: just create. Duplicate names allowed.
        
        new_style = EpoxyStyle(
            project_id=project_id,
            name=sys_style.name, # Keep same name
            category=sys_style.category,
            is_system=False,
            cover_image_id=sys_style.cover_image_id,
            texture_maps=sys_style.texture_maps,
            parameters=sys_style.parameters
        )
        db.add(new_style)
        new_styles.append(new_style)
    
    await db.commit()
    
    # Refresh all to get IDs and relationships
    for ns in new_styles:
        await db.refresh(ns)
        # We need to reload cover_image for response map if we want to be correct, 
        # though refresh might not load relation.
        # Efficient way: return list using _map_to_response but we need to ensure loaded.
        # Let's just do a fresh query for the response.
    
    # Return all project styles to update UI efficiently? Or just the new ones?
    # Schema says List[EpoxyStyleResponse]. Let's return the new ones.
    
    # Re-query to ensure relationships loaded
    new_ids = [s.id for s in new_styles]
    q = select(EpoxyStyle).where(EpoxyStyle.id.in_(new_ids)).options(selectinload(EpoxyStyle.cover_image))
    res = await db.execute(q)
    fetched = res.scalars().all()

    return [_map_to_response(s) for s in fetched]

