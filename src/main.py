import os
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"

from fastapi import FastAPI
from dotenv import load_dotenv
import logging
from resume_filter.api import router as resume_router

load_dotenv()

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(resume_router)

@app.get("/health")
def health_check():
    return {"message": "Resume tracker application running successful"}


