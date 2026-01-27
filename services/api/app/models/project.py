import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String)
    config: Mapped[dict] = mapped_column(JSON, default={})
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="projects")
    domains = relationship("ProjectDomain", back_populates="project")
    api_keys = relationship("ApiKey", back_populates="project")
    modules = relationship("ProjectModule", back_populates="project")
    assets = relationship("Asset", back_populates="project")
    events = relationship("UsageEvent", back_populates="project")
    errors = relationship("ErrorEvent", back_populates="project")

class ProjectDomain(Base):
    __tablename__ = "project_domains"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    domain: Mapped[str] = mapped_column(String, unique=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    project = relationship("Project", back_populates="domains")

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    key_hash: Mapped[str] = mapped_column(String, index=True)
    prefix: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    scopes: Mapped[list] = mapped_column(JSON, default=[])
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    project = relationship("Project", back_populates="api_keys")
