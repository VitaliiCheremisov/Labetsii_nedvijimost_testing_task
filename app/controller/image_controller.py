import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
from aio_pika.exceptions import AMQPError

from app.shared.db import get_async_session
from app.models.models import ImageStatus
from app.service.image_service import ImageService
from app.shemas.image_shemas import ImageUploadResponseSchema, ImageResponseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/images", tags=["Обработка изображений"])

def get_image_service(db: AsyncSession = Depends(get_async_session)) -> ImageService:
    """Зависимость для получения сервиса загрузки изображений."""
    return ImageService(db)


@router.post(
    "/upload_image",
    response_model=ImageUploadResponseSchema,
    summary="Загрузка изображения в проект"
)
async def upload_image(
    file: UploadFile = File(...),
    image_service: ImageService = Depends(get_image_service)
):
    """
    Загружает изображение, создаёт запись в БД и ставит задачу в очередь RabbitMQ.

    Шаги:
    1) Сохраняет оригинал изображения во внутреннем хранилище (`STORAGE_DIR`).
    2) Создаёт запись в таблице `images` со статусом NEW.
    3) Публикует сообщение в обменник `images` (очередь `images`) для последующей
       фоновой обработки воркером (генерация миниатюр и сжатие).

    Возвращает идентификатор изображения, идентификатор задачи и текущий статус.
    """
    try:
        # Загружаем новое изображение в локальное хранилище
        image_id, saved_path = await image_service.upload_image_to_storage(file)
        logger.info(f"Загружено новое изображение {image_id} - {saved_path}.")
        # Сохраняем информацию о новом изображении в БД
        await image_service.add_new_image(image_id, str(saved_path))
        logger.info(f"Сохранено информация о новом изображении.")
        # Публикуем задачу на обработку изображения
        task_id = await image_service.publish_image_task(image_id, str(saved_path))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "image_id": image_id,
                "task_id": task_id,
                "status": ImageStatus.NEW
            }
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.exception(f"Ошибка БД при сохранении информации об изображении: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка базы данных")
    except AMQPError as e:
        logger.exception(f"Ошибка при публикации задачи в RabbitMQ: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Очередь задач недоступна")
    except OSError as e:
        logger.exception(f"Ошибка файловой системы при сохранении изображения: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка файловой системы при сохранении")
    except Exception as e:
        logger.exception(f"Ошибка при загрузке изображения {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ошибка при загрузке изображения {e}"
        )


@router.get(
    "/{image_id}",
    response_model=ImageResponseModel,
    summary="Получение информации по изображению"
)
async def get_image(
    image_id: UUID,
    image_service: ImageService = Depends(get_image_service)
):
    """
    Получение информации об изображении по ID.
    
    Возвращает полную информацию об изображении, включая:
    - Уникальный идентификатор изображения
    - Текущий статус обработки (NEW, PROCESSING, DONE, ERROR)
    - Путь к оригинальному файлу
    - Карту миниатюр (если обработка завершена успешно)
    
    Args:
        image_id (UUID): Уникальный идентификатор изображения
        
    Returns:
        ImageResponseModel: Модель с информацией об изображении
        
    Raises:
        HTTPException: 404 - если изображение не найдено
        HTTPException: 500 - при ошибке базы данных или внутренней ошибке сервера
        
    Example:
        GET /v1/images/550e8400-e29b-41d4-a716-446655440000
        
        Response 200:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "DONE",
            "original_url": "/path/to/original.jpg",
            "thumbnails": {
                "100x100": "/path/to/100x100.jpg",
                "300x300": "/path/to/300x300.jpg",
                "1200x1200": "/path/to/1200x1200.jpg"
            }
        }
    """
    try:
        existing_image = await image_service.get_image_by_id(image_id)
        if not existing_image:
            logger.warning(f"Изображение с id {image_id} не найдено в БД.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Изображения с id {image_id} нет в БД."
            )
        return ImageResponseModel.model_validate(existing_image)       
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.exception(f"Ошибка БД при поиске изображения {image_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка базы данных"
        )
    except Exception as e:
        logger.exception(f"Неожиданная ошибка при поиске изображения {image_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера"
        )
