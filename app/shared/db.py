import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text


def _get_database_url() -> str:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        try:
            load_dotenv(env_path)
        except Exception:
            pass
    default_url = "postgresql+asyncpg://app:app@localhost:5432/app"
    if os.getenv("RUNNING_IN_DOCKER") == "1":
        default_url = "postgresql+asyncpg://app:app@db:5432/app"
    return os.getenv("DATABASE_URL", default_url)


engine = create_async_engine(_get_database_url(), future=True, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def ping_database(session: AsyncSession) -> bool:
    try:
        result = await session.execute(text("SELECT 1"))
        return result.scalar() == 1
    except Exception:
        return False


async def get_async_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
