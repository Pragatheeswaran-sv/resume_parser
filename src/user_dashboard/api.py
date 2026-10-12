"""API route endpoints for User Dashboard.

All routes cleanly delegate to user_dashboard_service class methods,
maintaining complete separation between routing and business logic.
"""

import logging
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.dependencies import get_current_user
from src.user_dashboard.service import user_dashboard_service

load_dotenv()
logger = logging.getLogger(__name__)

# Legacy module-level alias for backward compatibility
user_dashboard = user_dashboard_service.user_dashboard


router = APIRouter(
    prefix="/api",
    tags=["User Dashboard"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


@router.get("/user_dashboard")
def get_user_dashboard(_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Fetch dashboard metrics for the currently authenticated user."""
    try:
        user_mail = _user.email_address
        return user_dashboard_service.get_dashboard(user_mail)
    except ValueError as e:
        logger.warning("[get_user_dashboard] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[get_user_dashboard] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )