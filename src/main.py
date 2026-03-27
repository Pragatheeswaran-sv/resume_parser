import os
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"
from fastapi import FastAPI
from dotenv import load_dotenv
import logging
from db.connection import engine, Base
from sqlalchemy import text
from src.resume_filter.api import router as resume_router
from src.email_reader.api import router as email_router
from src.candidate.api import router as candidate_route
from fastapi.middleware.cors import CORSMiddleware
 

 
load_dotenv()

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(resume_router)
app.include_router(email_router)
app.include_router(candidate_route)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    """Initialize database and pgvector extension on application startup."""

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    logger.info("Database & pgvector ready")

@app.get("/health")
def health_check()-> dict:
    """Simple health check endpoint."""
    return {"message": "Resume tracker application running successful"}