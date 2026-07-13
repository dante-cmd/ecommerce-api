"""Celery tasks that run the client simulation on a schedule."""

import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.scripts.simulate_client import simulate
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.simulation_tasks.run_client_simulation", bind=True, max_retries=0)
def run_client_simulation(self, mailbox_dir: str | None = None) -> None:
    """Run a complete simulated client interaction.

    Designed to be triggered by Celery Beat every few seconds.  Emails that
    would normally be delivered over SMTP are saved to ``mailbox_dir`` as HTML
    files.
    """
    settings = get_settings()
    default_dir = Path(__file__).parent.parent / "scripts" / "mailbox"
    target_dir = Path(mailbox_dir) if mailbox_dir else default_dir
    asyncio.run(simulate(settings, target_dir))
