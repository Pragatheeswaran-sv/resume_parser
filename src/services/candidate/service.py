import os
import re
import json
import logging
import ollama
from dotenv import load_dotenv
from db.connection import SessionLocal
from src.resume_filter.models import Resume
from sqlalchemy import func, select, and_, cast, String, text
from sqlalchemy.dialects.postgresql import JSON
from src.candidate.models import Candidate, CandidateSkills, Skill, CandidateEducation, Education, Role, WorkExperience, Company

load_dotenv()
logger = logging.getLogger(__name__)
db = SessionLocal()

def candidate_datails(page):
    try:
        details = []

        per_page = 10
        offset = (int(page) - 1) * per_page

        candidate_education = (
            db.query(
                CandidateEducation.candidate_id.label("candidate_id"),
                func.json_agg(
                    func.json_build_object(
                        "education_id", Education.education_id,
                        "education", Education.education,
                        "institution", CandidateEducation.institution,
                        "percentage", CandidateEducation.percentage,
                        "year_of_passed", CandidateEducation.year_of_passed
                    )
                ).label("education")
            )
            .select_from(CandidateEducation)
            .join(Education, CandidateEducation.education_id == Education.education_id)
            .group_by(CandidateEducation.candidate_id)
            .subquery()
        )

        candidate_skills = (
            db.query(
                CandidateSkills.candidate_id.label("candidate_id"),
                func.json_agg(
                    func.json_build_object(
                        "skill_id", Skill.skill_id,
                        "skill", Skill.skill
                    )
                ).label("skills")
            )
            .select_from(CandidateSkills)
            .join(Skill, CandidateSkills.skill_id == Skill.skill_id)
            .group_by(CandidateSkills.candidate_id)
            .subquery()
        )
        
        candidate_work_exp = (
            db.query(
                WorkExperience.candidate_id.label("candidate_id"),
                func.json_agg(
                    func.json_build_object(
                        "role_id", Role.role_id,
                        "role", Role.role,
                        "company_name", Company.company_name,
                        "company_location", Company.company_location,
                        "start_date", WorkExperience.start_date,
                        "end_date", WorkExperience.end_date,
                        "is_present", WorkExperience.is_active
                    )
                ).label("work_experience")
            )
            .select_from(WorkExperience)
            .join(Role, WorkExperience.role_id == Role.role_id)
            .join(Company, WorkExperience.company_id == Company.company_id)
            .group_by(WorkExperience.candidate_id)
            .subquery()
        )
       
        data = (
            db.query(
                func.json_build_object(
                    "candidate_id", Candidate.candidate_id,
                    "name", Candidate.name,
                    "email", Candidate.email_address,
                    "phone_number", Candidate.phone_number,
                    "location", Candidate.location,
                    "total_experience", Candidate.total_experience,
                    "education", func.coalesce(candidate_education.c.education, cast('[]', JSON)),
                    "skills", func.coalesce(candidate_skills.c.skills, cast('[]', JSON)),
                    "work_experience", func.coalesce(candidate_work_exp.c.work_experience, cast('[]', JSON))
                ).label("candidate_info")
            )
            .select_from(Candidate)
            .outerjoin(candidate_education, Candidate.candidate_id == candidate_education.c.candidate_id)
            .outerjoin(candidate_skills, Candidate.candidate_id == candidate_skills.c.candidate_id)
            .outerjoin(candidate_work_exp, Candidate.candidate_id == candidate_work_exp.c.candidate_id)
            .filter(Candidate.is_active == True)
            .limit(per_page).offset(offset)
        )

        total_count = (
            db.query(func.count(Candidate.candidate_id))
            .filter(Candidate.is_active == True)
            .scalar()
        )

        if not data:
            return {"message": "Candidates not found"}
        
        
        for info in data:
            detail_dict = {}
            for key in info.candidate_info:
                detail_dict[key] = info.candidate_info[key]
            details.append(detail_dict)

        total ={}
        total['total_record'] = total_count
        details.append(total)

        return details

    except Exception as e:
        logger.info(f"[ERROR] in candidate fetch: {e}")