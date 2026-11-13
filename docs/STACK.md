# Стек проекта

Одна страница: что и в какой версии реально стоит в репозитории. Версии
зафиксированы в `backend/requirements.txt`, `frontend/package.json`,
`docker-compose.yml` и Dockerfile'ах — таблицы ниже повторяют их, а не
предполагают «примерно такие».

## Backend

| Компонент | Версия | Зачем в проекте |
|---|---|---|
| Python | 3.12 (`python:3.12-slim`) | Язык бэкенда; кейс разрешает любой стек (Q&A), Python выбран ради скорости |
| FastAPI | 0.162.4 | HTTP API с автогенерацией OpenAPI — контракт для фронта и для имитаций |
| Uvicorn[standard] | 0.54.0 | ASGI-сервер, SSE-стриминг ответов чата |
| SQLAlchemy[asyncio] | 2.1.8 | ORM и асинхронные сессии; один код на SQLite и PostgreSQL |
| greenlet | 3.5.6 | Мост sync→async, нужен SQLAlchemy async |
| Alembic | 1.20.1 | Миграции, включая `0004` (напоминания + `started_at`) |
| Pydantic | 2.14.3 | Схемы запросов/ответов, валидация контрактов |
| pydantic-settings | 2.16.2 | Конфигурация из env (12-factor) |
| psycopg[binary] | 3.3.8 | Драйвер PostgreSQL 16 |
| httpx | 0.28.1 | HTTP-клиент (тесты, MCP-клиент) |
| redis | 8.1.0 | Клиент Redis: сессии, rate-limit, кэш ретрива |
| MCP (FastMCP) | 1.30.0 | Отдельный процесс инструментов — единственный канал агента к сервисам |

**LLM.** Один код на два режима: OpenAI-совместимый API через `LLM_BASE_URL` /
`LLM_API_KEY` / `LLM_MODEL` (по умолчанию модель `gpt-4o-mini`, в `.env.example`
и CI — `qwen2.5-72b-instruct`) и оффлайн `FakeLLM` — детерминированная
keyword-заглушка, которая работает без ключа и без сети. `docker compose up`
поднимается на `FakeLLM`; ключ подставляется экспертом.

**Имитации.** Сервисы отсутствий и чек-листа — FastAPI-роутеры с OpenAPI;
агент не ходит в БД напрямую, только через MCP-инструменты (7 штук:
`absence_create`, `absence_status`, `absence_list`, `checklist_get`,
`checklist_complete`, `contacts_lookup`, `contacts_route`).

## Frontend

| Компонент | Версия | Зачем в проекте |
|---|---|---|
| React | 18.3.1 | UI чата и панелей (чек-лист, напоминания, заявки) |
| React DOM | 18.3.1 | Рендер |
| TypeScript | 5.6.2 | Типы, `tsc --noEmit` в сборке и CI |
| Vite | 5.4.8 | Дев-сервер и сборка |
| @vitejs/plugin-react | 4.3.1 | React-плагин Vite (Fast Refresh) |
| Zustand | 4.5.5 | Локальное состояние чата и панелей |
| TanStack Query | 5.56.2 | Запросы к API, кэш, инвалидация после действий |
| Zod | 3.23.8 | Валидация ответов API на границе — контракт ловится в рантайме |
| react-markdown + remark-gfm | 10.1.0 / 4.0.1 | Markdown в ответах ассистента (таблицы, списки) |
| pnpm | 12.18.0 | Пакетный менеджер, версия зафиксирована в `packageManager` |
| Node | 20 (`node:20-alpine`) | Сборка образа |

**Дизайн.** Фирменный `hoshi-style` v2 — «Nord Brutal Grid (Stone-Warm)»:
тёмная палитра Nord с тёплым камнем, моноширинная типографика как несущая
конструкция, жёсткая модульная сетка, нулевые скругления/тени/блюры и
документальные аннотации (номера секций, статусы). Это осознанный уход от
дефолтного вида UI-китов: жюри видит систему, а не шаблон.

## Данные и инфраструктура

| Компонент | Версия / образ | Зачем в проекте |
|---|---|---|
| PostgreSQL | `pgvector/pgvector:pg16` | Пользователи, роли, диалоги, чек-лист, заявки, напоминания, аудит; образ готов под pgvector, если заменим BM25 на эмбеддинги |
| Redis | `redis:7-alpine` | Сессии, rate-limit, кэш ретрива |
| nginx | `nginx:1.27-alpine` | Раздача собранного фронта, прокси на API |
| Docker Compose | `docker-compose.yml` | Один `docker compose up` поднимает postgres, redis, backend, mcp, frontend |
| MCP-сервер | `python -m mcp_server`, streamable-http :8001 | Отдельный процесс, порт не публикуется наружу |
| Alembic | `alembic upgrade head` в `entrypoint.sh` | Схема БД создаётся при старте, сиды идемпотентны |

Фоновые задачи: имитация ИИ-крона (`app/services/reminder_cron.py`) живёт в
процессе API (FastAPI lifespan), тикает раз в `REMINDER_INTERVAL_SEC` (300 с) и
может быть запущена разово — `python -m app.services.reminder_cron`.

## Качество

| Инструмент | Версия | Что проверяет |
|---|---|---|
| pytest | 9.2.0 | 135 тестов бэкенда |
| pytest-asyncio | 1.4.1.post1 | Асинхронные тесты (`asyncio_mode=auto`) |
| pytest-cov | 7.1.0 | Покрытие `app` + `mcp_server`, порог `--cov-fail-under=80` (факт — 92%) |
| aiosqlite | 0.22.1 | Тестовая БД без внешнего сервиса |
| ruff | 0.17.4 | Линт (E, F, I, UP, B) и формат, line-length 100 |
| Vitest | 2.1.1 | Тесты фронта (store/utils/api) |
| @vitest/coverage-v8 | 2.1.1 | Покрытие фронта, отчёт в CI |
| jsdom + Testing Library | 25.0.0 / 16.0.1 | DOM-тесты компонентов |
| GitHub Actions | `.github/workflows/ci.yml` | Два job'а: backend (ruff + pytest + coverage ≥80%) и frontend (vitest coverage + build), отчёты — артефактами |

## Стек Авито из кейса ↔ наш стек

| Из кейса / ожидание жюри | У нас |
|---|---|
| Frontend: React + TypeScript, Zustand, TanStack Query, Zod | Без изменений — тот же стек и те же версии-мажоры |
| Backend на Go (не обязателен: «пишите на чём удобно») | Python 3.12 + FastAPI; кейс и Q&A разрешают любой язык явно |
| PostgreSQL как основное хранилище | PostgreSQL 16 (`pgvector/pgvector:pg16`), та же СУБД, плюс готовность к pgvector |
| Redis для сессий, лимитов и кэша | Redis 7-alpine, те же сценарии |
| REST/OpenAPI-контракты корпоративных сервисов | FastAPI-имитации с OpenAPI; замена на реальный сервис — смена base URL |
| Инструменты через MCP | Собственный MCP-сервер (FastMCP), 7 инструментов, RBAC на уровне инструмента |
| Дизайн-система Авито | `hoshi-style` (Nord Brutal Grid) — своя система, а не дефолтный UI-кит |
| Внешний LLM API | OpenAI-совместимый клиент через env + оффлайн `FakeLLM` по умолчанию |
