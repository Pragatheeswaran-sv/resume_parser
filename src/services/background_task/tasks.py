import os
import json
import logging
from dotenv import load_dotenv
from src.services.resume_filter.service import process_resumes
from typing import List, Dict, Any
from src.celery.celery_app import celery

load_dotenv()
logger = logging.getLogger(__name__)

@celery.task
def resume_track(message_id: int):
    """
    Process resumes from the local `Resumes` folder.

    This API performs the following steps:
    1. Reads all PDF and DOCX resumes from the `Resumes` directory.
    2. Extracts raw text from each resume.
    3. Uses a local Ollama LLM (llama3) to extract structured information such as:
        - Name
        - Total experience
        - Skills
        - Companies
        - Education
    4. Generates embeddings using the HuggingFace model `all-MiniLM-L6-v2`.
    5. Stores the extracted resume data in the PostgreSQL database.
    6. Saves vector embeddings in a FAISS vector database for semantic search.

    Returns:
        dict: Summary of the resume processing including total resumes processed
        and extracted structured data.

    Example Response:
    {
        "status": "success",
        "message": "Resumes processed successfully",
        "total_resumes": 3,
        "data": [
            {
                "file_name": "resume1.pdf",
                "name": "John Doe",
                "total_experience": 5,
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "companies": ["ABC Corp", "XYZ Ltd"],
                "education": ["B.Tech Computer Science"]
            }
        ]
    }
    """
    logger.info("NAV----> the celery function initiated successfully")
    # os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"
    # folder = "Resumes"
    data = process_resumes(message_id)
    return json.dumps(data, indent=2)