from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.module import Module
from app.models.user import User
from app.schemas.module import ModuleResponse

router = APIRouter()

@router.get("/", response_model=List[ModuleResponse])
async def read_modules(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve system modules.
    """
    query = select(Module).order_by(Module.name).offset(skip).limit(limit)
    result = await db.execute(query)
    modules = result.scalars().all()
    return modules
