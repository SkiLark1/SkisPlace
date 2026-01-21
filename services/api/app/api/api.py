from fastapi import APIRouter
from app.api.endpoints import auth, clients, projects, modules, public, assets, styles, epoxy

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(modules.router, prefix="/modules", tags=["modules"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(styles.router, prefix="/styles", tags=["styles"])
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(epoxy.router, prefix="/epoxy", tags=["epoxy"])

