import asyncio
import os
import sys

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import User
from app.core.security import verify_password
from sqlalchemy.future import select

async def verify_login():
    async with AsyncSessionLocal() as session:
        print("Checking admin user...", file=sys.stderr)
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalar_one_or_none()
        
        if not user:
            print("ERROR: User admin@example.com NOT found in database.", file=sys.stderr)
            return

        print(f"User found: {user.email}", file=sys.stderr)
        print(f"Role: {user.role}", file=sys.stderr)
        
        is_valid = verify_password("admin", user.password_hash)
        if is_valid:
            print("VALIDATION_SUCCESS: Password 'admin' is correct.", file=sys.stderr)
        else:
            print("VALIDATION_FAILURE: Password 'admin' is INCORRECT.", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(verify_login())
