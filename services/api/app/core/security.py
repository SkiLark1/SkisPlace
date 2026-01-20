from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import jwt
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --- API Key Helpers ---
import hashlib
import secrets

def generate_api_key(prefix: str = "sk_live_") -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    return hash_api_key(plain_key) == hashed_key
