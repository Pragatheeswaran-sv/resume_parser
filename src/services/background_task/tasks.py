import datetime
import json
import logging
from dotenv import load_dotenv
from src.resume_share.models import EmailNotification, ist_now
from src.resume_share.schemas import ShareResumeResponse
from src.services.resume_share.service import share_resume_via_email
from src.services.resume_filter.service import process_resumes
from src.celery.celery_app import celery
from uuid import UUID
from db.connection import SessionLocal

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
def share_mail_to_client(candidate_id, resume_id, to_address, cc_address, share_log_id):
    
    logger.info("the celery function initiated for share_mail")
    result = share_resume_via_email(
            candidate_id= candidate_id,
            resume_id = resume_id,
            to_address = to_address,
            cc_address = cc_address,
            share_log_id = share_log_id
        )
    db = SessionLocal()
    email_notification = db.query(EmailNotification).filter(EmailNotification.email_share_id == share_log_id).first()
    
    if result['success'] and email_notification is not None:
        print('--celery')
        email_notification.sent_at = ist_now()
        email_notification.status = 'sent'
        email_notification.updated_at = ist_now()
        db.commit()
        
        
    return {
        'success': result['success'], 
        'message': result['message'], 
        'email_id': result['email_id']
    }