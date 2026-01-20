from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.api import deps
import uuid

router = APIRouter()

@router.get("/", response_model=List[ClientResponse])
async def read_clients(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Retrieve clients.
    """
    result = await db.execute(select(Client).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/", response_model=ClientResponse)
async def create_client(
    *,
    db: AsyncSession = Depends(get_db),
    client_in: ClientCreate,
    current_user = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Create new client.
    """
    # Check for existing slug
    if client_in.slug:
        result = await db.execute(select(Client).where(Client.slug == client_in.slug))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Slug already exists")
    else:
        # Generate slug from name (simple version)
        import re
        client_in.slug = re.sub(r'[^a-zA-Z0-9]+', '-', client_in.name.lower()).strip('-')

    client = Client(
        name=client_in.name,
        slug=client_in.slug
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client

@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    *,
    db: AsyncSession = Depends(get_db),
    client_id: uuid.UUID,
    client_in: ClientUpdate,
    current_user = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Update a client.
    """
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    update_data = client_in.dict(exclude_unset=True)
    if "slug" in update_data and update_data["slug"] != client.slug:
        # Check slug uniqueness check if changing
        result = await db.execute(select(Client).where(Client.slug == update_data["slug"]))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Slug already exists")

    for field, value in update_data.items():
        setattr(client, field, value)

    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client
