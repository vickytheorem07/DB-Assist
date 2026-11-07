from fastapi import APIRouter

from app.api.v1.endpoints import load_docs

api_router = APIRouter()
api_router.include_router(load_docs.router, tags=["load_doc"])
# api_router.include_router(interact_agent.router, prefix="/interact_agent", tags=["interact_agent"])
# api_router.include_router(history.router, prefix="/history", tags=["history"])
