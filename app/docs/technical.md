# Documentación Técnica - Ecommerce API

## 1. Visión General

Esta API RESTful es el backend de una plataforma de comercio electrónico. Está construida sobre Python 3.12 con un enfoque **async-first**, arquitectura por capas (Clean Architecture light) y separación clara de responsabilidades entre presentación, lógica de negocio, acceso a datos e infraestructura.

El objetivo principal es ofrecer un sistema escalable, mantenible y seguro que soporte: autenticación de usuarios, catálogo de productos, carrito de compras, órdenes, pagos mediante Stripe, envío de emails, almacenamiento de archivos, tareas en segundo plano y administración.

---

## 2. Arquitectura

### 2.1. Estructura de capas

```
app/
├── main.py              # Punto de entrada FastAPI
├── api/v1/              # Capa de presentación (HTTP)
│   ├── deps.py          # Dependencias inyectables
│   └── routers/         # Endpoints por dominio
├── services/            # Lógica de negocio
├── repositories/        # Acceso a datos (Repository Pattern)
├── models/              # Modelos SQLAlchemy (ORM)
├── schemas/             # DTOs con Pydantic
├── tasks/               # Tareas Celery
├── core/                # Infraestructura transversal
└── templates/           # Plantillas Jinja2 para emails
```

### 2.2. Patrones de diseño

| Patrón | Uso |
|--------|-----|
| **Repository Pattern** | Aislar el acceso a datos y facilitar tests. `BaseRepository[ModelType]` centraliza operaciones CRUD. |
| **Service Layer** | Encapsular reglas de negocio y coordinar repositorios, terceros (Stripe, SMTP) y tareas Celery. |
| **Dependency Injection** | FastAPI `Depends` inyecta sesiones de DB, settings, Redis y permisos. |
| **DTOs / Schemas** | Pydantic separa datos de entrada, salida y filtros. |
| **CQRS light** | Lecturas complejas en repositorios; escrituras por servicios. |

### 2.3. Flujo de datos típico

```
Cliente HTTP
    ↓
Router FastAPI → Depends(deps)
    ↓
Service → Repository → SQLAlchemy AsyncSession → PostgreSQL
    ↓
Celery Task → Email / Stripe / Redis
```

---

## 3. Stack Tecnológico y Justificación

### 3.1. Lenguaje y runtime

**Python 3.12**

- Lenguaje maduro con gran ecosistema para backend.
- Soporte nativo para `async`/`await` y mejoras de performance (comprehensiones anidadas, f-strings más rápidas, etc.).
- Tipado progresivo compatible con herramientas como Pydantic y mypy.

### 3.2. Framework web

**FastAPI 0.115**

- Framework moderno, async-first y de alto rendimiento basado en Starlette.
- Validación automática de request/response con Pydantic.
- Generación automática de documentación OpenAPI (`/docs`, `/redoc`).
- Sistema de inyección de dependencias integrado.
- Amplia adopción en la industria y comunidad activa.

### 3.3. Validación y configuración

**Pydantic v2 + pydantic-settings**

- Pydantic v2 ofrece validación de datos muy rápida (escrita en Rust).
- `pydantic-settings` permite cargar configuración desde variables de entorno de forma tipada y con valores por defecto.
- Facilita mantener secretos y parámetros fuera del código fuente.

### 3.4. Servidor ASGI

**Uvicorn + Gunicorn**

- **Uvicorn**: servidor ASGI rápido basado en `uvloop` y `httptools`; ideal para desarrollo con hot-reload.
- **Gunicorn**: gestor de procesos para producción; puede ejecutar workers Uvicorn (`uvicorn.workers.UvicornWorker`) para aprovechar múltiples núcleos.

### 3.5. ORM y base de datos

**SQLAlchemy 2.0 (async)**

- ORM más maduro y flexible del ecosistema Python.
- Versión 2.0 introduce modelos tipados con `Mapped` y `mapped_column`, mejor soporte async y consultas más explícitas.
- Permite migrar fácilmente entre drivers síncronos y asíncronos.

**asyncpg**

- Driver nativo async para PostgreSQL.
- Mejor rendimiento que `psycopg2` en contextos concurrentes porque no bloquea el event loop.
- Perfecto para FastAPI + SQLAlchemy async.

**PostgreSQL 16**

- Base de datos relacional robusta, ACID-compliant y con soporte avanzado para:
  - Full-text search (`to_tsvector`).
  - JSONB, transacciones, restricciones `CHECK`.
  - Índices y paginación eficiente.

**Alembic**

- Herramienta estándar de migraciones para SQLAlchemy.
- Permite versionar el esquema de la base de datos y reproducir cambios en cualquier entorno.
- Integrado con `Base.metadata` de SQLAlchemy.

### 3.6. Caché y broker de tareas

**Redis 7**

- Caché compartida y broker de Celery unificado.
- Se utiliza para:
  - Blacklist de tokens JWT (`jti`).
  - Result backend de Celery.
  - Caché genérica de la aplicación.
- Alto rendimiento en memoria y soporte para estructuras de datos útiles.

**Celery 5.4**

- Sistema de colas de tareas distribuidas.
- Permite ejecutar operaciones pesadas o lentas fuera del request HTTP:
  - Envío de emails.
  - Simulaciones y tareas programadas.
- Soporta múltiples colas (`default`, `emails`, `orders`).
- Celery Beat para tareas periódicas.

### 3.7. Autenticación y seguridad

**JWT (python-jose) + passlib (argon2 / bcrypt)**

- JWT permite tokens stateless con expiración y claims personalizados.
- Refresh tokens rotativos mejoran la seguridad frente a robos de tokens.
- Blacklist de `jti` en Redis permite invalidación selectiva.
- Argon2 es el ganador actual del Password Hashing Competition; bcrypt se mantiene como fallback.

**itsdangerous**

- Firma de cookies seguras para el carrito de usuarios anónimos.
- Permite mantener sesiones sin estado en el servidor.

**slowapi**

- Rate limiting integrado con FastAPI/Starlette.
- Limita endpoints sensibles como login y registro para mitigar ataques de fuerza bruta.

### 3.8. Pagos

**Stripe**

- Plataforma de pagos líder en comercio electrónico.
- Soporta PaymentIntents, webhooks y reembolsos.
- API bien documentada y SDK oficial para Python.

### 3.9. Almacenamiento de archivos

**MinIO + boto3**

- MinIO es un object storage compatible con la API S3 de AWS.
- Permite almacenar imágenes de productos de forma self-hosted en desarrollo y producción.
- `boto3` facilita migrar a AWS S3 en producción sin cambios significativos.

### 3.10. Emails

**fastapi-mail + Jinja2**

- `fastapi-mail` simplifica el envío de emails HTML con SMTP.
- Jinja2 permite plantillas reutilizables para verificación, confirmaciones y notificaciones.

### 3.11. Observabilidad

**structlog**

- Genera logs estructurados (JSON en producción).
- Facilita ingestión en sistemas ELK, Loki o Datadog.

**prometheus-client**

- Expone métricas en `/metrics` para monitoreo con Prometheus.

**sentry-sdk**

- Captura errores en producción con trazas, contexto y alertas.

### 3.12. Contenedores y orquestación local

**Docker + Docker Compose**

- Entornos reproducibles entre desarrollo y producción.
- Docker Compose levanta 7+ servicios: API, worker, beat, PostgreSQL, Redis, MinIO y Nginx.
- Healthchecks y dependencias condicionales mejoran la robustez del arranque.

**Nginx**

- Reverse proxy que expone la API en puertos 80/443.
- Puede servir archivos estáticos, balanceo de carga y terminación SSL.

### 3.13. Testing y calidad de código

**pytest, pytest-asyncio, pytest-cov**

- `pytest` es el framework de testing estándar en Python.
- `pytest-asyncio` permite testear funciones asíncronas.
- `pytest-cov` mide cobertura (mínimo configurado al 70%).

**factory-boy**

- Genera datos de prueba de forma sencilla y reproducible.

**httpx**

- Cliente HTTP moderno y async para tests de integración contra la API.

**black, ruff, mypy**

- `black`: formateo consistente del código.
- `ruff`: linter ultrarrápido que reemplaza a flake8 y otras herramientas.
- `mypy`: verificación estática de tipos.

---

## 4. Seguridad

| Medida | Implementación |
|--------|----------------|
| Autenticación | JWT access tokens de 15 min + refresh tokens de 7 días. |
| Refresh tokens | Cookie `HttpOnly`, `SameSite=Strict`, `Secure` en producción. |
| Logout / invalidación | Blacklist de `jti` en Redis. |
| Passwords | Hash con Argon2 (fallback bcrypt). |
| Rate limiting | slowapi en `/register`, `/login`, `/password-reset-request`. |
| Headers de seguridad | `X-Content-Type-Options`, `X-Frame-Options`, CSP, HSTS. |
| Subida de archivos | Almacenamiento en MinIO/S3, no en disco local. |
| Validación | Pydantic en todas las entradas. |

---

## 5. Flujo de Compra Principal

1. **Registro**: `POST /api/v1/auth/register` → crea usuario y envía email de verificación vía Celery.
2. **Verificación**: `POST /api/v1/auth/verify-email` → marca la cuenta como verificada.
3. **Login**: `POST /api/v1/auth/login` → devuelve access token y refresh token en cookie.
4. **Catálogo**: `GET /api/v1/products` → búsqueda con full-text search, filtros y paginación por cursor.
5. **Carrito**: `POST /api/v1/cart/items` → soporta usuarios autenticados y sesiones anónimas.
6. **Checkout**: `POST /api/v1/orders` → valida stock, calcula totales, crea orden y limpia carrito.
7. **Pago**: `POST /api/v1/payments/intent` → crea PaymentIntent en Stripe.
8. **Webhook**: `POST /api/v1/payments/webhook` → actualiza estado de la orden a `paid`.
9. **Fulfillment**: `PATCH /api/v1/orders/{id}/status` → máquina de estados con notificación por email.

---

## 6. Despliegue y Operación

### 6.1. Desarrollo local

```bash
docker-compose up --build
```

El contenedor `api` ejecuta automáticamente migraciones, seed y levanta Uvicorn con reload.

### 6.2. Seed

`app/seed.py` crea un usuario administrador y aproximadamente 500 productos determinísticos (`random.seed(42)`).

### 6.3. CI/CD

GitHub Actions ejecuta:
1. Lint (`ruff`, `black`, `mypy`).
2. Migraciones Alembic.
3. Tests con cobertura.
4. Build de imágenes Docker.

### 6.4. Monitoreo

- Logs estructurados con `structlog`.
- Métricas Prometheus en `/metrics`.
- Errores en producción con Sentry.

---

## 7. Consideraciones Técnicas

- **Async-first**: todo el acceso a DB, Redis y terceros es asíncrono para maximizar throughput.
- **Paginación por cursor** en catálogo para evitar problemas de `OFFSET` en grandes volúmenes.
- **Máquina de estados** en órdenes para mantener integridad del flujo de fulfillment.
- **Numeric(12,2)** para dinero y restricciones `CHECK` para reglas de negocio en DB.
- **Relaciones con `lazy="selectin"`** para evitar problemas N+1 en lecturas.

---

## 8. Decisiones de Diseño Resumidas

| Aspecto | Decisión | Razón |
|---------|----------|-------|
| Lenguaje | Python 3.12 | Ecosistema maduro y async. |
| Framework | FastAPI | Alto rendimiento, validación automática, OpenAPI. |
| ORM | SQLAlchemy 2.0 async | Flexibilidad, madurez, tipado. |
| DB | PostgreSQL 16 | Robusta, full-text search, ACID. |
| Cache/Broker | Redis | Unificado, rápido, versátil. |
| Tareas | Celery | Escalable y probado. |
| Pagos | Stripe | Estándar de la industria. |
| Archivos | MinIO/S3 | Self-hosted y portable a AWS. |
| Auth | JWT + Redis blacklist | Stateless con invalidación. |
| Emails | fastapi-mail + Jinja2 | Plantillas HTML y SMTP. |
| Contenedores | Docker Compose | Reproducibilidad local. |
| Tests | pytest async + factory-boy | Calidad y velocidad de testing. |
