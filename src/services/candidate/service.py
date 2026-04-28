import logging
from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.candidate.models import (
    Candidate, CandidateSkills, Skill, CandidateEducation,
    Education, Role, WorkExperience, Company,
)
from src.resume_filter.models import Resume
from src.services.nl_search.service import _execute_search, _load_search_session
load_dotenv()
logger = logging.getLogger(__name__)

VALID_SORT_FIELDS = {"name", "experience", "year", "percentage"}


class CandidateServiceError(Exception):
    """Raised when candidate service encounters a recoverable business error."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def _validate_data(data) -> None:
    """Raise if the query returned no rows."""
    if not data:
        raise CandidateServiceError("No data found", status_code=404)


def _build_subqueries(db):
    """Build the reusable education / skills / work-experience subqueries."""

    candidate_education = (
        db.query(
            CandidateEducation.candidate_id.label("candidate_id"),
            func.json_agg(
                func.json_build_object(
                    "education_id", Education.education_id,
                    "education", Education.education,
                    "institution", CandidateEducation.institution,
                    "percentage", CandidateEducation.percentage,
                    "year_of_passed", CandidateEducation.year_of_passed,
                )
            ).label("education"),
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
                    "skill", Skill.skill,
                )
            ).label("skills"),
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
                    "is_present", WorkExperience.is_active,
                )
            ).label("work_experience"),
        )
        .select_from(WorkExperience)
        .join(Role, WorkExperience.role_id == Role.role_id)
        .join(Company, WorkExperience.company_id == Company.company_id)
        .group_by(WorkExperience.candidate_id)
        .subquery()
    )

    return candidate_education, candidate_skills, candidate_work_exp


def _base_candidate_query(db, edu_sq, skills_sq, work_sq):
    """Return the base query selecting json_build_object for candidate info."""
    return (
        db.query(
            func.json_build_object(
                "candidate_id", Candidate.candidate_id,
                "name", Candidate.name,
                "email", Candidate.email_address,
                "phone_number", Candidate.phone_number,
                "location", Candidate.location,
                "matching_role", Resume.candidate_role,
                "total_experience", Candidate.total_experience,
                "education", func.coalesce(edu_sq.c.education, cast("[]", JSON)),
                "skills", func.coalesce(skills_sq.c.skills, cast("[]", JSON)),
                "work_experience", func.coalesce(work_sq.c.work_experience, cast("[]", JSON)),
            ).label("candidate_info")
        )
        .select_from(Candidate)
        .outerjoin(edu_sq, Candidate.candidate_id == edu_sq.c.candidate_id)
        .outerjoin(skills_sq, Candidate.candidate_id == skills_sq.c.candidate_id)
        .outerjoin(work_sq, Candidate.candidate_id == work_sq.c.candidate_id)
        .outerjoin(Resume, Candidate.candidate_id == Resume.candidate_id)
        .filter(Candidate.is_active == True)
    )


def _extract_results(rows, total_count: int) -> list[dict]:
    """Unwrap SQLAlchemy rows into a plain list and append the total record count."""
    results = [row.candidate_info for row in rows]
    results.append({"total_record": total_count})
    return results


def candidate_datails(page, sort_by, sort_type) -> list[dict]:
    """Return paginated candidate details with optional sorting.

    Returns a list of candidate dicts with a trailing ``{"total_record": N}`` element.
    Raises ``CandidateServiceError`` for invalid parameters or empty results.
    """
    db = SessionLocal()
    try:
        per_page = 10
        offset = (int(page) - 1) * per_page

        candidate_education, candidate_skills, candidate_work_exp = _build_subqueries(db)

        total_count = (
            db.query(func.count(Candidate.candidate_id))
            .filter(Candidate.is_active == True)
            .scalar()
        ) or 0

        if total_count < offset:
            raise CandidateServiceError("Invalid page number", status_code=400)

        sort_type_resolved = sort_type if sort_type in ("asc", "desc") else "asc"

        if sort_by in (None, "None", ""):
            query = (
                _base_candidate_query(db, candidate_education, candidate_skills, candidate_work_exp)
                .limit(per_page).offset(offset)
            )
            data = query.all()
            _validate_data(data)
            return _extract_results(data, total_count)

        if sort_by == "name":
            return _sort_by_name(db, sort_type_resolved, candidate_education, candidate_skills, candidate_work_exp, per_page, offset, total_count)

        if sort_by == "experience":
            return _sort_by_experience(db, sort_type_resolved, candidate_education, candidate_skills, candidate_work_exp, per_page, offset, total_count)

        if sort_by == "year":
            return _sort_by_year(db, sort_type_resolved, candidate_skills, candidate_work_exp, per_page, offset, total_count)

        if sort_by == "percentage":
            return _sort_by_percentage(db, sort_type_resolved, candidate_education, candidate_skills, candidate_work_exp, per_page, offset, total_count)

        raise CandidateServiceError("Invalid sorting operation", status_code=400)

    except CandidateServiceError:
        raise
    except Exception as e:
        logger.error("[ERROR] in candidate fetch: %s", str(e), exc_info=True)
        raise CandidateServiceError(f"Failed to fetch candidates: {str(e)}", status_code=500)
    finally:
        db.close()


def _sort_by_name(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page, offset, total_count):
    order = Candidate.name.desc() if sort_type == "desc" else Candidate.name.asc()
    data = (
        _base_candidate_query(db, candidate_education, candidate_skills, candidate_work_exp)
        .order_by(order)
        .limit(per_page).offset(offset)
        .all()
    )
    _validate_data(data)
    return _extract_results(data, total_count)


def _sort_by_experience(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page, offset, total_count):
    order = Candidate.total_experience.desc() if sort_type == "desc" else Candidate.total_experience.asc()
    data = (
        _base_candidate_query(db, candidate_education, candidate_skills, candidate_work_exp)
        .order_by(order)
        .limit(per_page).offset(offset)
        .all()
    )
    _validate_data(data)
    return _extract_results(data, total_count)


def _sort_by_year(db, sort_type, candidate_skills, candidate_work_exp, per_page, offset, total_count):
    agg_func = func.max if sort_type == "desc" else func.min
    agg_order = CandidateEducation.year_of_passed.desc() if sort_type == "desc" else CandidateEducation.year_of_passed.asc()
    sort_order_col_dir = "desc" if sort_type == "desc" else "asc"

    passout_year_sq = (
        db.query(
            CandidateEducation.candidate_id.label("candidate_id"),
            agg_func(CandidateEducation.year_of_passed).label("latest_year"),
            func.json_agg(
                aggregate_order_by(
                    func.json_build_object(
                        "education_id", Education.education_id,
                        "education", Education.education,
                        "institution", CandidateEducation.institution,
                        "percentage", CandidateEducation.percentage,
                        "year_of_passed", CandidateEducation.year_of_passed,
                    ),
                    agg_order,
                )
            ).label("education"),
        )
        .join(Education, CandidateEducation.education_id == Education.education_id)
        .filter(~func.lower(Education.education).in_(["sslc", "hse"]))
        .group_by(CandidateEducation.candidate_id)
        .subquery()
    )

    order_col = passout_year_sq.c.latest_year.desc() if sort_order_col_dir == "desc" else passout_year_sq.c.latest_year.asc()

    data = (
        db.query(
            func.json_build_object(
                "candidate_id", Candidate.candidate_id,
                "name", Candidate.name,
                "email", Candidate.email_address,
                "phone_number", Candidate.phone_number,
                "location", Candidate.location,
                "total_experience", Candidate.total_experience,
                "education", func.coalesce(passout_year_sq.c.education, cast("[]", JSON)),
                "skills", func.coalesce(candidate_skills.c.skills, cast("[]", JSON)),
                "work_experience", func.coalesce(candidate_work_exp.c.work_experience, cast("[]", JSON)),
            ).label("candidate_info")
        )
        .select_from(Candidate)
        .outerjoin(passout_year_sq, Candidate.candidate_id == passout_year_sq.c.candidate_id)
        .outerjoin(candidate_skills, Candidate.candidate_id == candidate_skills.c.candidate_id)
        .outerjoin(candidate_work_exp, Candidate.candidate_id == candidate_work_exp.c.candidate_id)
        .filter(Candidate.is_active == True)
        .order_by(order_col)
        .limit(per_page)
        .offset(offset)
        .all()
    )
    _validate_data(data)
    return _extract_results(data, total_count)


def _sort_by_percentage(db, sort_type, candidate_education, candidate_skills, candidate_work_exp, per_page, offset, total_count):
    agg_func = func.max if sort_type == "desc" else func.min

    percentage_sq = (
        db.query(
            CandidateEducation.candidate_id.label("candidate_id"),
            agg_func(CandidateEducation.percentage).label("highest_percentage"),
        )
        .group_by(CandidateEducation.candidate_id)
        .subquery()
    )

    order = percentage_sq.c.highest_percentage.desc() if sort_type == "desc" else percentage_sq.c.highest_percentage.asc()

    data = (
        _base_candidate_query(db, candidate_education, candidate_skills, candidate_work_exp)
        .outerjoin(percentage_sq, Candidate.candidate_id == percentage_sq.c.candidate_id)
        .order_by(order)
        .limit(per_page)
        .offset(offset)
        .all()
    )
    _validate_data(data)
    return _extract_results(data, total_count)

def export_candidate(search_id, page, page_size, export):
    try:
        result = _load_search_session(search_id)
        resolved_filters = result["filters"]
        return _execute_search(
            resolved_filters, 
            page, 
            page_size, 
            sort_by = None, 
            sort_order =None,
            export = export)
    except Exception as e:
        logger.warning("[export_candidate] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
