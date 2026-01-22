from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.module import Module
from app.models.epoxy_style import EpoxyStyle

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

DEFAULT_STYLES = [
    {
        "name": "Metallic Silver",
        "category": "Metallic",
        "parameters": {"color": "#C0C0C0", "roughness": 0.2, "metallic": 0.9},
        "is_system": True
    },
    {
        "name": "Deep Ocean",
        "category": "Metallic",
        "parameters": {"color": "#003366", "roughness": 0.3, "metallic": 0.8},
        "is_system": True
    },
    {
        "name": "Midnight Black",
        "category": "Solid",
        "parameters": {"color": "#111111", "roughness": 0.1, "metallic": 0.5},
        "is_system": True
    }
]

async def init_db(db: AsyncSession) -> None:
    """
    Seed database with default modules if they don't exist.
    """
    # 1. Modules
    for module_data in DEFAULT_MODULES:
        query = select(Module).where(Module.name == module_data["name"])
        result = await db.execute(query)
        existing_module = result.scalar_one_or_none()

        if not existing_module:
            new_module = Module(**module_data)
            db.add(new_module)
            print(f"Seeding module: {module_data['name']}")
            
    # 2. Styles
    for style_data in DEFAULT_STYLES:
        # Check if system style with this name exists
        query = select(EpoxyStyle).where(
            EpoxyStyle.name == style_data["name"],
            EpoxyStyle.is_system == True
        )
        result = await db.execute(query)
        existing_style = result.scalar_one_or_none()
        
        if not existing_style:
            new_style = EpoxyStyle(**style_data)
            # project_id is None by default
            db.add(new_style)
            print(f"Seeding system style: {style_data['name']}")
    
    await db.commit()
