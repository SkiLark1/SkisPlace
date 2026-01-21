from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, List, Dict, Any

# --- System Modules ---

class ModuleBase(BaseModel):
    name: str
    description: str
    default_config: Dict[str, Any] = {}

class ModuleResponse(ModuleBase):
    id: UUID4
    created_at: datetime

    class Config:
        from_attributes = True

# --- Project Modules ---

class ProjectModuleBase(BaseModel):
    config: Dict[str, Any] = {}
    enabled: bool = True

class ProjectModuleCreate(BaseModel):
    module_id: UUID4
    config: Optional[Dict[str, Any]] = {}

class ProjectModuleUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None

class ProjectModuleResponse(ProjectModuleBase):
    id: UUID4
    project_id: UUID4
    module_id: UUID4
    module: ModuleResponse # Nested full module details

    class Config:
        from_attributes = True
