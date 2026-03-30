import uuid
from sqlalchemy import UUID, Column, Float, Integer, String, DateTime, ForeignKey, Boolean, Text, Date
from sqlalchemy.orm import relationship
from db.connection import Base
import datetime
from zoneinfo import ZoneInfo

def ist_now():
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))

class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    name = Column(Text)
    email_address = Column(String(255), nullable=True)
    email_from_sender = Column(Boolean, default=False)
    phone_number = Column(String(20), nullable=True)
    location = Column(String(255), nullable=True)
    total_experience = Column(Integer)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class Education(Base):
    __tablename__ = "education"

    education_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    education = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class CandidateEducation(Base):
    __tablename__ = "candidate_education"

    candidate_education_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.candidate_id"), nullable = True)
    institution = Column(String(255), nullable=True)
    percentage = Column(Float)
    year_of_passed = Column(Integer)
    education_id = Column(UUID(as_uuid=True), ForeignKey("education.education_id"), nullable = True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)


    candidate = relationship("Candidate")
    education = relationship("Education")


class Skill(Base):
    __tablename__ = "skills"

    skill_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    skill = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

    # candidate_skills = relationship("CandidateSkills")

class CandidateSkills(Base):
    __tablename__ = "candidate_skills"

    candidate_skills_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.candidate_id"), nullable=False)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.skill_id"), nullable=False)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

    candidate = relationship("Candidate")
    skill = relationship("Skill")

class Role(Base):
    __tablename__ = "roles"

    role_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    role = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class Company(Base):
    __tablename__ = "company"

    company_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False, unique=True)
    company_location = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class WorkExperience(Base):
    __tablename__ = "work_experience"

    experience_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.candidate_id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.company_id"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.role_id"), nullable=False)
    start_date =  Column(Date, default=datetime.date.today)
    end_date =  Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

    candidate = relationship("Candidate")
    company = relationship("Company")
    role = relationship("Role")