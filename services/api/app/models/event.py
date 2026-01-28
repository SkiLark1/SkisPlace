import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modules.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String)
    properties: Mapped[dict] = mapped_column(JSON, default={})
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    project = relationship("Project", back_populates="events")
    module = relationship("Module")


class ErrorEvent(Base):
    __tablename__ = "error_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    error_code: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    stack_trace: Mapped[str] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default={})
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    project = relationship("Project", back_populates="errors")
