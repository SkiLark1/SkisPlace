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
            {
                "name": "Epoxy Visualizer", 
                "description": "Upload a room photo and preview epoxy finishes",
                "default_config": {
                    "theme": "light", 
                    "maxRendersPerDay": 50,
                    "ai_segmentation": {
                        "enabled": True,
                        "provider": "local_segmentation",
                        "auto_mask": True
                    }
                }
            },
            {
                "name": "Hello Widget",
                "description": "A simple hello world widget for testing",
                "default_config": {}
            },
            {
                "name": "Lead Capture",
                "description": "Capture leads from your website",
                "default_config": {"email_notifications": True},
            }
        ]
        
        for mod_data in modules:
            result = await session.execute(select(Module).where(Module.name == mod_data["name"]))
            if not result.scalar_one_or_none():
                print(f"Creating module: {mod_data['name']}")
                session.add(Module(**mod_data))

        await session.commit()
        
        # Seed Epoxy Styles
        from app.models import EpoxyStyle
        
        styles = [
            {
                "name": "Metallic Marble", 
                "category": "Metallic", 
                "is_system": True,
                "parameters": {"color": "#C0C0C0"},
                "texture_maps": {},
                "cover_image_id": None 
            },
            {
                "name": "Midnight Sparkle", 
                "category": "Flake", 
                "is_system": True,
                "parameters": {"density": "high"},
                "texture_maps": {},
                "cover_image_id": None
            },
             {
                "name": "Industrial Grey", 
                "category": "Quartz", 
                "is_system": True,
                "parameters": {"finish": "matte"},
                "texture_maps": {},
                "cover_image_id": None
            }
        ]
        
        for style_data in styles:
             result = await session.execute(select(EpoxyStyle).where(EpoxyStyle.name == style_data["name"]))
             if not result.scalar_one_or_none():
                 print(f"Creating style: {style_data['name']}")
                 session.add(EpoxyStyle(**style_data))

        await session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_data())
