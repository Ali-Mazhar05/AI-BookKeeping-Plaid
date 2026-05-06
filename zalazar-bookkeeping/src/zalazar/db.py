from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from contextlib import asynccontextmanager
import uuid
from .config import settings

# Supabase transaction pooler (port 6543) requires asyncpg with no prepared statements
_raw_url = settings.DATABASE_URL
if _raw_url.startswith("postgresql://"):
    _async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgres://"):
    _async_url = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    _async_url = _raw_url

engine = create_async_engine(
    _async_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        # UUID-based names prevent collisions when pgbouncer recycles backend connections
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4().hex}__",
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def pg_advisory_lock(session: AsyncSession, lock_id: int):
    """Acquires a transaction-scoped PostgreSQL advisory lock."""
    await session.execute(text(f"SELECT pg_advisory_xact_lock({lock_id})"))
    yield
