from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from typing import Optional, Dict


class ImageUploadResponseSchema(BaseModel):
    image_id: UUID = Field(..., description="Уникальный идентификатор изображения")
    task_id: UUID = Field(..., description="Уникальный идентификатор задачи")
    status: str = Field(..., description="Статус задачи")

    model_config = ConfigDict(from_attributes=True)


class ImageResponseModel(BaseModel):
    id: UUID = Field(..., description="Уникальный идентификатор изображения")
    status: str = Field(..., description="Статус обработки изображения")
    original_url: str = Field(..., description="Путь к оригиналу изображения")
    thumbnails: Optional[Dict[str, str]] = Field(None, description="Карта миниатюр: размер → путь")

    model_config = ConfigDict(from_attributes=True)
