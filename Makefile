# AI-buddy — короткие команды для повседневной работы.
# Рецепты — табы, не пробелы.

.PHONY: up down logs test seed lint build ps restart

## Поднять весь стек (сборка образов)
## --force-recreate: nginx резолвит адрес backend один раз при старте. Если
## пересобрать только бэкенд, фронтенд остаётся со старым IP и :3000 отдаёт 502.
up:
	docker compose up --build -d --force-recreate

## Остановить и убрать контейнеры
down:
	docker compose down

## Логи всех сервисов (Ctrl+C для выхода)
logs:
	docker compose logs -f --tail=100

## Покрытие: бэкенд pytest + фронтенд vitest (порог 80% в CI)
test:
	docker compose exec backend pytest --cov=app --cov-report=html --cov-report=xml
	docker compose run --rm --build frontend-test

## Пересоздать синтетические данные (сиды)
seed:
	docker compose exec backend python -m app.seeds

## Линтеры (конфиг ruff — в backend/pyproject.toml)
lint:
	cd backend && ruff check . && ruff format --check .

## Пересобрать образы без запуска
build:
	docker compose build

## Состояние сервисов
ps:
	docker compose ps

## Перезапустить один сервис: make restart S=backend
restart:
	docker compose restart $(S)
