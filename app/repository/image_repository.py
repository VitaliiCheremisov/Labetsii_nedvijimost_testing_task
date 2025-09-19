from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select
from uuid import UUID

from app.models.models import Image, ImageStatus


class ImageRepository:
    """
    Репозиторий для CRUD операций модели Image.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_new_image(self, image_id: UUID, saved_path: str):
        """
        Запись сведений об изображении в БД.
        """
        stmt = insert(Image).values(
            id=image_id,
            status=ImageStatus.NEW,
            original_url=str(saved_path),
            thumbnails=None,
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_by_id(self, image_id: UUID):
        """
        Получение изображения по ID.
        """
        query = select(Image).where(Image.id == image_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
