import asyncio
import os
import sys

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import EpoxyStyle
from sqlalchemy.future import select

async def update_categories():
    async with AsyncSessionLocal() as session:
        print("Updating style categories...")
        
        # 1. Update Metallic Marble -> Metallic
        result = await session.execute(select(EpoxyStyle).where(EpoxyStyle.name == "Metallic Marble"))
        s1 = result.scalar_one_or_none()
        if s1:
            s1.category = "Metallic"
            print("Updated Metallic Marble to Metallic")
            
        # 2. Update Midnight Sparkle -> Flake
        result = await session.execute(select(EpoxyStyle).where(EpoxyStyle.name == "Midnight Sparkle"))
        s2 = result.scalar_one_or_none()
        if s2:
            s2.category = "Flake"
            print("Updated Midnight Sparkle to Flake")
            
        # 3. Update Industrial Grey -> Quartz (Renaming concept to fit Quartz system)
        result = await session.execute(select(EpoxyStyle).where(EpoxyStyle.name == "Industrial Grey"))
        s3 = result.scalar_one_or_none()
        if s3:
            s3.category = "Quartz"
            print("Updated Industrial Grey to Quartz")
            
        await session.commit()
        print("Category update complete.")

if __name__ == "__main__":
    asyncio.run(update_categories())
