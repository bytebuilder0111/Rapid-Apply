from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# statement_cache_size=0: disables asyncpg's client-side prepared-statement cache.
# Required for providers like Neon whose default connection string goes through a
# PgBouncer-style pooler in transaction mode — the cache otherwise holds onto stale
# type OIDs (e.g. our `role` enum) across pooled connections and DDL changes,
# surfacing as "cache lookup failed for type ..." errors.
engine = create_async_engine(
    settings.database_url, echo=False, connect_args={"statement_cache_size": 0}
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
