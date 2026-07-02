# Канаста Online

Классическая карточная игра «Канаста» на четверых — по ссылке, без регистрации. FastAPI + WebSocket на бэкенде, React на фронтенде, состояние партии живёт в Redis, история — в Postgres. Полное описание требований и архитектуры — в [plan.md](plan.md).

## Стек

- **Backend:** Python 3.12, FastAPI, WebSocket, SQLAlchemy + Alembic, Redis
- **Frontend:** React + TypeScript, Vite, Zustand, Framer Motion
- **Инфраструктура:** Docker Compose (Postgres, Redis, backend, frontend)

## Разработка

Поднимает весь стек с hot-reload на backend и frontend:

```bash
docker compose up
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000 (`/health` для проверки)

Тесты:

```bash
cd backend && uv run pytest
cd frontend && pnpm test
```

## Продакшен

Отдельный compose-файл с production-образами (multi-stage сборка, без bind-mount'ов и hot-reload; backend — слим-образ на uvicorn, frontend — статика через nginx).

1. Скопируйте `.env.example` в `.env` и заполните реальными значениями (пароль БД, `SECRET_KEY`, `CORS_ORIGINS` и `VITE_API_BASE_URL` — оба должны указывать на публичный адрес, на котором будет открываться сайт):

   ```bash
   cp .env.example .env
   ```

2. Соберите и запустите:

   ```bash
   docker compose -f docker-compose.prod.yml up --build -d
   ```

   При старте backend-контейнер сам применяет миграции (`alembic upgrade head`) перед запуском сервера.

3. Приложение доступно на порту 80 (frontend, nginx) и 8000 (backend API/WS).

`VITE_API_BASE_URL` вшивается в статическую сборку фронтенда на этапе `docker build`, поэтому при смене адреса backend нужно пересобрать фронтенд-образ (`docker compose -f docker-compose.prod.yml build frontend`).

Реальный TLS/домен/reverse-proxy перед nginx в этот compose не входит — добавляется отдельно под конкретный хостинг.

> Dev- и prod-compose используют одинаковые имена сервисов (`backend`, `frontend`) и потому одинаковые теги образов. Если гоняете оба файла на одной машине, после переключения между ними пересобирайте образы явно (`docker compose up --build`), иначе Docker может переиспользовать образ, собранный другим compose-файлом.
