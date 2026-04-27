import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from db.connection import SessionLocal
from src.services.auth.service import fetch_emails_oauth
from src.admin.models import ExtractionConfig
from src.services.admin.service import is_within_extraction_window
from src.services.email_reader.service import fetch_emails

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")

scheduler = BlockingScheduler(timezone="Asia/Kolkata")


# ------------------ TIME PARSER ------------------ #
def parse_time_string(time_str):
    """Convert string → datetime.time"""
    if not time_str:
        return None

    if isinstance(time_str, str):
        try:
            return datetime.strptime(time_str, "%H:%M:%S").time()
        except ValueError:
            try:
                return datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                raise ValueError(f"Invalid time format: {time_str}")

    return time_str  # already time object


# ------------------ CONFIG ------------------ #
def _load_config():
    session = SessionLocal()
    try:
        cfg = (
            session.query(ExtractionConfig)
            .filter(ExtractionConfig.is_active.is_(True))
            .first()
        )

        if cfg:
            start_time = parse_time_string(cfg.window_start_time)

            return {
                "is_paused": cfg.is_paused,
                "interval_minutes": cfg.interval_minutes or 15,
                "schedule_type": cfg.schedule_type or "hourly",
                "window_start_time": start_time,
                "weekday": cfg.weekday or "mon",
            }

        return {
            "is_paused": False,
            "interval_minutes": 15,
            "schedule_type": "hourly",
            "window_start_time": None,
            "weekday": "mon",
        }

    except Exception:
        logger.exception("DB read failed")
        return {
            "is_paused": False,
            "interval_minutes": 15,
            "schedule_type": "hourly",
            "window_start_time": None,
            "weekday": "mon",
        }

    finally:
        session.close()


# ------------------ MAIN JOB ------------------ #
def trigger_email_processing():
    config = _load_config()

    if config["is_paused"]:
        logger.info("Paused")
        return

    if not is_within_extraction_window(config):
        logger.info("Outside window")
        return

    logger.info("Processing emails...")
    try:
        result = fetch_emails_oauth()
        logger.info("Done: %s", result)
    except Exception:
        logger.exception("Job failed")


# ------------------ APPLY SCHEDULE ------------------ #
def apply_schedule():
    config = _load_config()

    schedule_type = config["schedule_type"]
    interval = int(config["interval_minutes"])
    start_time = config["window_start_time"]
    weekday = config["weekday"]

    logger.info(f"CONFIG => {config}")

    job = scheduler.get_job("email_processing_job")

    # -------- Determine trigger -------- #
    if schedule_type == "hourly":
        trigger_args = {
            "trigger": "interval",
            "minutes": interval,
        }
        logger.info(f"Hourly schedule at {interval}")

    elif schedule_type == "daily":
        if not start_time:
            logger.warning("Missing start_time for daily")
            return

        trigger_args = {
            "trigger": "cron",
            "hour": start_time.hour,
            "minute": start_time.minute,
        }
        logger.info(f"Daily at {start_time}")

    elif schedule_type == "weekly":
        if not start_time:
            logger.warning("Missing start_time for weekly")
            return

        trigger_args = {
            "trigger": "cron",
            "day_of_week": weekday,
            "hour": start_time.hour,
            "minute": start_time.minute,
        }
        logger.info(f"Weekly on {weekday} at {start_time}")

    else:
        logger.warning("Invalid schedule_type → default hourly")
        trigger_args = {
            "trigger": "interval",
            "minutes": 15,
        }

    # -------- Create or Update -------- #
    if not job:
        scheduler.add_job(
            trigger_email_processing,
            id="email_processing_job",
            replace_existing=True,
            **trigger_args,
        )
        logger.info("Job CREATED → %s", trigger_args)
        return

    try:
        need_update = False

        if job.trigger.__class__.__name__ == "IntervalTrigger":
            current = int(job.trigger.interval.total_seconds() / 60)
            if trigger_args["trigger"] != "interval" or current != interval:
                need_update = True
        else:
            need_update = True  # cron → always update

        if need_update:
            scheduler.reschedule_job(
                "email_processing_job",
                **trigger_args,
            )
            logger.info("Job UPDATED → %s", trigger_args)

    except Exception:
        logger.exception("Failed updating job")


# ------------------ AUTO REFRESH ------------------ #
def refresh_scheduler():
    logger.info("Checking for schedule updates...")
    apply_schedule()


# ------------------ MAIN ------------------ #
def main():
    apply_schedule()

    scheduler.add_job(
        refresh_scheduler,
        "interval",
        seconds=600,
        id="refresh_job",
        replace_existing=True,
    )

    logger.info("Scheduler started (auto-refresh enabled)")
    scheduler.start()


if __name__ == "__main__":
    main()