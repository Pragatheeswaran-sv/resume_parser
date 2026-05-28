import os
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
import logging
from db.connection import engine, Base
from src.resume_filter.api import router as resume_router
from src.email_reader.api import router as email_router
from src.candidate.api import router as candidate_route
from src.admin.api import router as admin_route
from src.admin.dependencies import AllowedEmailMiddleware
from fastapi.middleware.cors import CORSMiddleware
from src.auth.api import router as auth_router
from src.resume_download.api import router as resume_download_router
from src.resume_share.api import router as resume_share_router
from src.resume_share.admin_api import router as email_config_router
from src.admin_dashboard.api import router as admin_dashboard
from src.user_dashboard.api import router as user_dashboard
from src.client_track.api import router as client

 
load_dotenv()

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Resume Tracker API",
    description="API for tracking, filtering, and searching candidate resumes.",
    version="1.0.0",
)
app.include_router(resume_router)
app.include_router(email_router)
app.include_router(candidate_route)
app.include_router(admin_route)
app.include_router(auth_router)
app.include_router(resume_download_router)
app.include_router(resume_share_router)
app.include_router(email_config_router)
app.include_router(admin_dashboard)
app.include_router(user_dashboard)
app.include_router(client)

app.add_middleware(AllowedEmailMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a structured 422 response for Pydantic / FastAPI validation errors."""
    logger.warning("Request validation error: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Request validation failed",
            "errors": [
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in exc.errors()
            ],
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler that logs the full traceback and returns a safe 500 response."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
    )


@app.on_event("startup")
def startup():
    """Initialize database tables on application startup."""

    Base.metadata.create_all(bind=engine)
    logger.info("Database ready")

@app.get("/health")
def health_check() -> dict:
    """Simple health check endpoint."""
    return {"message": "Resume tracker application running successful"}