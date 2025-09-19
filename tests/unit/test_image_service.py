"""
Unit tests for image service.
"""
import pytest
import shutil
import uuid
import json
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
from uuid import uuid4
import tempfile
from fastapi import UploadFile, HTTPException

from app.service.image_service import ImageService
from app.models.models import ImageStatus


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


class TestImageService:
    """Test cases for image service."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def image_service(self, mock_session):
        """Create image service instance."""
        return ImageService(mock_session)

    @pytest.mark.asyncio
    async def test_upload_image_to_storage_success(self, image_service, temp_storage_dir, sample_image_data):
        """Test successful image upload to storage."""
        # Create mock upload file
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.read = AsyncMock(side_effect=[sample_image_data, b""])  # First call returns data, second returns empty
        
        with patch('app.service.image_service.PILImage') as mock_pil:
            mock_img = MagicMock()
            mock_img.verify.return_value = None
            mock_pil.open.return_value.__enter__.return_value = mock_img
            
            image_id, saved_path = await image_service.upload_image_to_storage(mock_file)
            
            assert image_id is not None
            assert isinstance(saved_path, Path)
            assert saved_path.exists()
            assert saved_path.suffix == ".jpg"

    @pytest.mark.asyncio
    async def test_upload_image_to_storage_invalid_filename(self, image_service):
        """Test upload with invalid filename."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = None
        
        with pytest.raises(HTTPException) as exc_info:
            await image_service.upload_image_to_storage(mock_file)
        
        assert exc_info.value.status_code == 400
        assert "Пустое имя файла" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_upload_image_to_storage_invalid_extension(self, image_service):
        """Test upload with invalid file extension."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.txt"
        
        with pytest.raises(HTTPException) as exc_info:
            await image_service.upload_image_to_storage(mock_file)
        
        assert exc_info.value.status_code == 415
        assert "Неподдерживаемый формат файла" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_upload_image_to_storage_file_too_large(self, image_service, temp_storage_dir):
        """Test upload with file too large."""
        # Create large file data (6MB)
        large_data = b"x" * (6 * 1024 * 1024)
        
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.read = AsyncMock(side_effect=[large_data[:1024*1024], large_data[1024*1024:], b""])
        
        with pytest.raises(HTTPException) as exc_info:
            await image_service.upload_image_to_storage(mock_file)
        
        assert exc_info.value.status_code == 413
        assert "Размер файла превышает 5 МБ" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_upload_image_to_storage_invalid_image(self, image_service, temp_storage_dir, sample_image_data):
        """Test upload with invalid image file."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.read = AsyncMock(side_effect=[sample_image_data, b""])
        
        with patch('app.service.image_service.PILImage') as mock_pil:
            mock_pil.open.side_effect = Exception("Invalid image")
            
            with pytest.raises(HTTPException) as exc_info:
                await image_service.upload_image_to_storage(mock_file)
            
            assert exc_info.value.status_code == 415
            assert "Невалидное изображение" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_add_new_image_success(self, image_service, mocker):
        """Test successful addition of new image to database."""
        image_id = uuid4()
        saved_path = "/test/path/image.jpg"

        mock_add = mocker.patch.object(
            image_service.image_repository,
            "add_new_image",
            new_callable=AsyncMock
        )

        await image_service.add_new_image(image_id, saved_path)

        mock_add.assert_called_once_with(image_id, saved_path)

    @pytest.mark.asyncio
    async def test_publish_image_task_success(self, image_service, mocker):
        """Test that publish_image_task correctly calls exchange.publish."""
        # Мокаем зависимости
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()

        mock_connection = AsyncMock()
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_exchange.return_value = mock_exchange

        # Мокаем connect_robust
        mock_connect = mocker.patch("aio_pika.connect_robust", return_value=mock_connection)

        # Данные
        image_id = uuid.uuid4()
        saved_path = "/dummy/path/image.jpg"

        # Выполняем тестируемый метод
        await image_service.publish_image_task(image_id, saved_path)

        # Проверяем: подключение установлено
        mock_connect.assert_called_once()

        # Проверяем: declare_exchange вызван с правильными аргументами
        mock_channel.declare_exchange.assert_called_once_with(
            "images",
            "direct",
            durable=True
        )

        # Проверяем: publish вызван
        mock_exchange.publish.assert_called_once()

        # Проверяем сообщение
        call_args = mock_exchange.publish.call_args
        message = call_args.args[0]
        routing_key = call_args.kwargs["routing_key"]

        assert routing_key == "images"

        body = json.loads(message.body)
        assert body["image_id"] == str(image_id)

    @pytest.mark.asyncio
    async def test_get_image_by_id_success(self, image_service, mocker):
        """Test successful image retrieval by ID."""
        # Создаём мок-изображение
        mock_image = mocker.MagicMock()
        mock_image.id = uuid.uuid4()

        # Мокаем метод get_by_id как AsyncMock
        mock_get_by_id = mocker.patch.object(
            image_service.image_repository,
            "get_by_id",
            return_value=mock_image
        )

        # Выполняем
        result = await image_service.get_image_by_id(mock_image.id)

        # Проверяем
        assert result == mock_image
        mock_get_by_id.assert_called_once_with(mock_image.id)

    @pytest.mark.asyncio
    async def test_get_image_by_id_not_found(self, image_service, mocker):
        """Test image retrieval when image not found."""
        image_id = uuid.uuid4()  # ← не забудь импортировать: from uuid import uuid4

        # Заменяем get_by_id на AsyncMock, который возвращает None
        image_service.image_repository.get_by_id = mocker.AsyncMock(return_value=None)

        # Выполняем
        result = await image_service.get_image_by_id(image_id)

        # Проверяем
        assert result is None
        image_service.image_repository.get_by_id.assert_called_once_with(image_id)

    @pytest.mark.asyncio
    async def test_validate_upload_metadata_success(self, image_service):
        """Test successful metadata validation."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.jpg"
        
        # Should not raise exception
        await image_service._validate_upload_metadata(mock_file)

    @pytest.mark.asyncio
    async def test_validate_upload_metadata_empty_filename(self, image_service):
        """Test metadata validation with empty filename."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = ""
        
        with pytest.raises(HTTPException) as exc_info:
            await image_service._validate_upload_metadata(mock_file)
        
        assert exc_info.value.status_code == 400
        assert "Пустое имя файла" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_upload_metadata_none_filename(self, image_service):
        """Test metadata validation with None filename."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = None
        
        with pytest.raises(HTTPException) as exc_info:
            await image_service._validate_upload_metadata(mock_file)
        
        assert exc_info.value.status_code == 400
        assert "Пустое имя файла" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_upload_metadata_invalid_extension(self, image_service):
        """Test metadata validation with invalid extension."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.txt"
        
        with pytest.raises(HTTPException) as exc_info:
            await image_service._validate_upload_metadata(mock_file)
        
        assert exc_info.value.status_code == 415
        assert "Неподдерживаемый формат файла" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_image_file_success(self, image_service, temp_storage_dir, sample_image_data):
        """Test successful image file verification."""
        test_file = temp_storage_dir / "test.jpg"
        test_file.write_bytes(sample_image_data)
        
        with patch('app.service.image_service.PILImage') as mock_pil:
            mock_img = MagicMock()
            mock_img.verify.return_value = None
            mock_pil.open.return_value.__enter__.return_value = mock_img
            
            # Should not raise exception
            await image_service._verify_image_file(test_file)

    @pytest.mark.asyncio
    async def test_verify_image_file_invalid_extension(self, image_service, temp_storage_dir):
        """Test image file verification with invalid extension."""
        test_file = temp_storage_dir / "test.txt"
        test_file.write_text("not an image")
        
        with pytest.raises(HTTPException) as exc_info:
            await image_service._verify_image_file(test_file)
        
        assert exc_info.value.status_code == 415
        assert "Неподдерживаемый формат файла" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_image_file_invalid_image(self, image_service, temp_storage_dir):
        """Test image file verification with invalid image."""
        test_file = temp_storage_dir / "test.jpg"
        test_file.write_text("not an image")
        
        with patch('app.service.image_service.PILImage') as mock_pil:
            mock_pil.open.side_effect = Exception("Invalid image")
            
            with pytest.raises(HTTPException) as exc_info:
                await image_service._verify_image_file(test_file)
            
            assert exc_info.value.status_code == 415
            assert "Невалидное изображение" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_stream_file_with_limit_success(self, image_service, temp_storage_dir):
        """Test successful file streaming with limit."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.read = AsyncMock(side_effect=[b"chunk1", b"chunk2", b""])
        
        target_path = temp_storage_dir / "test.jpg"
        
        await image_service._stream_file_with_limit(mock_file, target_path, max_bytes=1024)
        
        assert target_path.exists()
        assert target_path.read_bytes() == b"chunk1chunk2"

    @pytest.mark.asyncio
    async def test_stream_file_with_limit_exceeded(self, image_service, temp_storage_dir):
        """Test file streaming with size limit exceeded."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.read = AsyncMock(side_effect=[b"x" * 1024, b"y" * 1024, b""])
        
        target_path = temp_storage_dir / "test.jpg"
        
        with pytest.raises(HTTPException) as exc_info:
            await image_service._stream_file_with_limit(mock_file, target_path, max_bytes=1024)
        
        assert exc_info.value.status_code == 413
        assert "Размер файла превышает 5 МБ" in exc_info.value.detail
        # File should be cleaned up
        assert not target_path.exists()
