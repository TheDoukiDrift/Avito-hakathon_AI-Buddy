# AI-buddy — короткие команды для повседневной работы.
# Рецепты — табы, не пробелы.

.PHONY: up down logs test seed lint build ps restart

## Поднять весь стек (сборка образов)
up:
	docker compose up --build -d

## Остановить и убрать контейнеры
down:
	docker compose down

## Логи всех сервисов (Ctrl+C для выхода)
logs:
	docker compose logs -f --tail=100

## Покрытие: бэкенд pytest + фронтенд vitest (порог 80% в CI)
test:
	docker compose exec backend pytest --cov=app --cov-report=html --cov-report=xml
	docker compose exec frontend npx vitest run --coverage

## Пересоздать синтетические данные (сиды)
seed:
	docker compose exec backend python -m app.seeds

## Линтеры (подключим, когда появятся конфиги ruff/eslint)
lint:
	@echo "lint: ruff / eslint подключаются вместе с кодом"

## Пересобрать образы без запуска
build:
	docker compose build

## Состояние сервисов
ps:
	docker compose ps

## Перезапустить один сервис: make restart S=backend
restart:
	docker compose restart $(S)
