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

En el primer arranque se restaura automáticamente el backup de datos incluido
(`docker/backup.dump`) y se aplican migraciones + seed. Ver
[Seed y datos iniciales](#seed-y-datos-iniciales).

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

## Simulación

Con el stack levantado, un script independiente (fuera de la app y de los
contenedores) ejercita la API por HTTP como un cliente real: registro, login,
dirección, carrito, pedido, pago con Stripe (webhook firmado) y ciclo de
fulfillment.

```bash
python simulation/simulate.py
```

Opcional: con el perfil `mailpit` activo (ver abajo), la simulación verifica
automáticamente el email de registro usando `MAILPIT_URL`. Ver
`app/docs/simulation.md`.

## Servicios opcionales (perfiles)

Dos helpers de desarrollo no arrancan por defecto; se activan con perfiles:

```bash
docker compose --profile mailpit up -d   # capturador SMTP
docker compose --profile stripe up -d    # mock de la API de Stripe
```

- **mailpit**: expone la UI en http://localhost:8025 y SMTP en 1025. Para que
  la API/worker entreguen ahí el correo, ajusta en `.env`:
  `MAIL_SERVER=mailpit`, `MAIL_PORT=1025`, `MAIL_STARTTLS=False`,
  `MAIL_SSL_TLS=False`. La simulación lo usa vía `MAILPIT_URL`.
- **stripe-mock**: réplica local de la API de Stripe (puertos 12111/12112).
  Apunta la app con `STRIPE_API_BASE=http://stripe-mock:12111` en `.env`.

También puedes exportar `COMPOSE_PROFILES=mailpit,stripe` para activarlos en
cada `docker compose up`.

## Seed y datos iniciales

El proyecto incluye un backup de la base de datos en `docker/backup.dump` que se
restaura automáticamente la **primera vez** que se levanta el stack (solo cuando
el volumen de Postgres está vacío). Así, quien clone el repo arranca con datos
reales en lugar de una BD vacía.

Después de la restauración, el seed de admin/categorías/productos (`app/seed.py`)
corre automáticamente al levantar `docker compose up`. Es idempotente: salta los
registros que ya existen gracias al backup. También puedes ejecutarlo manualmente:

```bash
docker compose exec api python -m app.seed
```

### Regenerar el backup

Cuando quieras actualizar el backup con los datos actuales de tu BD:

```bash
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > docker/backup.dump
```

Luego commitea el `docker/backup.dump` actualizado. El script
`docker/restore-backup.sh` (montado en `/docker-entrypoint-initdb.d/`) es el
encargado de restaurarlo en arranques con volumen fresco, usando
`pg_restore --clean --if-exists`.

> **Nota:** el backup contiene datos reales, incluidos hashes de contraseñas.
> Evita publicarlo en repositorios públicos; en ese caso distribúyelo como
> release o artefacto aparte.

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

simulation/         # script de simulación de cliente (se ejecuta fuera de Docker)
```

## Licencia

MIT
