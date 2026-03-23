from sqlalchemy import Column, Integer, Text, Numeric, ARRAY, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from db.connection import Base
from src.email_reader.models import Email
from sqlalchemy.orm import relationship

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(Text)
    name = Column(Text)
    total_experience = Column(Numeric)
    skills = Column(ARRAY(Text))
    companies = Column(ARRAY(Text))
    education = Column(JSON)
    embedding = Column(Vector(384))
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    email_id = Column(Integer, ForeignKey("emails.id"))

    email = relationship("Email")