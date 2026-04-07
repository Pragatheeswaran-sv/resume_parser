import time
import logging
# from .schema import ModelConfigRequest
from dotenv import load_dotenv
from pydantic import ValidationError
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from src.services.admin.service import (
    admin_check, create_model,
    delete_auth_mail, new_admin,
    list_mail, new_auth,
    update_auth_mail, list_model,
    model_version, new_model_version,
    model_config, get_model
)
from src.utils.response import serialize_response

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter(
	prefix="/api",
	tags=["Payment-Process"],
	responses={
		400: {"description": "Bad Request"},
		404: {"description": "Not Found"},
		500: {"description": "Internal Server Error"},
	},
)

@router.post("/create_admin")
def create_admin(payload: Dict[str, Any]) :
    try:
        return new_admin(payload)
    except ValueError as e:
        logger.warning("[create_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.post("/admin/login")
def admin_login(email: str, password: str) :
    try:
        return admin_check(email, password)
    except ValueError as e:
        logger.warning("[admin_login] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.get("/list_auth_mail")
def main() :
    try:
        return list_mail()
    except ValueError as e:
        logger.warning("[list_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.post("/create_auth_mail")
def new_auth_mail(payload: Dict[str, Any]) :
    try:
        return new_auth(payload)
    except ValueError as e:
        logger.warning("[create_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.patch("/delete_auth_mail/")
def delete_auth(auth_mail_id: str):
    try:
        return delete_auth_mail(auth_mail_id)
    except ValueError as e:
        logger.warning("[delete_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.patch("/update_auth_mail/")
def update_auth(auth_mail_id: str, payload: Dict[str, Any]):
    try:
        return update_auth_mail(auth_mail_id, payload)
    except ValueError as e:
        logger.warning("[update_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.get(
    "/list_model/",
    # summary="List active AI models",
    # description=(
    #     "Fetch all active AI models configured for admin workflows and "
    #     "resume processing."
    # ),
    # response_description="A list of active AI model entries.",
)
def list_models() :
    """Return all active models available in the system."""
    try:
        return list_model()
    except ValueError as e:
        logger.warning("[list_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })


@router.post(
    "/create_model/",
    summary="Create a new AI model",
    description="Create and store a new active AI model by model name.",
    response_description="Created AI model details.",
)
def add_model(payload: Dict[str, Any]):
    """Create a new model with the provided ``model_name``."""
    try:
        return create_model(payload)
    except ValueError as e:
        logger.warning("[create_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.get("/list_model_versions/")
def list_model_versions(model_id):
    """
    List Model Versions

    Retrieves all active versions for a given AI model using the provided model ID.

    This endpoint first checks whether the AI model exists and is active.
    If the model is found, it returns all active versions associated with that model.

    Args:
        model_id (str): The unique identifier of the AI model.

    Returns:
        dict: A response object containing:
            - status (int): HTTP status code
            - message (str): Success message
            - data (list): List of active model versions

    Response Includes:
        - model_version_id
        - version_name

    Raises:
        HTTPException:
            - 400 Bad Request: If the model is not found or no versions exist.
    """
    
    try:
       return model_version(model_id)
    except ValueError as e:
        logger.warning("[list_model_versions] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    

@router.post("/new_model_version/")
def create_model_version(model_id, payload: Dict[str, Any]):
    """
        Create Model Version

        Creates a new version entry for a given AI model using the provided model ID
        and request payload.

        This endpoint first validates whether the AI model exists and is active.
        If the model is valid, it creates a new active version associated with that model.

        Args:
            model_id (str): The unique identifier of the AI model.
            payload (Dict[str, Any]): Request body containing model version details.

        Request Body:
            - version_name (str): Name of the new model version

        Returns:
            dict: A response object containing:
                - status (int): HTTP status code
                - message (str): Success message
                - data (dict): Newly created model version details

        Response Includes:
            - model_version_id
            - version_name

        Raises:
            HTTPException:
                - 400 Bad Request: If the model does not exist or version name is invalid.
    """
    try:
        return new_model_version(model_id, payload)
    except ValueError as e:
        logger.warning("[new_model_version] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.post("/model_config/")
def get_model_config(payload: Dict[str, Any], admin_id):
    """
        Create Model Configuration

        Creates a new AI model configuration for a given admin using the provided
        model ID, model version ID, and configuration details.

        This endpoint validates whether:
        - the admin ID is provided
        - the AI model exists and is active
        - the AI model version exists and is active

        If validation succeeds, a new model configuration is created and stored.

        Args:
            payload (Dict[str, Any]): Request body containing model configuration details.
            admin_id (str): The unique identifier of the admin creating the configuration.

        Request Body:
            - model_id (str): Unique AI model ID
            - model_version_id (str): Unique AI model version ID
            - apikey (str, optional): API key for the selected model
            - version (str, optional): External provider version name
            - max_tokens (int, optional): Maximum token limit
            - temperature (float, optional): Model temperature value

        Returns:
            dict: A response object containing:
                - status (int): HTTP status code
                - message (str): Success message
                - data (dict): Created model configuration details

        Response Includes:
            - model_config_id
            - model_id
            - model_name
            - model_version_id
            - model_version_name
            - admin_id
            - apikey
            - max_tokens

        Raises:
            HTTPException:
                - 400 Bad Request: If admin ID, model, or model version is invalid.
    """
    try:
        return model_config(payload, admin_id)
    except ValueError as e:
        logger.warning("[get_model_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.get("/get_model_config/")
def fetch_model_config(admin_id):
    """
        Fetch Model Configuration

        Retrieves the active AI model configuration associated with the given admin ID.

        This endpoint fetches the configured AI model, model version, API key,
        token settings, and other related configuration details for the specified admin.

        Args:
            admin_id (str): The unique identifier of the admin.

        Returns:
            dict: A response object containing:
                - status (int): HTTP status code
                - message (str): Success message
                - data (dict): Active model configuration details

        Response Includes:
            - model_config_id
            - model_id
            - model_name
            - model_version_id
            - model_version_name
            - admin_id
            - apikey
            - max_tokens
            - temperature

        Raises:
            HTTPException:
                - 400 Bad Request: If admin ID is missing or no active configuration is found.
    """
    try:
        return get_model(admin_id)
    except ValueError as e:
        logger.warning("[fetch_model_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })