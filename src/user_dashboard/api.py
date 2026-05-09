import logging

# from .schema import ModelConfigRequest
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from src.services.user_dashboard.service import user_dashboard
from src.admin.dependencies import get_current_user

load_dotenv()
logger = logging.getLogger(__name__)


# ── Public routes (no auth guard) ─────────────────────────────────────────

router = APIRouter(
    prefix="/api",
    tags=["Admin"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)

@router.get("/user_dashboard")
def get_user_dashboard(_user=Depends(get_current_user)):
    """Fetch the profile of the currently authenticated admin."""
    try:
        user_id = _user.user_id
        user_mail = _user.email_address
        return user_dashboard(user_mail)
    except ValueError as e:
        logger.warning("[get_profile] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )