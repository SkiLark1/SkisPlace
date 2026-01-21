from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.api import api_router

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

from fastapi.staticfiles import StaticFiles
import os
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory="static/uploads"), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "service": "api"}

@app.on_event("startup")
async def startup_event():
    from app.db.session import AsyncSessionLocal
    from app.db.init_db import init_db
    
    async with AsyncSessionLocal() as db:
        await init_db(db)

@app.get("/")
def root():
    return {"message": "API is running"}
