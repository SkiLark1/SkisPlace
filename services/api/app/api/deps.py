import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
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
    
    try:
        user_uuid = uuid.UUID(token_data)
    except ValueError:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )
    result = await db.execute(select(User).where(User.id == user_uuid))
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
from sqlalchemy.orm import selectinload

from app.core.security import hash_api_key
from app.models.project import ApiKey, Project


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
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    project: Project = Depends(get_project_from_api_key),
) -> Project:
    """
    Verify request Origin against Project Allowed Domains.
    Preview tokens bypass this check (short-lived, requires dashboard auth).
    """
    # Check if this is a preview token - bypass domain check
    if x_api_key and "." in x_api_key:
        try:
            payload = jwt.decode(
                x_api_key, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            if payload.get("type") == "preview":
                # Preview tokens bypass domain verification
                return project
        except:
            pass  # Fall through to normal domain check
    
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    
    allowed_domains = [d.domain for d in project.domains]

    if not allowed_domains:
        return project # Open mode

    # Check Origin
    if origin:
        domain_match = any(d in origin for d in allowed_domains)
        if not domain_match:
             raise HTTPException(status_code=403, detail=f"Origin {origin} not allowed")
        return project

    # Check Referer if Origin missing
    if referer:
        domain_match = any(d in referer for d in allowed_domains)
        if not domain_match:
             raise HTTPException(status_code=403, detail=f"Referer {referer} not allowed")
        return project

    # If neither, and domains strictly required -> Block
    raise HTTPException(status_code=403, detail="Missing Origin/Referer header")

async def get_current_project_opt(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    db: AsyncSession = Depends(get_db),
) -> Optional[Project]:
    """
    Optional version of get_project_from_api_key.
    Returns Project if key is valid, else None.
    Does NOT raise 401.
    """
    if not x_api_key:
        return None

    try:
        # Re-use logic by calling the other function? 
        # Cannot easily call dependency from dependency without using the Depends mechanism which enforces it.
        # So we copy the logic but safe return.
        
        # Check for Preview Token (JWT)
        if "." in x_api_key:
            try:
                payload = jwt.decode(
                    x_api_key, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
                )
                if payload.get("type") != "preview":
                    return None
                
                project_id = payload.get("sub")
                if not project_id:
                    return None

                result = await db.execute(select(Project).where(Project.id == project_id).options(selectinload(Project.domains)))
                return result.scalar_one_or_none()
            except:
                return None

        # Standard API Key Hash Check
        hashed = hash_api_key(x_api_key)
        
        query = (
            select(ApiKey)
            .where(ApiKey.key_hash == hashed)
            .options(selectinload(ApiKey.project).selectinload(Project.domains))
        )
        result = await db.execute(query)
        key_obj = result.scalars().first()

        if key_obj:
            return key_obj.project
        return None

    except Exception:
        return None

