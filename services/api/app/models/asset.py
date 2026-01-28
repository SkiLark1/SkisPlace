import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    type: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    meta: Mapped[dict] = mapped_column(JSON, default={})

    project = relationship("Project", back_populates="assets")
