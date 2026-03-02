import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

logger = logging.getLogger(__name__)

# DATABASE_URL_value = os.getenv("DATABASE_URL")
# DATABASE_URL_value =  "postgresql://postgres:2023@db:5432/resume_tracker"
DATABASE_URL_value = "postgresql://postgres:2023@db:5432/resume_tracker"


logger.info(f"NAV----> Tue db url is {DATABASE_URL_value}")

engine = create_engine(DATABASE_URL_value)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()