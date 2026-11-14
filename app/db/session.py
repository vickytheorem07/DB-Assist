from collections.abc import AsyncGenerator
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Convert postgresql:// → postgresql+psycopg:// for the async psycopg driver.
_async_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+psycopg://", 1
).replace(
    "postgresql+psycopg2://", "postgresql+psycopg://", 1
)

engine = create_async_engine(
    _async_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _start_query_timer(conn, cursor, statement, parameters, context, executemany):
    if context is not None:
        context._query_started_at = time.perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _log_query(conn, cursor, statement, parameters, context, executemany):
    started_at = getattr(context, "_query_started_at", None) if context is not None else None
    if started_at is None:
        return
    duration_ms = (time.perf_counter() - started_at) * 1000
    operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "SQL"
    logger.info("Database query completed: operation=%s duration_ms=%.2f", operation, duration_ms)


@event.listens_for(engine.sync_engine, "handle_error")
def _log_query_error(exception_context):
    statement = exception_context.statement or ""
    operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "SQL"
    error = exception_context.original_exception
    logger.error("Database query failed: operation=%s error=%s", operation, type(error).__name__)


