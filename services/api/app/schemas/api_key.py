from pydantic import BaseModel, UUID4
from typing import Optional, List
from datetime import datetime

class ApiKeyBase(BaseModel):
    name: str
    scopes: List[str] = []

class ApiKeyCreate(ApiKeyBase):
    pass

class ApiKeyResponse(ApiKeyBase):
    id: UUID4
    project_id: UUID4
    prefix: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ApiKeySecret(ApiKeyResponse):
    key: str # This is the full key, shown ONLY once upon creation.
