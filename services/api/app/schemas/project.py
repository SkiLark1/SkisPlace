from pydantic import BaseModel, UUID4
from typing import Optional, List
from datetime import datetime

# Domain Schemas
class ProjectDomainBase(BaseModel):
    domain: str

class ProjectDomainCreate(ProjectDomainBase):
    pass

class ProjectDomainResponse(ProjectDomainBase):
    id: UUID4
    project_id: UUID4
    verified: bool

    class Config:
        from_attributes = True

# Project Schemas
class ProjectBase(BaseModel):
    name: str
    slug: Optional[str] = None
    config: Optional[dict] = {}

class ProjectCreate(ProjectBase):
    client_id: UUID4

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    config: Optional[dict] = None

class ProjectResponse(ProjectBase):
    id: UUID4
    client_id: UUID4
    created_at: datetime
    updated_at: datetime
    domains: List[ProjectDomainResponse] = []

    class Config:
        from_attributes = True
