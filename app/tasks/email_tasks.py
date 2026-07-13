import asyncio
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from jinja2 import Environment, FileSystemLoader

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.tasks.celery_app import celery_app

settings = get_settings()
logger = get_logger(__name__)

mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_STARTTLS=settings.mail_starttls,
    MAIL_SSL_TLS=settings.mail_ssl_tls,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates" / "emails",
)

fm = FastMail(mail_config)


def _render(template_name: str, context: dict) -> str:
    env = Environment(loader=FileSystemLoader(Path(__file__).parent.parent / "templates" / "emails"))
    template = env.get_template(template_name)
    return template.render(context)


def _send(message: MessageSchema) -> None:
    """Send an email.  Synchronous wrapper used by Celery tasks."""
    asyncio.run(fm.send_message(message))


@celery_app.task(bind=True, max_retries=3)
def send_verification_email(self, to_email: str, token: str) -> None:
    try:
        link = f"{settings.frontend_url}/verify-email?token={token}"
        html = _render("verify_email.html", {"verification_link": link})
        message = MessageSchema(
            subject="Verify your email",
            recipients=[to_email],
            body=html,
            subtype=MessageType.html,
        )
        _send(message)
    except Exception as exc:
        logger.error("verification_email_failed", error=str(exc), email=to_email)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_password_reset_email(self, to_email: str, token: str) -> None:
    try:
        link = f"{settings.frontend_url}/reset-password?token={token}"
        html = _render("reset_password.html", {"reset_link": link})
        message = MessageSchema(
            subject="Reset your password",
            recipients=[to_email],
            body=html,
            subtype=MessageType.html,
        )
        _send(message)
    except Exception as exc:
        logger.error("password_reset_email_failed", error=str(exc), email=to_email)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_order_status_email(self, order_id: int, status: str, user_email: str) -> None:
    try:
        html = _render("order_status.html", {"order_id": order_id, "status": status})
        message = MessageSchema(
            subject=f"Order #{order_id} status update: {status}",
            recipients=[user_email],
            body=html,
            subtype=MessageType.html,
        )
        _send(message)
    except Exception as exc:
        logger.error("order_status_email_failed", error=str(exc), order_id=order_id)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_order_confirmation_email(self, order_id: int, total: str, user_email: str) -> None:
    try:
        html = _render("order_confirmation.html", {"order_id": order_id, "total": total})
        message = MessageSchema(
            subject=f"Order #{order_id} confirmation",
            recipients=[user_email],
            body=html,
            subtype=MessageType.html,
        )
        _send(message)
    except Exception as exc:
        logger.error("order_confirmation_email_failed", error=str(exc), order_id=order_id)
        raise self.retry(exc=exc, countdown=60)
