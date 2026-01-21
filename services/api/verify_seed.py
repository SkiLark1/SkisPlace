import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.module import Module

async def verify():
    print("--- START VERIFICATION ---")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Module))
        modules = result.scalars().all()
        print(f"Total Modules Found: {len(modules)}")
        for m in modules:
            print(f"MODULE: {m.name}")
    print("--- END VERIFICATION ---")

if __name__ == "__main__":
    asyncio.run(verify())
