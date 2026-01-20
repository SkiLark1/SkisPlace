from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class ClientBase(BaseModel):
    name: str
    slug: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None

class ClientResponse(ClientBase):
    id: UUID
    slug: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
