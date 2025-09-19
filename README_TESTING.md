# Testing Guide

This project includes comprehensive testing using pytest with unit and integration tests.

## Test Structure

```
tests/
├── __init__.py
├── unit/                          # Unit tests
│   ├── __init__.py
│   ├── test_image_controller.py   # Controller tests
│   ├── test_image_service.py      # Service tests
│   └── test_image_repository.py   # Repository tests
├── integration/                   # Integration tests
│   ├── __init__.py
│   └── test_image_workflow.py     # End-to-end workflow tests
└── fixtures/                      # Test fixtures and utilities
    ├── __init__.py
    └── conftest.py               # Pytest fixtures
```

## Dependencies

The following testing dependencies are included in `requirements.txt`:

- `pytest==8.2.2` - Testing framework
- `pytest-asyncio==0.23.8` - Async testing support
- `pytest-mock==3.12.0` - Mocking utilities
- `httpx==0.27.0` - HTTP client for testing
- `pytest-cov==5.0.0` - Coverage reporting

## Running Tests

### Quick Start

Use the provided test runner script:

```bash
python run_tests.py
```

This will:
1. Install dependencies
2. Run unit tests
3. Run integration tests
4. Generate coverage report

### Manual Testing

#### Run all tests:
```bash
pytest
```

#### Run specific test categories:
```bash
# Unit tests only
pytest tests/unit/

# Specific test file
pytest tests/unit/test_image_controller.py
```

#### Run with coverage:
```bash
pytest --cov=app --cov-report=html --cov-report=term
```

#### Run with verbose output:
```bash
pytest -v
```

#### Run specific test:
```bash
pytest tests/unit/test_image_controller.py::TestImageController::test_upload_image_success -v
```

## Test Configuration

The project uses `pytest.ini` for configuration:

- **Test paths**: `tests/`
- **Coverage threshold**: 80%
- **Async mode**: Auto
- **Markers**: `unit`, `integration`, `slow`

## Test Coverage

The tests cover:

### Unit Tests
- **Controller**: API endpoint testing, error handling, response validation
- **Service**: Business logic, file validation, image processing
- **Repository**: Database operations, CRUD functionality

### Integration Tests
- **Workflow**: Complete image upload and processing pipeline
- **Storage**: File system operations and directory structure
- **Error Handling**: End-to-end error scenarios

## Test Fixtures

Key fixtures available in `conftest.py`:

- `client`: FastAPI test client
- `test_db_session`: In-memory database session
- `temp_storage_dir`: Temporary storage directory
- `sample_image_data`: Test image bytes
- `mock_image`: Mock image object
- `mock_processed_image`: Mock processed image with thumbnails

## Writing New Tests

### Unit Test Example:
```python
@pytest.mark.asyncio
async def test_my_function_success(self, image_service):
    """Test successful function execution."""
    result = await image_service.my_function()
    assert result is not None
```

### Integration Test Example:
```python
@pytest.mark.asyncio
async def test_complete_workflow(self, client, sample_image_data):
    """Test complete workflow."""
    response = client.post("/v1/images/upload_image", 
                          files={"file": ("test.jpg", sample_image_data, "image/jpeg")})
    assert response.status_code == 200
```

## Mocking

The tests use extensive mocking for:
- Database operations
- File system operations
- RabbitMQ connections
- External services

## Continuous Integration

The test suite is designed to run in CI/CD pipelines:
- No external dependencies required
- In-memory database for testing
- Temporary file system operations
- Comprehensive error handling

## Coverage Reports

Coverage reports are generated in HTML format in the `htmlcov/` directory:
- Open `htmlcov/index.html` in a browser
- View line-by-line coverage
- Identify untested code paths

## Troubleshooting

### Common Issues:

1. **Import errors**: Ensure all dependencies are installed
2. **Database errors**: Tests use in-memory SQLite, no setup required
3. **File permission errors**: Tests use temporary directories
4. **Async test failures**: Ensure `@pytest.mark.asyncio` decorator is used

### Debug Mode:
```bash
pytest --pdb  # Drop into debugger on failure
pytest -s     # Don't capture output
pytest -vv    # Extra verbose output
```
python