import logging
from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import func, cast, case
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.email_reader.models import EmailLogs, Attachment
from src.candidate.models import (
    Candidate, CandidateSkills, Skill, CandidateEducation,
    Education, Role, WorkExperience, Company,
)
from fastapi import APIRouter, Depends, HTTPException, status
from src.resume_share.models import EmailShareLogs
from src.admin.models import (
    ExtractionConfig,
    Users
)
from src.resume_filter.models import Resume
from src.services.nl_search.service import _execute_search, _load_search_session
load_dotenv()
logger = logging.getLogger(__name__)
db = SessionLocal()

def admin_dashboard(admin_id):
    try:
        users = (
            db.query(
                func.count(Users.user_id)
                .filter(Users.is_active == True)
                .label("total_users"),

                func.count(Users.user_id)
                .filter(
                    Users.is_active == True,
                    Users.is_blocked == False
                )
                .label("active_users")
            )
            .first()
        )

        total_users = users.total_users or 0
        active_users = users.active_users or 0
        blocked_users = total_users - active_users

        active_user_percentage = (
            round((active_users / total_users) * 100, 2)
            if total_users > 0 else 0
        )

        blocked_user_percentage = (
            round((blocked_users / total_users) * 100, 2)
            if total_users > 0 else 0
        )

        schedular = (
            db.query(ExtractionConfig)
            .filter(ExtractionConfig.is_active == True)
            .first()
        )

        if schedular:
            schedular_data = {
                "schedular_id": schedular.config_id,
                "schedule_type": schedular.schedule_type,
                "interval_minutes": schedular.interval_minutes,
                "weekday": schedular.weekday,
                "is_active": schedular.is_active,
            }


        total_candidates = (
            db.query(func.count(Candidate.candidate_id))
            .filter(Candidate.is_active == True)
            .scalar()
        )

        total_roles_count = (
            db.query(func.count(Resume.resume_id))
            .scalar()
        ) or 1

        roles = (
            db.query(
                Resume.candidate_role,

                func.count(Resume.resume_id)
                .label("role_count"),

                (
                    (
                        func.count(Resume.resume_id) * 100.0
                    ) / total_roles_count
                ).label("role_percentage")
            )
            .group_by(Resume.candidate_role)
            .order_by(func.count(Resume.resume_id).desc())
            .all()
        )

        role_data = [
            {
                "candidate_role": role.candidate_role,
                "no_of_candidate": role.role_count,
                "percentage": f"{round(role.role_percentage, 2)}%"
            }
            for role in roles
        ]

        recent_candidate = (
            db.query(
                func.json_build_object(
                    "candidate_id", Candidate.candidate_id,
                    "name", Candidate.name,
                    "email", Candidate.email_address,
                    "phone_number", Candidate.phone_number,
                    "location", Candidate.location,
                    "total_experience", Candidate.total_experience,
                    "parsed_user_name", Users.name
                ).label("candidate_info")
            )
            .select_from(Candidate)
            .join(
                Resume,
                Resume.candidate_id == Candidate.candidate_id
            )
            .join(
                Attachment,
                Attachment.attachment_id == Resume.attachment_id
            )
            .join(
                EmailLogs,
                EmailLogs.email_id == Attachment.email_id
            )
            .join(
                Users,
                Users.email_address == EmailLogs.source_mail
            )
            .order_by(Candidate.created_at.desc())
            .limit(5)
            .all()
        )

        parsed_count = (
            db.query(
                func.count(Resume.attachment_id)
                .label("parsed_success_count"),

                func.count(
                    case(
                        (Resume.attachment_id == None, 1)
                    )
                ).label("parsed_fail_count")
            )
            .select_from(Attachment)
            .outerjoin(
                Resume,
                Attachment.attachment_id == Resume.attachment_id
            )
            .first()
        )

        email_share_success_count = (
            db.query(func.count(EmailShareLogs.email_share_id))
            .scalar()
        )

        data = {
            "total_users": total_users,
            "active_users": active_users,
            "blocked_users": blocked_users,
            "total_candidates": total_candidates,
            "active_user_percentage": f"{active_user_percentage}%",
            "blocked_user_percentage": f"{blocked_user_percentage}%",
            "total_users_percentage": f"{active_user_percentage + blocked_user_percentage}%",
            "schedular_data": schedular_data,
            "roles": role_data,
            "recent_candidate": [
                candidate.candidate_info
                for candidate in recent_candidate
            ],
            "parsed_success_count": parsed_count.parsed_success_count,
            "parsed_fail_count": parsed_count.parsed_fail_count,
            "total_parsed_count" : parsed_count.parsed_fail_count + email_share_success_count,
            "email_share_success_count": email_share_success_count, 
        }

        return {
            "status": status.HTTP_200_OK,
            "message": "admin dashboard retrieved successfully",
            "data": data
        }

    except Exception as e:
        logger.error(
            "[ERROR] in admin dashboard: %s",
            str(e),
            exc_info=True
        )
        raise Exception(
            f"Error at admin_dashboard: {str(e)}"
        )

    finally:
        db.close()
