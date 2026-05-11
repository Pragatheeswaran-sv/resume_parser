import json
import logging
from dotenv import load_dotenv
from src.resume_share.schemas import ShareResumeResponse
from src.services.resume_share.service import share_resume_via_email
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
    logger.info("the celery function initiated successfully")
    data = process_resumes(UUID(email_id))
    return json.dumps(data, indent=2)

@celery.task
def share_mail_to_client(candidate_id, resume_id, to_address, cc_address):
    
    logger.info("the celery function initiated for share_mail")
    result = share_resume_via_email(
            candidate_id= candidate_id,
            resume_id = resume_id,
            to_address = to_address,
            cc_address = cc_address,
        )
    return {
        'success': result['success'], 
        'message': result['message'], 
        'email_id': result['email_id']
    }