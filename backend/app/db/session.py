from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from ..core.config import settings
from typing import AsyncGenerator

connect_args = {}
if settings.DB_PREPARED_STATEMENT_CACHE_SIZE is not None:
    connect_args["prepared_statement_cache_size"] = settings.DB_PREPARED_STATEMENT_CACHE_SIZE

engine_kwargs = {
    "echo": settings.SQLALCHEMY_ECHO,
    "future": True,
    "pool_pre_ping": settings.DB_POOL_PRE_PING,
}
if connect_args:
    engine_kwargs["connect_args"] = connect_args

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
