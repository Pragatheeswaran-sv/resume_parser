import logging

from fastapi import APIRouter, HTTPException

from src.resume_share.schemas import ShareResumeRequest, ShareResumeResponse
from src.services.resume_share.service import ResumeShareError, share_resume_via_email

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
        result = share_resume_via_email(
            candidate_id=request.candidate_id,
            resume_id=request.resume_id,
            to_address=request.to_address,
            cc_address=request.cc_address,
        )
        return ShareResumeResponse(**result)

    except ResumeShareError as e:
        logger.warning("Resume share error: %s (status=%d)", e.message, e.status_code)
        raise HTTPException(status_code=e.status_code, detail=e.message)

    except Exception as e:
        logger.error("Unexpected error in share_resume_email: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred while sending the email")
