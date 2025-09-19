from fastapi import FastAPI, Depends
from pathlib import Path
import os
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
import aio_pika

from app.shared.db import get_async_session, ping_database
from .controller.image_controller import router as image_router

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(Path(__file__).resolve().parents[1] / "storage")))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
title="image_testing_task",
    description="API тествого сервиса по обработке изображений",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

app.include_router(image_router)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_async_session)) -> dict:
    db_ok = await ping_database(session)

    # Check RabbitMQ availability with a short timeout
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    rabbit_ok = False
    try:
        conn = await asyncio.wait_for(aio_pika.connect_robust(rabbitmq_url), timeout=2.0)
        await conn.close()
        rabbit_ok = True
    except Exception:
        rabbit_ok = False

    overall = "ok" if (db_ok and rabbit_ok) else ("degraded" if (db_ok or rabbit_ok) else "error")
    return {
        "status": overall,
        "checks": {
            "database": "ok" if db_ok else "error",
            "rabbitmq": "ok" if rabbit_ok else "error",
        },
    }
