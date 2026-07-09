import datetime
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from src.services.background_task.tasks import share_mail_to_client
from src.resume_share.schemas import (
    RetryShareEmailRequest,
    RetryShareEmailResponse,
    ShareResumeRequest,
    ShareResumeResponse,
)
from src.resume_share.models import EmailNotification, ist_now
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

        share_log = (
            db.query(EmailNotification)
            .filter(
                EmailNotification.resume_id == resume_id,
                EmailNotification.to_address == to_address,
            )
            .order_by(EmailNotification.created_at.desc())
            .first()
        )

        date = datetime.datetime.now()

        past_five_days = date - datetime.timedelta(days=7)
        if share_log and share_log.created_at > past_five_days and not share:
            return {
                "success": False,
                "message": f"Candidate profile already shared to {to_address} at {share_log.created_at}",
                "email_id": "",
            }

        share_log = EmailNotification(
            # candidate_id=candidate_id,
            resume_id=resume_id,
            to_address=to_address,
            cc_address=cc_address,
        )

        db.add(share_log)
        db.commit()
        db.refresh(share_log)

        celery_task = share_mail_to_client.delay(
            candidate_id=request.candidate_id,
            resume_id=request.resume_id,
            to_address=request.to_address,
            cc_address=request.cc_address,
            share_log_id=share_log.email_share_id,
        )

        return {
            "success": True,
            "message": "resume shared successfully",
            "email_id": to_address,
        }

    except ResumeShareError as e:
        logger.warning("Resume share error: %s (status=%d)", e.message, e.status_code)
        raise HTTPException(status_code=e.status_code, detail=e.message)

    except Exception as e:
        logger.error(
            "Unexpected error in share_resume_email: %s", str(e), exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while sending the email",
        )
    finally:
        db.close()


@router.post("/resume/share-email/retry", response_model=RetryShareEmailResponse)
def retry_share_emails(request: RetryShareEmailRequest):
    """Manually retry multiple failed email shares after fixing configuration."""
    db = SessionLocal()
    try:
        ids = request.email_share_ids
        if not ids:
            return {
                "success": False,
                "message": "No email_share_ids provided",
                "results": [],
            }

        results = []
        queued_count = 0
        skipped_count = 0

        for i, email_share_id in enumerate(ids):
            share_log = (
                db.query(EmailNotification)
                .filter(EmailNotification.email_share_id == email_share_id)
                .first()
            )

            if not share_log:
                results.append(
                    {
                        "email_share_id": email_share_id,
                        "success": False,
                        "message": "Email share log not found",
                    }
                )
                skipped_count += 1
                continue

            if share_log.status not in ("failed",):
                results.append(
                    {
                        "email_share_id": email_share_id,
                        "success": False,
                        "message": f"Cannot retry — current status is '{share_log.status}'. Only 'failed' emails can be retried.",
                    }
                )
                skipped_count += 1
                continue

            share_log.retry_count = 0
            share_log.status = "Pending"
            share_log.failed_at = None
            share_log.updated_at = ist_now()
            db.flush()

            share_mail_to_client.apply_async(
                args=(
                    str(share_log.resume.candidate_id),
                    str(share_log.resume_id),
                    share_log.to_address,
                    share_log.cc_address.split(",") if share_log.cc_address else None,
                    share_log.email_share_id,
                ),
                countdown=i * 15,
            )

            results.append(
                {
                    "email_share_id": email_share_id,
                    "success": True,
                    "message": "Retry queued successfully",
                }
            )
            queued_count += 1

        db.commit()

        return {
            "success": queued_count > 0,
            "message": f"{queued_count} email(s) queued for retry, {skipped_count} skipped",
            "results": results,
        }

    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error in retry_share_emails: %s", str(e), exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while retrying emails",
        )
    finally:
        db.close()
