
import asyncio
import os
import sys
from uuid import uuid4

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import User, Client, Project, ApiKey
from app.core.security import get_password_hash, generate_api_key, hash_api_key
from sqlalchemy import select

async def seed_full():
    print("--- Seeding Database ---")
    async with AsyncSessionLocal() as session:
        # 1. Create User
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalars().first()
        if not user:
            user = User(
                email="admin@example.com",
                password_hash=get_password_hash("password"),
                full_name="Admin User",
                role="superuser"
            )
            session.add(user)
            print("✅ User created: admin@example.com / password (Superuser)")
        else:
            if user.role != "superuser":
                print("ℹ️ Upgrading existing user to superuser...")
                user.role = "superuser"
                session.add(user)
            print("ℹ️ User already exists")

        # 2. Create Client
        result = await session.execute(select(Client).where(Client.name == "Test Client"))
        client = result.scalars().first()
        if not client:
            client = Client(name="Test Client", slug="test-client")
            session.add(client)
            await session.flush() # get ID
            print(f"✅ Client created: {client.name}")
        else:
            print("ℹ️ Client already exists")

        # 3. Create Project
        if client:
            result = await session.execute(select(Project).where(Project.client_id == client.id))
            project = result.scalars().first()
            if not project:
                project = Project(
                    name="Test Project",
                    slug=f"test-project-{uuid4()}",
                    client_id=client.id,
                    config={"theme": "dark"}
                )
                session.add(project)
                await session.flush()
                print(f"✅ Project created: {project.name}")
            else:
                print(f"ℹ️ Project already exists: {project.id}")
            
            # 4. Create API Key
            if project:
                # Check if random key exists? No just make one.
                # Actually, duplicate keys are fine, but let's see if we have one.
                result = await session.execute(select(ApiKey).where(ApiKey.project_id == project.id))
                existing_key = result.scalars().first()
                if existing_key:
                    print("ℹ️ Deleting existing key to generate a fresh one...")
                    await session.delete(existing_key)
                    await session.flush()

                key_secret = generate_api_key()
                key_hash = hash_api_key(key_secret)
                new_key = ApiKey(
                    name="Dev Key",
                    prefix=key_secret[:10],
                    key_hash=key_hash,
                    project_id=project.id
                )
                session.add(new_key)
                
                creds = f"""
✅ API Key created!
   Secret: {key_secret}
   Project ID: {project.id}
   User: admin@example.com / password
"""
                print(creds)
                with open("seed_credentials.txt", "w") as f:
                    f.write(creds)

        await session.commit()
        print("--- Seed Complete ---")

if __name__ == "__main__":
    asyncio.run(seed_full())
