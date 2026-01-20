import asyncio
import os
import sys
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import ApiKey, Project

async def list_keys():
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "list_keys_log.txt")
    
    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write("--- API Keys List ---\n")

    async with AsyncSessionLocal() as session:
        query = select(ApiKey).options(selectinload(ApiKey.project))
        result = await session.execute(query)
        keys = result.scalars().all()
        
        with open(log_file_path, "a", encoding="utf-8") as f:
            if not keys:
                f.write("No API keys found in the database.\n")
            for k in keys:
                f.write(f"ID: {k.id} | Name: {k.name} | Prefix: {k.prefix} | Hash: {k.key_hash} | Project: {k.project.name if k.project else 'None'}\n")

if __name__ == "__main__":
    asyncio.run(list_keys())
