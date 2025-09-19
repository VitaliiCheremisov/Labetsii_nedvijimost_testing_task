## FastAPI + PostgreSQL (Docker Compose)

### Что внутри
- FastAPI приложение (`app/main.py`) с эндпоинтами:
   `GET /health`
   `POST /v1/image/upload_image`
   `GET /v1/image/{image_id}`
- Асинхронный SQLAlchemy + asyncpg (`app/db.py`)
- Dockerfile для приложения и docker-compose с отдельным контейнером PostgreSQL

### Запуск
1. Создайте `.env` из примера:
   ```bash
   cp env.example .env
   ```
2. Соберите и запустите:
   ```bash
   docker compose up --build
   ```
3. Откройте:
   - API: `http://localhost:8000`
   - Документация: `http://localhost:8000/docs`
   - Healthcheck: `http://localhost:8000/health`
   - Отправка изображения: `http://localhost:8000/v1/image/upload_image`
   - Поиск изображения: `http://localhost:8000/v1/image/{image_id}`

### Полезные команды
- Остановить и удалить контейнеры/сеть (с сохранением данных в volume):
  ```bash
  docker compose down
  ```
- Полностью очистить volume БД:
  ```bash
  docker compose down -v
  ```
