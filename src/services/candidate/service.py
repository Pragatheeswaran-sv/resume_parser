import logging
from fastapi.responses import JSONResponse
import ollama
from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.candidate.models import Candidate, CandidateSkills, Skill, CandidateEducation, Education, Role, WorkExperience, Company

load_dotenv()
logger = logging.getLogger(__name__)

def candidate_datails(page, sort_by, sort_type):
    try:
        db = SessionLocal()
        details = []

        per_page = 10
        offset = (int(page) - 1) * per_page
        print(offset)

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

        total_count = (
            db.query(func.count(Candidate.candidate_id))
            .filter(Candidate.is_active == True)
            .scalar()
        )

        if total_count < offset:
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": "Invalid page number"
                }
            )
        
        if sort_by == "None" and sort_type == "None":
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

            valid = validate_data(data)
            if valid != None:
                return valid        
            
            for info in data:
                detail_dict = {}
                for key in info.candidate_info:
                    detail_dict[key] = info.candidate_info[key]
                details.append(detail_dict)

            total ={}
            total['total_record'] = total_count
            details.append(total)

            return details
        
        elif sort_by == 'name':
            if sort_type == 'desc':
                return sort_by_name(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count)
            return sort_by_name(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count)
        
        elif sort_by == 'experience':
            if sort_type == 'desc':
                return sort_by_experience(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count)
            return sort_by_experience(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count)
        
        elif sort_by == 'year':
            if sort_type == 'desc':
                return sort_by_year(db, sort_type, candidate_skills, candidate_work_exp, per_page,offset, total_count)
            return sort_by_year(db, sort_type, candidate_skills, candidate_work_exp, per_page,offset, total_count)

        elif sort_by == 'percentage':
            if sort_type == 'desc':
                return sort_by_percentage(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count)
            return sort_by_percentage(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count)
        
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "status": False,
                    "message": "Invalid sorting operation"
                }
            )
        
    except Exception as e:
        logger.info(f"[ERROR] in candidate fetch: {e}")
        return JSONResponse(
                status_code=404,
                content={
                    "status": False,
                    "message": str(e)
                }
            )
    finally:
        db.close()


def sort_by_name(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count):
    if sort_type == 'desc':
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
            .order_by(Candidate.name.desc())
            .limit(per_page).offset(offset)
        )

        valid = validate_data(data)
        if valid != None:
            return valid
        
        candidate_names_desc = [row.candidate_info for row in data]
        total ={}
        total['total_record'] = total_count
        candidate_names_desc.append(total)
        return candidate_names_desc
    
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
            .order_by(Candidate.name.asc())
            .limit(per_page).offset(offset)
        )
    
    valid = validate_data(data)
    if valid != None:
        return valid
    candidate_names_asc = [row.candidate_info for row in data]
    total ={}
    total['total_record'] = total_count
    candidate_names_asc.append(total)
    return candidate_names_asc


def sort_by_experience(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count):
    if sort_type == 'desc':
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
            .order_by(Candidate.total_experience.desc())
            .limit(per_page).offset(offset)
        )

        valid = validate_data(data)
        if valid != None:
            return valid
        
        candidate_experience_desc = [row.candidate_info for row in data]
        total ={}
        total['total_record'] = total_count
        candidate_experience_desc.append(total)
        return candidate_experience_desc
    
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
            .order_by(Candidate.total_experience.asc())
            .limit(per_page).offset(offset)
        )
    
    valid = validate_data(data)
    if valid != None:
        return valid
    
    candidate_experience_asc = [row.candidate_info for row in data]
    total ={}
    total['total_record'] = total_count
    candidate_experience_asc.append(total)
    return candidate_experience_asc

def sort_by_year(db, sort_type, candidate_skills, candidate_work_exp, per_page,offset, total_count):
    if sort_type == 'desc':

        passout_year_dec = (
            db.query(
                CandidateEducation.candidate_id.label("candidate_id"),
                func.max(CandidateEducation.year_of_passed).label("latest_year"),
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            "education_id", Education.education_id,
                            "education", Education.education,
                            "institution", CandidateEducation.institution,
                            "percentage", CandidateEducation.percentage,
                            "year_of_passed", CandidateEducation.year_of_passed
                        ),
                        CandidateEducation.year_of_passed.desc()
                    )
                ).label("education")
            )
            .join(Education, CandidateEducation.education_id == Education.education_id)
            .filter(~func.lower(Education.education).in_(["sslc", "hse"]))
            .group_by(CandidateEducation.candidate_id)
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
                    "education", func.coalesce(passout_year_dec.c.education, cast('[]', JSON)),
                    "skills", func.coalesce(candidate_skills.c.skills, cast('[]', JSON)),
                    "work_experience", func.coalesce(candidate_work_exp.c.work_experience, cast('[]', JSON))
                ).label("candidate_info")
            )
            .select_from(Candidate)
            .outerjoin(passout_year_dec, Candidate.candidate_id == passout_year_dec.c.candidate_id)
            .outerjoin(candidate_skills, Candidate.candidate_id == candidate_skills.c.candidate_id)
            .outerjoin(candidate_work_exp, Candidate.candidate_id == candidate_work_exp.c.candidate_id)
            .filter(Candidate.is_active == True)
            .order_by(passout_year_dec.c.latest_year.desc())
            .limit(per_page)
            .offset(offset)
            .all()
        )

        valid = validate_data(data)
        if valid != None:
            return valid
        
        candidate_passout_year_dec = [row.candidate_info for row in data]
        total ={}
        total['total_record'] = total_count
        candidate_passout_year_dec.append(total)
        return candidate_passout_year_dec
    
    passout_year_asc = (
            db.query(
                CandidateEducation.candidate_id.label("candidate_id"),
                func.min(CandidateEducation.year_of_passed).label("latest_year"),
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            "education_id", Education.education_id,
                            "education", Education.education,
                            "institution", CandidateEducation.institution,
                            "percentage", CandidateEducation.percentage,
                            "year_of_passed", CandidateEducation.year_of_passed
                        ),
                        CandidateEducation.year_of_passed.asc()
                    )
                ).label("education")
            )
            .join(Education, CandidateEducation.education_id == Education.education_id)
            .filter(~func.lower(Education.education).in_(["sslc", "hse"]))
            .group_by(CandidateEducation.candidate_id)
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
                "education", func.coalesce(passout_year_asc.c.education, cast('[]', JSON)),
                "skills", func.coalesce(candidate_skills.c.skills, cast('[]', JSON)),
                "work_experience", func.coalesce(candidate_work_exp.c.work_experience, cast('[]', JSON))
            ).label("candidate_info")
        )
        .select_from(Candidate)
        .outerjoin(passout_year_asc, Candidate.candidate_id == passout_year_asc.c.candidate_id)
        .outerjoin(candidate_skills, Candidate.candidate_id == candidate_skills.c.candidate_id)
        .outerjoin(candidate_work_exp, Candidate.candidate_id == candidate_work_exp.c.candidate_id)
        .filter(Candidate.is_active == True)
        .order_by(passout_year_asc.c.latest_year.asc())
        .limit(per_page)
        .offset(offset)
        .all()
    )

    valid = validate_data(data)
    if valid != None:
        return valid
    
    candidate_passout_year_asc = [row.candidate_info for row in data]
    total ={}
    total['total_record'] = total_count
    candidate_passout_year_asc.append(total)
    return candidate_passout_year_asc

def sort_by_percentage(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page,offset, total_count):
    if sort_type == 'desc':

        percentage_sort_desc = (
            db.query(
                CandidateEducation.candidate_id.label("candidate_id"),
                func.max(CandidateEducation.percentage).label("highest_percentage")
            )
            .group_by(CandidateEducation.candidate_id)
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
            .outerjoin(percentage_sort_desc, Candidate.candidate_id == percentage_sort_desc.c.candidate_id)
            .filter(Candidate.is_active == True)
            .order_by(percentage_sort_desc.c.highest_percentage.desc())
            .limit(per_page)
            .offset(offset)
            .all()
        )

        valid = validate_data(data)
        if valid != None:
            return valid

        candidate_percentage_sort_desc = [row.candidate_info for row in data]
        total ={}
        total['total_record'] = total_count
        candidate_percentage_sort_desc.append(total)
        return candidate_percentage_sort_desc     

    percentage_sort_asc = (
            db.query(
                CandidateEducation.candidate_id.label("candidate_id"),
                func.min(CandidateEducation.percentage).label("highest_percentage")
            )
            .group_by(CandidateEducation.candidate_id)
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
        .outerjoin(percentage_sort_asc, Candidate.candidate_id == percentage_sort_asc.c.candidate_id)
        .filter(Candidate.is_active == True)
        .order_by(percentage_sort_asc.c.highest_percentage.asc())
        .limit(per_page)
        .offset(offset)
        .all()
    )

    valid = validate_data(data)
    if valid != None:
        return valid
    
    candidate_percentage_sort_asc = [row.candidate_info for row in data]
    total ={}
    total['total_record'] = total_count
    candidate_percentage_sort_asc.append(total)
    return candidate_percentage_sort_asc

def validate_data(data):
    if not data:
        return JSONResponse(
            status_code=404,
            content={
                "status": False,
                "message": "No data found"
            }
        )
    return None