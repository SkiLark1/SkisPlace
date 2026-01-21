from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.module import Module

DEFAULT_MODULES = [
    {
        "name": "Epoxy Visualizer",
        "description": "Upload a room photo and preview epoxy finishes",
        "default_config": {"theme": "light", "maxRendersPerDay": 50},
    },
    {
        "name": "Hello Widget",
        "description": "A simple hello world widget for testing",
        "default_config": {},
    },
    {
        "name": "Lead Capture",
        "description": "Capture leads from your website",
        "default_config": {"email_notifications": True},
    }
]

async def init_db(db: AsyncSession) -> None:
    """
    Seed database with default modules if they don't exist.
    """
    for module_data in DEFAULT_MODULES:
        query = select(Module).where(Module.name == module_data["name"])
        result = await db.execute(query)
        existing_module = result.scalar_one_or_none()

        if not existing_module:
            new_module = Module(**module_data)
            db.add(new_module)
            print(f"Seeding module: {module_data['name']}")
    
    await db.commit()
