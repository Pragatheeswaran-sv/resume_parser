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
    Users
)
from src.resume_filter.models import Resume
from src.services.nl_search.service import _execute_search, _load_search_session
load_dotenv()
logger = logging.getLogger(__name__)
db = SessionLocal()
def admin_dashboard(admin_id):
    try:
        # data = {}
        users = (
            db.query(
                func.json_build_object(
                    "total_users",
                    func.count().filter(
                        Users.is_active == True
                    ),

                    "active_users",
                    func.count().filter(
                        Users.is_blocked == False
                    )
                )
            )
            .select_from(Users)
            .scalar()
        )

        total_users = users["total_users"]
        active_users = users["active_users"]
        active_user_percentage = int((active_users /total_users) * 100)
        blocked_user_percentage = int((abs(active_users - total_users)/total_users) * 100)

        candidates = (
            db.query(
                func.count().filter(
                    Candidate.is_active == True
                )
            )
            .select_from(Candidate)
            .scalar()
        )

        roles = (
            db.query(
                Resume.candidate_role,
                func.count().label("role_count")
            )
            .group_by(Resume.candidate_role)
            .all()
        )

        role_data = [
            {
                "candidate_role": role.candidate_role,
                "no_of_candidate": role.role_count
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
                func.count(Resume.attachment_id).label("parsed_success_count"),

                func.count().filter(
                    Resume.attachment_id == None
                ).label("parsed_fail_count")
            )
            .select_from(Attachment)
            .outerjoin(
                Resume,
                Attachment.attachment_id == Resume.attachment_id
            )
            .first()
        )
        # print(parsed_count)

        shared_count = db.query(EmailShareLogs).all()
        print(shared_count)

        data = {
            "total_users": total_users,
            "active_users": active_users,
            "total_candidates": candidates,
            "active_user_percentage": f"{active_user_percentage}%",
            "blocked_user_percentage": f"{blocked_user_percentage}%",
            "roles": role_data,
            "recent_candidate": [
                candidate.candidate_info
                for candidate in recent_candidate
            ],
            "parsed_success_count": parsed_count.parsed_success_count,
            "parsed_fail_count": parsed_count.parsed_fail_count,
            "email_share_success_count" : len(shared_count)
        }

        return {
            "status" : status.HTTP_200_OK,
            "message": "admin dashboard retrieved successfully",
            "data" : data
        }
    except Exception as e:
        logger.error("[ERROR] in candidate fetch: %s", str(e), exc_info=True)
        raise Exception(f"Error at admin_dashboard: {str(e)}", status_code=500)
    finally:
        db.close()

