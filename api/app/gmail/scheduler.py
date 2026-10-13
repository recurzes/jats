from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.gmail.models import SyncTrigger
from app.gmail.sync import sync_owner_account

SYNC_JOB_ID = "gmail-sync"


def start_scheduler() -> BackgroundScheduler:
    """Start the in-process scheduler. It holds no state: everything is in Postgres."""
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        sync_owner_account,
        "interval",
        args=[SyncTrigger.SCHEDULE],
        minutes=get_settings().sync_interval_minutes,
        id=SYNC_JOB_ID,
        # A sync that outlasts the interval is not doubled, and missed runs collapse into one.
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
