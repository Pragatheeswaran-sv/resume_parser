import json
import logging
from dotenv import load_dotenv
from src.services.resume_filter.service import process_resumes
from src.celery.celery_app import celery
from uuid import UUID

load_dotenv()
logger = logging.getLogger(__name__)


@celery.task
def resume_track(email_id: str):
    """Process resumes extracted from an email's attachments.

    Args:
        email_id: UUID string of the email to process (passed as str for JSON
                  serialization compatibility with Celery).

    Returns:
        JSON string summarising processed files.
    """
    logger.info("NAV----> the celery function initiated successfully")
    data = process_resumes(UUID(email_id))
    return json.dumps(data, indent=2)