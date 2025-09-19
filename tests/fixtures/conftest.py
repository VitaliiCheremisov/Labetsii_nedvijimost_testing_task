"""
Pytest fixtures for testing.
"""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.models import Base, Image, ImageStatus
from app.shared.db import get_async_session


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def override_get_db(test_db_session: AsyncSession):
    """Override the database dependency."""
    def _override_get_db():
        yield test_db_session
    
    app.dependency_overrides[get_async_session] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_get_db) -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def temp_storage_dir() -> Generator[Path, None, None]:
    """Create a temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir) / "storage"
        storage_path.mkdir()
        (storage_path / "originals").mkdir()
        (storage_path / "thumbnails").mkdir()
        
        # Set environment variable
        original_storage_dir = os.environ.get("STORAGE_DIR")
        os.environ["STORAGE_DIR"] = str(storage_path)
        
        yield storage_path
        
        # Restore original environment
        if original_storage_dir is not None:
            os.environ["STORAGE_DIR"] = original_storage_dir
        else:
            os.environ.pop("STORAGE_DIR", None)


@pytest.fixture
def sample_image_data() -> bytes:
    """Create sample image data for testing."""
    from PIL import Image as PILImage
    import io
    
    # Create a simple 100x100 red image
    img = PILImage.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    return img_bytes.getvalue()


@pytest.fixture
def sample_image_file(sample_image_data: bytes) -> Generator[bytes, None, None]:
    """Create a sample image file for upload testing."""
    yield sample_image_data


@pytest.fixture
def mock_image() -> Image:
    """Create a mock image object."""
    return Image(
        id=uuid4(),
        status=ImageStatus.NEW,
        original_url="/test/path/image.jpg",
        thumbnails=None
    )


@pytest.fixture
def mock_processed_image() -> Image:
    """Create a mock processed image object."""
    return Image(
        id=uuid4(),
        status=ImageStatus.DONE,
        original_url="/test/path/image.jpg",
        thumbnails={
            "100x100": "/test/path/thumbnails/100x100.jpg",
            "300x300": "/test/path/thumbnails/300x300.jpg",
            "1200x1200": "/test/path/thumbnails/1200x1200.jpg"
        }
    )


@pytest.fixture
def mock_rabbitmq_connection():
    """Mock RabbitMQ connection."""
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_queue = AsyncMock()
    
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_exchange.return_value = mock_exchange
    mock_channel.declare_queue.return_value = mock_queue
    mock_exchange.publish.return_value = None
    
    return mock_connection


@pytest.fixture
def mock_image_service():
    """Mock image service."""
    service = MagicMock()
    service.upload_image_to_storage = AsyncMock()
    service.add_new_image = AsyncMock()
    service.publish_image_task = AsyncMock()
    service.get_image_by_id = AsyncMock()
    return service
