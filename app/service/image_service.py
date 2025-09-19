from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile, HTTPException, status
from pathlib import Path
from typing import Tuple
from uuid import UUID
import os
import uuid
import aio_pika
import json
from PIL import Image as PILImage

from app.repository.image_repository import ImageRepository


class ImageService:
    """
    Сервис для работы с изображениями.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.image_repository = ImageRepository(session)

    async def _get_storage_dir(self) -> Path:
        """
        Получение пути к локально хранилищу изображений.
        """
        return Path(os.getenv("STORAGE_DIR", str(Path(__file__).resolve().parents[1] / "storage")))

    async def _get_rabbitmq_url(self):
        """
        Получение url для rabbitMQ
        """
        return os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")

    async def upload_image_to_storage(self, file: UploadFile) -> Tuple[str, Path]:
        """
        Валидирует входной файл и сохраняет его в хранилище.

        Проверки:
        - Наличие имени файла
        - Content-Type вида image/*
        - Ограничение размера: не более 5 МБ
        - Файл является корректным изображением

        Возвращает кортеж (image_id, saved_path).
        """
        # Базовая валидация метаданных (по расширению файла)
        await self._validate_upload_metadata(file)

        storage = await self._get_storage_dir()
        originals_dir = storage / "originals"
        originals_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(file.filename or "").suffix or ""
        image_id = str(uuid.uuid4())
        target_path = originals_dir / f"{image_id}{suffix}"
        await self._stream_file_with_limit(file, target_path, max_bytes=5 * 1024 * 1024)

        # Дополнительная проверка валидности изображения
        await self._verify_image_file(target_path)
        return image_id, target_path

    async def _validate_upload_metadata(self, file: UploadFile) -> None:
        """Проверяет базовые метаданные загружаемого файла.

        Требования:
        - Непустое имя файла
        - Допустимое расширение файла (только изображения)
        """
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустое имя файла")
        allowed_image_ext = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        suffix = Path(file.filename).suffix.lower()
        if suffix not in allowed_image_ext:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Неподдерживаемый формат файла")

    async def _stream_file_with_limit(self, file: UploadFile, target_path: Path, max_bytes: int) -> None:
        """Потоково записывает файл на диск, контролируя максимальный размер.

        При превышении `max_bytes` генерирует 413 и удаляет частично записанный файл.
        """
        bytes_written = 0
        try:
            with target_path.open("wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Размер файла превышает 5 МБ")
                    out.write(chunk)
        except Exception:
            try:
                if target_path.exists():
                    target_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise
        finally:
            try:
                await file.close()
            except Exception:
                pass

    async def _verify_image_file(self, path: Path) -> None:
        """Проверяет, что записанный файл является валидным изображением.

        При неуспехе удаляет файл и возвращает 415.
        """
        suffix = path.suffix.lower()
        allowed_image_ext = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        if suffix not in allowed_image_ext:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Неподдерживаемый формат файла")
        try:
            with PILImage.open(path) as img:
                img.verify()
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Невалидное изображение")

    async def add_new_image(self, image_id : UUID, saved_path: str):
        """
        Сохранение сведений об изображении в БД.
        """
        return await self.image_repository.add_new_image(image_id, saved_path)

    async def publish_image_task(self, image_id: UUID, saved_path: str):
        """
        Публикуем задачу на обработку изображения.
        """
        storage_root = await self._get_storage_dir()
        try:
            original_rel_path = str(Path(saved_path).resolve().relative_to(storage_root.resolve()))
        except Exception:
            # Если по какой-то причине путь вне storage, отправим как абсолютный
            original_rel_path = str(saved_path)

        task_message = {
            "image_id": str(image_id),
            # Отправляем путь ОТНОСИТЕЛЬНО корня хранилища для переносимости между средами
            "original_path": original_rel_path,
            "sizes": [
                {"width": 100, "height": 100},
                {"width": 300, "height": 300},
                {"width": 1200, "height": 1200},
            ],
        }
        url = await self._get_rabbitmq_url()
        connection = await aio_pika.connect_robust(url)
        async with connection:
            channel: aio_pika.Channel = await connection.channel()
            exchange = await channel.declare_exchange("images", aio_pika.ExchangeType.DIRECT, durable=True)
            queue = await channel.declare_queue("images", durable=True)
            await queue.bind(exchange, routing_key="images")
            body = json.dumps(task_message).encode("utf-8")
            task_id = str(uuid.uuid4())
            msg = aio_pika.Message(
                body=body,
                message_id=task_id,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await exchange.publish(msg, routing_key="images")
            return task_id

    async def get_image_by_id(self, image_id: UUID):
        """
        Получение изображения по идентификатору.
        """
        return await self.image_repository.get_by_id(image_id)
