import asyncio
import os
import sys
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import ApiKey, Project
from app.core.security import hash_api_key

async def verify_key(raw_key):
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verification_log.txt")
    
    def log(msg):
        print(msg)
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    # Clear previous log
    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write("--- Verification log started ---\n")

    async with AsyncSessionLocal() as session:
        hashed = hash_api_key(raw_key)
        log(f"Checking Raw Key: {raw_key}")
        log(f"Hash: {hashed}")
        
        query = (
            select(ApiKey)
            .where(ApiKey.key_hash == hashed)
            .options(selectinload(ApiKey.project).selectinload(Project.domains))
        )
        result = await session.execute(query)
        api_key = result.scalars().first()
        
        if not api_key:
            log("❌ API Key NOT found in database.")
            return
            
        log(f"✅ API Key Found!")
        log(f"Key Name: {api_key.name}")
        log(f"Prefix: {api_key.prefix}")
        log(f"Project ID: {api_key.project.id}")
        log(f"Project Name: {api_key.project.name}")
        
        domains = [d.domain for d in api_key.project.domains]
        log(f"Allowed Domains: {domains}")
        
        if not domains:
            log("⚠️ Project has NO allowed domains. Public requests might be blocked depending on strictness.")
        
        # Test Validation URL
        import urllib.request
        import json
        import urllib.error
        
        # Try with the first domain, or localhost if empty
        test_origin = f"https://{domains[0]}" if domains else "http://localhost:3000"
        
        log(f"\n--- simulating request with Origin: {test_origin} ---")
        
        url = "http://localhost:8000/api/v1/public/validate"
        req = urllib.request.Request(url, headers={
            "X-API-KEY": raw_key,
            "Origin": test_origin
        })
        
        try:
            with urllib.request.urlopen(req) as response:
                log(f"Response: {response.getcode()}")
                log(str(json.load(response)))
        except urllib.error.HTTPError as e:
            log(f"❌ Validation Failed: {e.code} - {e.reason}")
            log(e.read().decode())
        except Exception as e:
            log(f"❌ Error during request: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_key_details.py <raw_key>")
        sys.exit(1)
    
    key = sys.argv[1]
    asyncio.run(verify_key(key))
