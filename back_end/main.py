from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__, "SERVER")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations are run explicitly, never at startup.
    logger.info("Application startup")
    yield
    #await engine.dispose()
    logger.info("Application shutdown")

app = FastAPI(
    title="DB Assist",
    version="1.0.0",
    description="An AI-powered database assistant that converts natural language questions into SQL queries, executes them against databases, and delivers accurate, context-aware results in a human-readable format. Built using LLMs, LangChain, and FastAPI to simplify database interactions and enable efficient data retrieval without requiring SQL expertise.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health", tags=["operations"])
async def health():
    return {"status": "ok"}

# from sqlalchemy import text
# from app.db.session import engine
# @app.get("/ready", tags=["operations"])
# async def readiness():
#     try:
#         async with engine.connect() as connection:
#             await connection.execute(text("SELECT 1"))
#     except Exception:
#         raise HTTPException(status_code=503, detail="Database is not ready")
#     return {"status": "ready", "database": "ok"}