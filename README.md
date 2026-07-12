# E-commerce Backend

Backend completo y production-ready de e-commerce construido con **FastAPI**, **PostgreSQL**, **Redis**, **Celery**, **MinIO** y **Stripe**.

## Stack

- Python 3.12 + FastAPI
- SQLAlchemy 2.0 (async) + Alembic
- PostgreSQL 16 + Redis 7
- Celery + Redis (colas y broker)
- Stripe (pagos + webhooks)
- MinIO (S3-compatible, imágenes)
- Docker + Docker Compose
- Nginx (reverse proxy)
- Pytest + factory-boy

## Requisitos

- Docker >= 24
- Docker Compose >= 2
- Python 3.12 (solo para desarrollo local sin Docker)
- Poetry (opcional)

## Inicio rápido

```bash
cp .env.example .env
# Edita .env con tus credenciales (Stripe, SMTP, etc.)
docker compose up --build
```

Servicios disponibles:

| Servicio | URL |
|----------|-----|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

## Variables de entorno

Ver `.env.example` para el listado completo. Las más importantes:

- `DATABASE_URL`: URL de conexión a Postgres (asyncpg)
- `SECRET_KEY`: clave para firmar JWT
- `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`
- `MINIO_*`: configuración de storage

## Migraciones

```bash
docker compose exec api alembic revision --autogenerate -m "descripcion"
docker compose exec api alembic upgrade head
```

## Tests

```bash
docker compose exec api pytest
```

Localmente con Poetry:

```bash
poetry install
poetry run pytest
```

## Seed de datos

El seed de admin/categorías/productos corre automáticamente al levantar `docker compose up`. También puedes ejecutarlo manualmente:

```bash
docker compose exec api python -m app.seed
```

## Estructura

```
app/
├── main.py
├── core/           # config, seguridad, logging, db, excepciones
├── api/v1/         # routers y dependencias
├── models/         # SQLAlchemy
├── schemas/        # Pydantic
├── services/       # lógica de negocio
├── repositories/   # acceso a datos
├── tasks/          # Celery
├── templates/      # emails Jinja2
└── tests/
```

## Licencia

MIT
