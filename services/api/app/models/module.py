from sqlalchemy import String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from ..db.base import Base

class Module(Base):
    __tablename__ = "modules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(String)
    default_config: Mapped[dict] = mapped_column(JSON, default={})

class ProjectModule(Base):
    __tablename__ = "project_modules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default={})

    project = relationship("Project", back_populates="modules")
    module = relationship("Module")
