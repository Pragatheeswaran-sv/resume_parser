"""API route endpoints for Admin Dashboard.

All routes cleanly delegate to admin_dashboard_service class methods,
maintaining complete separation between routing and business logic.
"""

import logging
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.dependencies import get_current_admin
from src.admin_dashboard.service import admin_dashboard_service

load_dotenv()
logger = logging.getLogger(__name__)

# Legacy module-level alias for backward compatibility
admin_dashboard = admin_dashboard_service.admin_dashboard


router = APIRouter(
    prefix="/api",
    tags=["Admin Dashboard"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


@router.get("/admin_dashboard")
def get_admin_dashboard(_admin=Depends(get_current_admin)) -> Dict[str, Any]:
    """Fetch aggregated dashboard analytics for the authenticated admin."""
    try:
        admin_id = _admin.admin_id
        return admin_dashboard_service.get_dashboard(admin_id)
    except ValueError as e:
        logger.warning("[get_admin_dashboard] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[get_admin_dashboard] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )