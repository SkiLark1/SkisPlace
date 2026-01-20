import asyncio
import os
import sys


# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import Project, Client, ProjectDomain, ApiKey
from app.core.security import generate_api_key, hash_api_key
from sqlalchemy.future import select

async def verify_public_api():
    async with AsyncSessionLocal() as session:
        print("Setting up test data...")
        
        # 1. Get Client
        client = (await session.execute(select(Client))).scalars().first()
        if not client:
            print("Error: No client found. Run seed first.")
            return

        # 2. Create Test Project
        project = Project(client_id=client.id, name="Public API Test", slug="public-test", config={})
        session.add(project)
        await session.commit()
        await session.refresh(project)
        
        # 3. Add Domain
        domain = ProjectDomain(project_id=project.id, domain="example.com", verified=True)
        session.add(domain)
        
        # 4. Generate Key
        raw_key = generate_api_key()
        api_key = ApiKey(
            project_id=project.id,
            key_hash=hash_api_key(raw_key),
            prefix=raw_key[:10],
            name="Test Key",
        )
        session.add(api_key)
        await session.commit()
        
        print(f"Project ID: {project.id}")
        print(f"API Key: {raw_key}")
        print(f"Allowed Domain: example.com")
        
        
        # 5. Test Requests (using urllib)
        base_url = "http://localhost:8000/api/v1/public"
        
        import urllib.request
        import json

        def make_request(url, headers):
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req) as response:
                    return response.getcode(), json.load(response)
            except urllib.error.HTTPError as e:
                return e.code, None

        print("\n--- Test 1: Valid Request ---")
        code, resp = make_request(
             f"{base_url}/validate",
             headers={"X-API-KEY": raw_key, "Origin": "https://example.com"}
        )
        print(f"Status: {code}")
        print(f"Response: {resp}")
        assert code == 200
        
        print("\n--- Test 2: Invalid Key ---")
        code, resp = make_request(
             f"{base_url}/validate",
             headers={"X-API-KEY": "sk_invalid_123", "Origin": "https://example.com"}
        )
        print(f"Status: {code}")
        assert code == 401
        
        print("\n--- Test 3: Invalid Origin ---")
        code, resp = make_request(
             f"{base_url}/validate",
             headers={"X-API-KEY": raw_key, "Origin": "https://evil.com"}
        )
        print(f"Status: {code}")
        assert code == 403
            
        # Cleanup
        print("\nCleaning up...")
        await session.delete(api_key)
        await session.delete(domain)
        await session.delete(project)
        await session.commit()
        
        print("\nVERIFICATION SUCCESSFUL")

if __name__ == "__main__":
    asyncio.run(verify_public_api())
