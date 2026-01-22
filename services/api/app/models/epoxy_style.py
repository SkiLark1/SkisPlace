from sqlalchemy import String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from ..db.base import Base

class EpoxyStyle(Base):
    __tablename__ = "epoxy_styles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[str] = mapped_column(String, index=True, default="General")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Cover image (Thumbnail)
    cover_image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id"), nullable=True)
    
    # Texture Maps (albedo, normal, roughness, etc.) - stored as JSON of Asset IDs
    # e.g. { "albedo": "uuid", "normal": "uuid" }
    texture_maps: Mapped[dict] = mapped_column(JSON, default={})
    
    # Shader Parameters (color, roughness scalar, metallic, etc.)
    parameters: Mapped[dict] = mapped_column(JSON, default={})

    # Relationships
    cover_image = relationship("Asset", foreign_keys=[cover_image_id])
    
    # Project Scoping (Null = System Default, Set = Project Specific)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=True)
    project = relationship("Project")
