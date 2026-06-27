"""
app/database.py
---------------
Async SQLAlchemy database engine, session factory, and Base declarative model.
Uses aiosqlite driver for non-blocking I/O compatible with FastAPI's async handlers.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Create async engine – echo=True only in non-production for SQL debugging
engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug and not settings.is_production,
    future=True,
)

# Session factory – expire_on_commit=False avoids lazy-load errors after commit
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


async def init_db() -> None:
    """
    Create all tables on application startup.
    In production, replace with Alembic migrations.
    """
    async with engine.begin() as conn:
        # Import models so they register on Base.metadata
        from app.models import task, user  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async DB session per request.
    Automatically closes the session after the request completes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
