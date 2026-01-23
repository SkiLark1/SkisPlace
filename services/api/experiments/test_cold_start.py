
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient
from uuid import uuid4
from main import app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import Project, User, ApiKey
from sqlalchemy import select

# Mock dependency
async def override_get_db():
    async with AsyncSessionLocal() as db:
        yield db

app.dependency_overrides = {} 
# We don't override DB here because we need real DB behavior for the test
# But we might need to create a dummy user/project/key first.

@pytest.mark.asyncio
async def test_cold_start_preview_no_project_id():
    """
    Test that calling /preview with ONLY an API Key (no project_id in body)
    1. Resolves the project from key
    2. Ensures the Epoxy Module exists (Cold Start)
    3. Runs the preview logic (which might fail on file not found, but we check logs/mock)
    """
    # 1. Setup Data
    async with AsyncSessionLocal() as db:
        # Create Project
        proj_id = uuid4()
        proj = Project(id=proj_id, name=f"Test Project {proj_id}", slug=f"test-{proj_id}")
        db.add(proj)
        
        # Create API Key
        key_val = f"sk_test_{uuid4()}"
        api_key = ApiKey(key=key_val, project_id=proj_id, name="Test Key", is_active=True)
        db.add(api_key)
        
        await db.commit()
    
    # 2. Call Endpoint (No project_id form, just key)
    headers = {"X-API-KEY": key_val}
    
    # We need a valid style_id to get past the first check? 
    # The endpoint checks style_id early.
    # We can rely on 404 Style Not Found, but check logs if "Ensured module config" printed?
    # Or cleaner: create a style too.
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Just send a dummy style_id.
        # This will error with 400 or 404, but IF the cold start fix works,
        # it should have executed `_ensure_epoxy_module` BEFORE the style check?
        # NO, lookup at code:
        # 1. Fallback project_id resolution happens first.
        # 2. _ensure_epoxy_module happens immediately after.
        # 3. THEN style fetch.
        
        # So even if we get 400 Invalid Style, the module should exist in DB.
        
        dummy_style = str(uuid4())
        # image_id also required
        dummy_image = "test_img"
        
        data = {
            "image_id": dummy_image,
            "style_id": dummy_style,
            # NO project_id
        }
        
        response = await ac.post("/api/v1/epoxy/preview", headers=headers, data=data)
        
        # We expect 400 or 404 (Style/Image not found), NOT 500.
        print(f"Response: {response.status_code}")
        
        # 3. Verify Module Created in DB
        async with AsyncSessionLocal() as db:
            from app.models import ProjectModule, Module
            stmt = select(ProjectModule).join(Module).where(ProjectModule.project_id == proj_id, Module.name == "Epoxy Visualizer")
            res = await db.execute(stmt)
            pm = res.scalar_one_or_none()
            
            if pm:
                print("PASS: ProjectModule created automatically via Cold Start")
            else:
                print("FAIL: ProjectModule NOT created")
                assert pm is not None

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_cold_start_preview_no_project_id())
    except Exception as e:
        print(f"Test Failed: {e}")
