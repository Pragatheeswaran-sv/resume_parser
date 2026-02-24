import os
import json
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, APIRouter
from services.resume_filter.service import process_resumes

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

@router.post("/test")
async def health_check():
    os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"
    folder = "Resumes"

    data =process_resumes(folder)

    print("\nExtracted Data:\n")
    return json.dumps(data, indent=2)