import datetime
import json
import logging
from dotenv import load_dotenv
from src.resume_share.models import EmailNotification, ist_now
from src.resume_share.schemas import ShareResumeResponse
from src.services.resume_share.service import ResumeShareError, share_resume_via_email
from src.services.resume_filter.service import process_resumes
from src.celery.celery_app import celery
from uuid import UUID
from db.connection import SessionLocal

load_dotenv()
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 300  # 5 minutes


@celery.task
def resume_track(email_id: str):
    """Process resumes extracted from an email's attachments.

    Args:
        email_id: UUID string of the email to process (passed as str for JSON
                  serialization compatibility with Celery).

    Returns:
        JSON string summarising processed files.
    """
    logger.info("the celery function initiated successfully")
    data = process_resumes(UUID(email_id))
    return json.dumps(data, indent=2)


@celery.task(
    bind=True, max_retries=MAX_RETRIES, default_retry_delay=RETRY_DELAY_SECONDS
)
def share_mail_to_client(
    self, candidate_id, resume_id, to_address, cc_address, share_log_id
):

    logger.info("the celery function initiated for share_mail")

    db = SessionLocal()

    try:
        try:
            result = share_resume_via_email(
                candidate_id=candidate_id,
                resume_id=resume_id,
                to_address=to_address,
                cc_address=cc_address,
                share_log_id=share_log_id,
            )

        except ResumeShareError as e:
            logger.error(str(e))

            email_notification = (
                db.query(EmailNotification)
                .filter(EmailNotification.email_share_id == share_log_id)
                .first()
            )

            if email_notification is not None:
                current_retry = (email_notification.retry_count or 0) + 1
                email_notification.retry_count = current_retry
                email_notification.last_retry_at = ist_now()

                if current_retry < MAX_RETRIES:
                    email_notification.status = "retrying"
                    db.commit()
                    logger.info(
                        "Retry %d/%d for email %s",
                        current_retry,
                        MAX_RETRIES,
                        share_log_id,
                    )
                    raise self.retry(exc=e)
                else:
                    email_notification.status = "failed"
                    email_notification.failed_at = ist_now()
                    email_notification.updated_at = ist_now()
                    db.commit()
                    logger.info(
                        "Max retries reached for email %s. Marked as failed.",
                        share_log_id,
                    )

            result = {"success": False, "message": str(e)}

        email_notification = (
            db.query(EmailNotification)
            .filter(EmailNotification.email_share_id == share_log_id)
            .first()
        )

        if email_notification is not None:
            email_notification.updated_at = ist_now()

            if result.get("success"):
                logger.info("email share Success at %s", ist_now())
                email_notification.status = "sent"
                email_notification.sent_at = ist_now()

            else:
                logger.info("email share Failed at %s", ist_now())
                email_notification.status = "failed"
                email_notification.failed_at = ist_now()

            db.commit()

        return {
            "success": result.get("success", False),
            "message": result.get("message", result.get("error")),
            "email_id": result.get("email_id"),
        }

    except Exception as e:
        db.rollback()

        return {"success": False, "message": str(e)}

    finally:
        db.close()
