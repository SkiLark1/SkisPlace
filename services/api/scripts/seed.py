import asyncio
import os
import sys

# Add parent dir to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import User, UserRole, Project, Client, Module
from app.core.security import get_password_hash
from sqlalchemy.future import select

async def seed_data():
    async with AsyncSessionLocal() as session:
        print("Seeding data...")
        
        # Check if admin exists
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            print("Creating admin user...")
            admin = User(
                email="admin@example.com",
                password_hash=get_password_hash("admin"),
                full_name="Admin User",
                role=UserRole.SUPERUSER
            )
            session.add(admin)
        
        # Check if client exists
        result = await session.execute(select(Client).where(Client.slug == "default-client"))
        client = result.scalar_one_or_none()
        
        if not client:
            print("Creating default client...")
            client = Client(name="Default Client", slug="default-client")
            session.add(client)
            await session.flush() # verify ID

            print("Creating sample project...")
            project = Project(
                client_id=client.id,
                name="Sample Project",
                slug="sample-project",
                config={"env": "dev"}
            )
            session.add(project)
            
        # Seed Modules
        modules = [
            {"name": "seo-monitor", "description": "SEO Monitoring"},
            {"name": "uptime", "description": "Uptime Monitoring"},
            {"name": "analytics", "description": "Usage Analytics"},
        ]
        
        for mod_data in modules:
            result = await session.execute(select(Module).where(Module.name == mod_data["name"]))
            if not result.scalar_one_or_none():
                print(f"Creating module: {mod_data['name']}")
                session.add(Module(**mod_data))

        await session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_data())
