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
    return project

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

@router.patch("/{project_id}/modules/{module_id}", response_model=ProjectModuleResponse)
async def update_project_module(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    module_id: UUID, # This is the PROJECT_MODULE id, or the SYSTEM_MODULE id?
                     # Ideally it should be the ID of the resource we are manipulating in URL.
                     # But frontend might trigger by "Enable Module X". 
                     # Let us assume this is the SYSTEM MODULE ID for convenience if the user wants "Toggle Module X".
                     # Actually, standard REST: /resources/{id}. If resource is "project_module", id is pm.id.
                     # However, keeping it simple: let use module_id refer to SYSTEM MODULE ID for semantic clarity "Toggle SeoMonitor".
    module_update: ProjectModuleUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update project module config or status using System Module ID.
    """
    query = select(ProjectModule).where(
        ProjectModule.project_id == project_id,
        ProjectModule.module_id == module_id
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

@router.delete("/{project_id}/modules/{module_id}", response_model=ProjectModuleResponse)
async def disable_project_module(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_id: UUID,
    module_id: UUID, # System Module ID
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Disable (remove) a module from a project.
    """
    query = select(ProjectModule).where(
        ProjectModule.project_id == project_id,
        ProjectModule.module_id == module_id
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

