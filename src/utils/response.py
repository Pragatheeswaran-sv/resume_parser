import logging
from typing import Any
from uuid import UUID
from datetime import datetime, date

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def serialize_value(value: Any) -> Any:
    """Recursively convert non-JSON-serializable types to JSON-safe equivalents."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Exception):
        return str(value)
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    return value


def serialize_response(data: Any) -> Any:
    """Ensure a response payload is fully JSON-serializable."""
    return serialize_value(data)


def safe_raise_http_exception(
    status_code: int,
    message: str,
    error: Exception | None = None,
) -> None:
    """Raise HTTPException with a consistently structured detail payload.

    Guarantees that no raw Exception objects appear in the response body.
    """
    if error is not None:
        logger.error(
            "HTTP %d: %s | error=%s", status_code, message, str(error), exc_info=True
        )
    raise HTTPException(
        status_code=status_code,
        detail={"status": "error", "message": message},
    )


from fastapi import status


def success_response(message: str, data=None, status_code=status.HTTP_200_OK):
    return {
        "status_code": status_code,
        "message": message,
        "data": data,
    }


def validation_error_response(errors: list):
    return {
        "status_code": status.HTTP_400_BAD_REQUEST,
        "errors": errors,
    }


def not_found_response(field: str, message: str):
    return {
        "status_code": status.HTTP_404_NOT_FOUND,
        "errors": [
            {
                "field": field,
                "message": message,
            }
        ],
    }


def internal_server_error_response():
    return {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "errors": [
            {
                "field": "server",
                "message": "An unexpected error occurred.",
            }
        ],
    }