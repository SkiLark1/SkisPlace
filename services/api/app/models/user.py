from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column
import uuid
import enum
from datetime import datetime
from ..db.base import Base

class UserRole(str, enum.Enum):
    SUPERUSER = "superuser"
    ADMIN = "admin"
    USER = "user"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
