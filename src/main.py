import os
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"
from fastapi import FastAPI
from dotenv import load_dotenv
import logging
from db.connection import engine, Base
from sqlalchemy import text
from resume_filter.api import router as resume_router

load_dotenv()

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(resume_router)

@app.on_event("startup")
def startup():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database & pgvector ready")


@app.get("/health")
def health_check():
    return {"message": "Resume tracker application running successful"}


