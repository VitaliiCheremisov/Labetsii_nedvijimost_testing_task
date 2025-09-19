import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from alembic import context


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = None


def get_url() -> str:
    # Load .env if present locally to support running outside Docker
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        try:
            load_dotenv(env_path)
        except Exception:
            pass

    # Prefer explicit DATABASE_URL; default to localhost for local runs
    default_url = "postgresql+asyncpg://app:app@localhost:5432/app"
    # But if running in container, DB host is 'db'
    if os.getenv("RUNNING_IN_DOCKER") == "1":
        default_url = "postgresql+asyncpg://app:app@db:5432/app"

    return os.getenv("DATABASE_URL", default_url)


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())


