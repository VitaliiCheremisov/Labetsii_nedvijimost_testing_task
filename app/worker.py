"""
Воркер для фоновой обработки изображений.

Функционал:
- Подключается к RabbitMQ и подписывается на очередь задач `images`.
- Для каждой задачи читает путь к оригинальному изображению и список требуемых размеров.
- Создаёт миниатюры (thumbnails) нужных размеров с JPEG-сжатием.
- Сохраняет миниатюры в хранилище и обновляет статус задачи в PostgreSQL:
  NEW → PROCESSING → DONE (или ERROR при ошибке).

Примечание: используется устойчивое подключение к RabbitMQ с ретраями
и ограничение QoS (prefetch_count=1) для контролируемой обработки.
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import aio_pika
from PIL import Image as PILImage
from sqlalchemy import update

from app.models.models import Image, ImageStatus
from app.shared.db import async_session_factory


def _get_storage_dir() -> Path:
    """Возвращает путь к корневой директории хранилища изображений.

    Путь берётся из переменной окружения `STORAGE_DIR`. Если переменная
    не задана, используется локальная директория `app/storage`.
    """
    return Path(os.getenv("STORAGE_DIR", str(Path(__file__).resolve().parents[1] / "storage")))


def _ensure_dirs(target_dir: Path) -> None:
    """Гарантирует существование директории `target_dir`.

    Создаёт все недостающие промежуточные директории (аналог mkdir -p).
    """
    target_dir.mkdir(parents=True, exist_ok=True)


def _resize_and_compress(src: Path, dst: Path, width: int, height: int) -> None:
    """Создаёт миниатюру из файла `src` и сохраняет в `dst` с JPEG-сжатием.

    - Приводит изображение к RGB.
    - Масштабирует с сохранением пропорций так, чтобы поместилось в рамки
      (width x height) используя PIL.Image.thumbnail.
    - Сохраняет как JPEG с качеством 85 и оптимизацией.
    """
    with PILImage.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((width, height))
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, format="JPEG", quality=85, optimize=True)


async def _process_task(payload: Dict[str, Any]) -> None:
    """Обрабатывает одну задачу генерации миниатюр.

    Ожидаемый формат `payload`:
    {
        "image_id": str,                # UUID изображения
        "original_path": str,           # абсолютный путь к оригиналу
        "sizes": [                      # список размеров для миниатюр
            {"width": int, "height": int},
            ...
        ]
    }

    Шаги:
    1) Обновляет статус изображения в БД на PROCESSING.
    2) Генерирует миниатюры для заданных размеров.
    3) Сохраняет карту путей миниатюр и устанавливает статус DONE.
    При исключении статус меняется на ERROR.
    """
    image_id: str = payload["image_id"]
    sizes: List[Dict[str, int]] = payload.get("sizes", [])

    storage_root = _get_storage_dir()
    # Support both absolute and storage-root-relative paths coming from the producer
    original_path_candidate = Path(payload["original_path"])  # could be relative
    if original_path_candidate.is_absolute():
        original_path = original_path_candidate.resolve()
    else:
        original_path = (storage_root / original_path_candidate).resolve()
    thumbnails_dir = storage_root / "thumbnails" / image_id
    _ensure_dirs(thumbnails_dir)

    thumbnails_map: Dict[str, str] = {}

    async with async_session_factory() as session:
        # Mark as PROCESSING
        await session.execute(
            update(Image).where(Image.id == image_id).values(status=ImageStatus.PROCESSING)
        )
        await session.commit()

        try:
            for s in sizes:
                w, h = int(s["width"]), int(s["height"])
                out_file = thumbnails_dir / f"{w}x{h}.jpg"
                _resize_and_compress(original_path, out_file, w, h)
                thumbnails_map[f"{w}x{h}"] = str(out_file)

            # Mark as DONE and store thumbnails map
            await session.execute(
                update(Image).where(Image.id == image_id).values(
                    status=ImageStatus.DONE,
                    thumbnails=thumbnails_map,
                )
            )
            await session.commit()
        except Exception:
            await session.execute(
                update(Image).where(Image.id == image_id).values(status=ImageStatus.ERROR)
            )
            await session.commit()
            raise


async def main() -> None:
    """Точка входа воркера.

    Подключается к RabbitMQ (с ретраями), настраивает канал и обменник/очередь
    `images`, ограничивает префетч до одного сообщения и начинает потребление
    задач. Каждая полученная задача обрабатывается функцией `_process_task`.
    """
    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")

    # Robust connect with retries (exponential backoff)
    max_delay_seconds = 30
    delay_seconds = 1
    connection = None
    while True:
        try:
            connection = await aio_pika.connect_robust(url)
            break
        except Exception:
            await asyncio.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, max_delay_seconds)

    async with connection:
        channel = await connection.channel()
        # Limit unacked messages per consumer
        await channel.set_qos(prefetch_count=1)

        exchange = await channel.declare_exchange("images", aio_pika.ExchangeType.DIRECT, durable=True)
        queue = await channel.declare_queue("images", durable=True)
        await queue.bind(exchange, routing_key="images")

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(requeue=False):
                    payload = json.loads(message.body)
                    await _process_task(payload)


if __name__ == "__main__":
    asyncio.run(main())
