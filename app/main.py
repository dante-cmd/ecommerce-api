import time

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1.routers import admin, auth, cart, orders, payments, products, users
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging_config import configure_logging, get_logger
from app.core.redis import close_redis

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )

from app.core.limiter import limiter

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="E-commerce backend API",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = (
    [str(settings.frontend_url)]
    if settings.is_production
    else ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # Swagger UI loads external JS/CSS from CDNs and uses inline scripts/styles,
        # so a restrictive CSP breaks /docs, /redoc and /openapi.json.
        if request.url.path not in {"/docs", "/redoc", "/openapi.json"}:
            response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(elapsed_ms, 2),
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning("application_error", message=exc.message, status=exc.status_code)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.on_event("shutdown")
async def shutdown_event():
    await close_redis()


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(products.router, prefix="/api/v1/products", tags=["products"])
app.include_router(cart.router, prefix="/api/v1/cart", tags=["cart"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["payments"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


@app.get("/metrics", tags=["metrics"])
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
