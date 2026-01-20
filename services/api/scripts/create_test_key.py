import asyncio
import os
import sys
from sqlalchemy.future import select

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import Project, ApiKey
from app.core.security import generate_api_key, hash_api_key

async def create_key():
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "create_key_log.txt")
    
    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write("--- Create Key Log ---\n")

    async with AsyncSessionLocal() as session:
        # Get first project
        result = await session.execute(select(Project))
        project = result.scalars().first()
        
        if not project:
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write("❌ No project found to assign key to.\n")
            return

        # Generate Key
        key_secret = generate_api_key()
        key_hash = hash_api_key(key_secret)
        
        new_key = ApiKey(
            name="Verification Key",
            prefix=key_secret[:10], # Store prefix for UI
            key_hash=key_hash,
            project_id=project.id
        )
        session.add(new_key)
        await session.commit()
        await session.refresh(new_key)
        
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(f"✅ Created Key!\n")
            f.write(f"Project: {project.name}\n")
            f.write(f"Secret: {key_secret}\n")
            f.write(f"Hash: {key_hash}\n")

if __name__ == "__main__":
    asyncio.run(create_key())
