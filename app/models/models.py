import enum
import uuid

from sqlalchemy import (
    Column, DateTime, func, String, JSON, Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class ImageStatus(str, enum.Enum):
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    ERROR = "ERROR"


class Image(Base):
    __tablename__ = "images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(Enum(ImageStatus, name="image_status", create_constraint=True), nullable=False, default=ImageStatus.NEW)
    original_url = Column(String(2048), nullable=False)
    thumbnails = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
