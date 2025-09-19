"""
Unit tests for image repository.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import uuid
from types import SimpleNamespace
from app.repository.image_repository import ImageRepository
from app.models.models import Image, ImageStatus


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


class TestImageRepository:
    """Test cases for image repository."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def image_repository(self, mock_session):
        """Create image repository instance."""
        return ImageRepository(mock_session)

    @pytest.mark.asyncio
    async def test_add_new_image_success(self, image_repository, mock_session):
        """Test successful addition of new image."""
        image_id = uuid4()
        saved_path = "/test/path/image.jpg"
        
        # Mock the insert statement execution
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_session.commit.return_value = None
        
        await image_repository.add_new_image(image_id, saved_path)
        
        # Verify that execute and commit were called
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # Verify the insert statement was created with correct values
        call_args = mock_session.execute.call_args[0][0]
        assert hasattr(call_args, 'table')  # This is an insert statement
        assert call_args.table.name == 'images'

    @pytest.mark.asyncio
    async def test_add_new_image_database_error(self, image_repository, mock_session):
        """Test addition of new image with database error."""
        image_id = uuid4()
        saved_path = "/test/path/image.jpg"
        
        # Mock database error
        from sqlalchemy.exc import SQLAlchemyError
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        
        with pytest.raises(SQLAlchemyError):
            await image_repository.add_new_image(image_id, saved_path)

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, image_repository, mock_session, mock_processed_image):
        """Test successful image retrieval by ID."""
        image_id = mock_processed_image.id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_processed_image
        mock_session.execute.return_value = mock_result
        
        result = await image_repository.get_by_id(image_id)
        
        assert result == mock_processed_image
        mock_session.execute.assert_called_once()
        
        # Verify the select statement was created
        call_args = mock_session.execute.call_args[0][0]
        assert hasattr(call_args, 'columns')  # This is a select statement

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, image_repository, mock_session):
        """Test image retrieval when image not found."""
        image_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await image_repository.get_by_id(image_id)
        
        assert result is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_database_error(self, image_repository, mock_session):
        """Test image retrieval with database error."""
        image_id = uuid4()
        
        # Mock database error
        from sqlalchemy.exc import SQLAlchemyError
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        
        with pytest.raises(SQLAlchemyError):
            await image_repository.get_by_id(image_id)

    @pytest.mark.asyncio
    async def test_repository_initialization(self, mock_session):
        """Test repository initialization."""
        repository = ImageRepository(mock_session)
        
        assert repository.session == mock_session
        assert hasattr(repository, 'add_new_image')
        assert hasattr(repository, 'get_by_id')

    @pytest.mark.asyncio
    async def test_add_new_image_with_different_image_id_types(self, image_repository, mock_session):
        """Test adding image with different ID types."""
        # Test with string UUID
        image_id_str = str(uuid4())
        saved_path = "/test/path/image.jpg"
        
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_session.commit.return_value = None
        
        await image_repository.add_new_image(image_id_str, saved_path)
        
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_new_image_with_empty_path(self, image_repository, mock_session):
        """Test adding image with empty path."""
        image_id = uuid4()
        saved_path = ""
        
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_session.commit.return_value = None
        
        await image_repository.add_new_image(image_id, saved_path)
        
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_with_invalid_uuid(self, image_repository, mock_session):
        """Test getting image with invalid UUID format."""
        # This should be handled by the database layer, but we test the repository behavior
        invalid_id = "not-a-uuid"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await image_repository.get_by_id(invalid_id)
        
        assert result is None
        mock_session.execute.assert_called_once()
