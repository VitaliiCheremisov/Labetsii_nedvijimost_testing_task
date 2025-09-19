"""
Unit tests for image controller.
"""
import pytest
import shutil
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from pathlib import Path
import tempfile
import uuid
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app 
from app.controller.image_controller import get_image_service
from app.models.models import Image, ImageStatus


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_storage_dir():
    """Создаёт временную директорию для хранения файлов и удаляет её после теста."""
    dirpath = Path(tempfile.mkdtemp())
    try:
        yield dirpath
    finally:
        shutil.rmtree(dirpath, ignore_errors=True)


@pytest.fixture
def sample_image_data():
    """Возвращает бинарные данные JPEG-изображения (заглушка)."""
    # Минимальный валидный JPEG-файл (SOI + EOI маркеры)
    return b"\xff\xd8\xff\xee\x00\x0eHelloWorld\xff\xd9"
    

@pytest.fixture
def mock_processed_image():
    """Mock an image with status DONE and thumbnails as a dictionary."""
    image_id = uuid.uuid4()
    base_path = f"/app/storage/thumbnails/{image_id}"

    return SimpleNamespace(
        id=image_id,
        original_url=f"{base_path}/original.jpg",
        status=ImageStatus.DONE,
        thumbnails={
            "100x100": f"{base_path}/100x100.jpg",
            "300x300": f"{base_path}/300x300.jpg",
            "1200x1200": f"{base_path}/1200x1200.jpg"
        }
    )


class TestImageController:
    """Test cases for image controller endpoints."""

    @pytest.mark.asyncio
    async def test_upload_image_success(self, client, temp_storage_dir, sample_image_data):
        """Test successful image upload."""
        with patch('app.controller.image_controller.ImageService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            
            # Mock service methods
            mock_service.upload_image_to_storage.return_value = (str(uuid4()), "/test/path/image.jpg")
            mock_service.add_new_image.return_value = None
            mock_service.publish_image_task.return_value = str(uuid4())
            
            response = client.post(
                "/v1/images/upload_image",
                files={"file": ("test.jpg", sample_image_data, "image/jpeg")}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "image_id" in data
            assert "task_id" in data
            assert data["status"] == ImageStatus.NEW

    @pytest.mark.asyncio
    async def test_upload_image_invalid_file_type(self, client):
        """Test upload with invalid file type."""
        response = client.post(
            "/v1/images/upload_image",
            files={"file": ("test.txt", b"not an image", "text/plain")}
        )
        
        assert response.status_code == 415

    @pytest.mark.asyncio
    async def test_upload_image_empty_filename(self, client):
        """Test upload with empty filename."""
        response = client.post(
            "/v1/images/upload_image",
            files={"file": ("", b"data", "image/jpeg")}
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_image_database_error(self, client, temp_storage_dir, sample_image_data):
        """Test upload with database error."""
        with patch('app.controller.image_controller.ImageService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            
            # Mock service to raise SQLAlchemyError
            from sqlalchemy.exc import SQLAlchemyError
            mock_service.upload_image_to_storage.side_effect = SQLAlchemyError("DB Error")
            
            response = client.post(
                "/v1/images/upload_image",
                files={"file": ("test.jpg", sample_image_data, "image/jpeg")}
            )
            
            assert response.status_code == 500
            assert "Ошибка базы данных" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_image_rabbitmq_error(self, client, temp_storage_dir, sample_image_data):
        """Test upload with RabbitMQ error."""
        with patch('app.controller.image_controller.ImageService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            
            # Mock service methods
            mock_service.upload_image_to_storage.return_value = (str(uuid4()), "/test/path/image.jpg")
            mock_service.add_new_image.return_value = None
            
            # Mock RabbitMQ error
            from aio_pika.exceptions import AMQPError
            mock_service.publish_image_task.side_effect = AMQPError("RabbitMQ Error")
            
            response = client.post(
                "/v1/images/upload_image",
                files={"file": ("test.jpg", sample_image_data, "image/jpeg")}
            )
            
            assert response.status_code == 503
            assert "Очередь задач недоступна" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_image_success(self, client, mock_processed_image):
        """Test successful image retrieval."""
        with patch('app.controller.image_controller.ImageService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.get_image_by_id.return_value = mock_processed_image
            
            image_id = str(mock_processed_image.id)
            response = client.get(f"/v1/images/{image_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == image_id
            assert data["status"] == ImageStatus.DONE
            assert "thumbnails" in data

    @pytest.mark.asyncio
    async def test_get_image_not_found(self, client):
        """Test image retrieval when image not found."""
        with patch('app.controller.image_controller.ImageService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.get_image_by_id.return_value = None
            
            image_id = str(uuid4())
            response = client.get(f"/v1/images/{image_id}")
            
            assert response.status_code == 404
            assert f"Изображения с id {image_id} нет в БД" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_image_database_error(self, client):
        """Test image retrieval with database error."""
        with patch('app.controller.image_controller.ImageService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            
            # Mock database error
            from sqlalchemy.exc import SQLAlchemyError
            mock_service.get_image_by_id.side_effect = SQLAlchemyError("DB Error")
            
            image_id = str(uuid4())
            response = client.get(f"/v1/images/{image_id}")
            
            assert response.status_code == 500
            assert "Ошибка базы данных" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_image_invalid_uuid(self, client):
        """Test image retrieval with invalid UUID."""
        response = client.get("/v1/images/invalid-uuid")
        
        assert response.status_code == 422  # Validation error

    def test_get_image_service_dependency(self):
        """Test image service dependency injection."""
        mock_session = MagicMock()
        service = get_image_service(mock_session)
        
        assert service is not None
        assert hasattr(service, 'upload_image_to_storage')
        assert hasattr(service, 'add_new_image')
        assert hasattr(service, 'publish_image_task')
        assert hasattr(service, 'get_image_by_id')
