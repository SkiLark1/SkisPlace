from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.config import settings
from app.core import security
from app.models.user import User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = payload.get("sub")
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    result = await db.execute(select(User).where(User.id == token_data))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "superuser":
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user

# --- Public API Deps ---

from fastapi import Header, Request
from app.models.project import ApiKey, Project, ProjectDomain
from app.core.security import hash_api_key
from sqlalchemy.orm import selectinload

async def get_project_from_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """
    Validate API Key and return associated project.
    Accepts either a raw API Key hash (standard) or a signed Preview Token (JWT).
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-KEY header")

    # Check for Preview Token (JWT)
    if "." in x_api_key:
        try:
            payload = jwt.decode(
                x_api_key, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            # Verify usage format
            if payload.get("type") != "preview":
                raise HTTPException(status_code=401, detail="Invalid token type")
            
            project_id = payload.get("sub")
            if not project_id:
                raise HTTPException(status_code=401, detail="Invalid token payload")

            # Fetch Project
            result = await db.execute(select(Project).where(Project.id == project_id).options(selectinload(Project.domains)))
            project = result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=401, detail="Project not found from token")
                
            return project

        except (JWTError, ValidationError):
            # Fallthrough to hash check? No, if it looks like JWT but fails, it's invalid.
            # But technically a raw key *could* have a dot (unlikely with our format).
            # Our keys are sk_live_... no dots.
            raise HTTPException(status_code=401, detail="Invalid Preview Token")

    # Standard API Key Hash Check
    hashed = hash_api_key(x_api_key)
    
    # Query Key + Project + Domains
    query = (
        select(ApiKey)
        .where(ApiKey.key_hash == hashed)
        .options(
            selectinload(ApiKey.project).selectinload(Project.domains),
            selectinload(ApiKey.project).selectinload(Project.modules)
        )
    )
    result = await db.execute(query)
    key_obj = result.scalars().first()

    if not key_obj:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    return key_obj.project

async def verify_public_origin(
    request: Request,
    project: Project = Depends(get_project_from_api_key),
) -> Project:
    """
    Verify request Origin against Project Allowed Domains.
    """
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    
    # If no domains configured, maybe allow all? Or block all? 
    # For security, if domains ARE configured, we must match.
    # If NO domains configured, we might be in "dev mode" or "setup mode".
    # Let's be strict: If domains exist, origin MUST match.
    # If no domains exist, allow (for local dev convenience) or block?
    # Better: If list is empty, BLOCK (unless it's localhost?). 
    # Actually, for this stage, let's implement:
    # - If allowed_domains is empty -> Allow (open mode)
    # - If allowed_domains is set -> Origin MUST match one of them.
    
    allowed_domains = [d.domain for d in project.domains if d.verified] # Only verified? Or all? Let's say all for now as we don't have verification flow yet.
    # actually let's use all domains for now.
    allowed_domains = [d.domain for d in project.domains]

    if not allowed_domains:
        return project # Open mode

    # Check Origin
    if origin:
        # origin usually "https://example.com"
        # simplistic check
        domain_match = any(d in origin for d in allowed_domains)
        if not domain_match:
             raise HTTPException(status_code=403, detail=f"Origin {origin} not allowed")
        return project

    # Check Referer if Origin missing (sometime happens)
    if referer:
        domain_match = any(d in referer for d in allowed_domains)
        if not domain_match:
             raise HTTPException(status_code=403, detail=f"Referer {referer} not allowed")
        return project

    # If neither, and domains strictly required...
    # For now, if header missing but domains required -> Block
    raise HTTPException(status_code=403, detail="Missing Origin/Referer header")

