import datetime
import logging

from fastapi import APIRouter, HTTPException
from src.services.background_task.tasks import share_mail_to_client
from src.resume_share.schemas import ShareResumeRequest, ShareResumeResponse
from src.resume_share.models import EmailNotification
from src.services.resume_share.service import ResumeShareError, share_resume_via_email
from db.connection import SessionLocal
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Resume-Share"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


@router.post("/resume/share-email", response_model=ShareResumeResponse)
def share_resume_email(request: ShareResumeRequest):
    """Send a candidate's resume and profile details via email."""
    try:
        db = SessionLocal()

        candidate_id = request.candidate_id
        resume_id = request.resume_id
        to_address = request.to_address
        cc_address = str(request.cc_address)
        share = request.share

        share_log = db.query(EmailNotification).filter(
                EmailNotification.resume_id == resume_id,
                EmailNotification.to_address == to_address,
            ).order_by(EmailNotification.created_at.desc()).first()
        
        date = datetime.datetime.now()

        past_five_days = date - datetime.timedelta(days=7)
        if share_log and share_log.created_at > past_five_days and not share:
            return {
                "success": False,
                "message": f"Candidate profile already shared to {to_address} at {share_log.created_at}",
                "email_id": ""
            }
        
        share_log = EmailNotification(
            # candidate_id=candidate_id,
            resume_id=resume_id,
            to_address=to_address,
            cc_address=cc_address
        )

        db.add(share_log)
        db.commit()
        db.refresh(share_log)
        print('share_log.email_share_id', share_log.email_share_id)
        celery_task = share_mail_to_client.delay(
            candidate_id=request.candidate_id,
            resume_id=request.resume_id,
            to_address=request.to_address,
            cc_address=request.cc_address,
            share_log_id = share_log.email_share_id
        )
       
        return{
            'success' : True,
            'message' : "resume shared successfully",
            'email_id' : to_address
        }

    except ResumeShareError as e:
        logger.warning("Resume share error: %s (status=%d)", e.message, e.status_code)
        raise HTTPException(status_code=e.status_code, detail=e.message)

    except Exception as e:
        logger.error("Unexpected error in share_resume_email: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred while sending the email")
    finally:
        db.close()
