import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from db.connection import SessionLocal
from src.admin.models import ExtractionConfig
from src.services.admin.service import is_within_extraction_window
from src.services.email_reader.service import fetch_emails

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")

DEFAULT_INTERVAL_MINUTES = 15
_DEFAULTS = {
    "is_paused": False,
    "interval_minutes": DEFAULT_INTERVAL_MINUTES,
    "window_enabled": False,
    "window_start_time": None,
    "window_end_time": None,
    "window_timezone": "Asia/Kolkata",
}


def _load_config():
    """Read the active ExtractionConfig row; return defaults when absent or on DB error."""
    session = SessionLocal()
    try:
        cfg = (
            session.query(ExtractionConfig)
            .filter(ExtractionConfig.is_active.is_(True))
            .first()
        )
        if cfg:
            return {
                "is_paused": cfg.is_paused,
                "interval_minutes": cfg.interval_minutes,
                "window_enabled": cfg.window_enabled or False,
                "window_start_time": cfg.window_start_time,
                "window_end_time": cfg.window_end_time,
                "window_timezone": cfg.window_timezone or "Asia/Kolkata",
            }
        return dict(_DEFAULTS)
    except Exception:
        logger.warning(
            "Could not read extraction_config (table may not exist yet) — using defaults",
            exc_info=True,
        )
        session.rollback()
        return dict(_DEFAULTS)
    finally:
        session.close()


def trigger_email_processing():
    """Fetch new emails and enqueue resume_track tasks via Celery.

    Respects the global ``is_paused`` flag and time-window restriction
    stored in ``extraction_config``.
    """
    config = _load_config()
    if config["is_paused"]:
        logger.info("Extraction is globally paused — skipping this cycle")
        return

    if not is_within_extraction_window(config):
        logger.info("Skipping extraction: outside configured time window")
        return

    logger.info("Scheduler job triggered — checking for new emails")
    try:
        result = fetch_emails()
        logger.info("Email processing cycle complete: %s", result)
    except Exception:
        logger.exception("Error during scheduled email processing")


def main():
    config = _load_config()
    interval = config["interval_minutes"]

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        trigger_email_processing,
        "interval",
        minutes=interval,
        id="email_processing_job",
        replace_existing=True,
    )
    logger.info(
        "Scheduler started — jobs will run every %d minute(s) (paused=%s)",
        interval,
        config["is_paused"],
    )
    scheduler.start()


if __name__ == "__main__":
    main()
