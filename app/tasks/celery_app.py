from celery import Celery
from celery.signals import setup_logging

from app.core.config import get_settings
from app.core.logging_config import configure_logging

settings = get_settings()

celery_app = Celery(
    "ecommerce",
    broker=str(settings.celery_broker_url),
    backend=str(settings.celery_result_backend),
    include=["app.tasks.email_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.tasks.email_tasks.*": {"queue": "emails"},
    },
    task_default_queue="default",
)


@setup_logging.connect
def config_loggers(**kwargs):
    configure_logging()
