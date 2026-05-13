import logging
from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import func, cast, case, text
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.email_reader.models import EmailLogs, Attachment
from src.candidate.models import (
    Candidate, CandidateSkills, Skill, CandidateEducation,
    Education, Role, WorkExperience, Company,
)
from fastapi import APIRouter, Depends, HTTPException, status
from src.resume_share.models import EmailNotification
from src.admin.models import (
    ExtractionConfig,
    Users
)
from src.resume_filter.models import Resume
from src.services.nl_search.service import _execute_search, _load_search_session
load_dotenv()
logger = logging.getLogger(__name__)
db = SessionLocal()

# def admin_dashboard(admin_id):
#     try:
#         users = (
#             db.query(
#                 func.count(Users.user_id)
#                 .filter(Users.is_active == True)
#                 .label("total_users"),

#                 func.count(Users.user_id)
#                 .filter(
#                     Users.is_active == True,
#                     Users.is_blocked == False
#                 )
#                 .label("active_users")
#             )
#             .first()
#         )

#         total_users = users.total_users or 0
#         active_users = users.active_users or 0
#         blocked_users = total_users - active_users

#         active_user_percentage = (
#             round((active_users / total_users) * 100, 2)
#             if total_users > 0 else 0
#         )

#         blocked_user_percentage = (
#             round((blocked_users / total_users) * 100, 2)
#             if total_users > 0 else 0
#         )

#         scheduler = (
#             db.query(ExtractionConfig)
#             .filter(ExtractionConfig.is_active == True)
#             .first()
#         )

#         if scheduler:
#             scheduler_data = {
#                 "scheduler_id": scheduler.config_id,
#                 "schedule_type": scheduler.schedule_type,
#                 "interval_minutes": scheduler.interval_minutes,
#                 "weekday": scheduler.weekday,
#                 "is_active": scheduler.is_active,
#             }


#         total_candidates = (
#             db.query(func.count(Candidate.candidate_id))
#             .filter(Candidate.is_active == True)
#             .scalar()
#         )

#         total_roles_count = (
#             db.query(func.count(Resume.resume_id))
#             .scalar()
#         ) or 1

#         roles = (
#             db.query(
#                 Resume.candidate_role,

#                 func.count(Resume.resume_id)
#                 .label("role_count"),

#                 (
#                     (
#                         func.count(Resume.resume_id) * 100.0
#                     ) / total_roles_count
#                 ).label("role_percentage")
#             )
#             .group_by(Resume.candidate_role)
#             .order_by(func.count(Resume.resume_id).desc())
#             .all()
#         )

#         role_data = [
#             {
#                 "candidate_role": role.candidate_role,
#                 "no_of_candidate": role.role_count,
#                 "percentage": f"{round(role.role_percentage, 2)}%"
#             }
#             for role in roles
#         ]

#         recent_candidate = (
#             db.query(
#                 func.json_build_object(
#                     "candidate_id", Candidate.candidate_id,
#                     "name", Candidate.name,
#                     "email", Candidate.email_address,
#                     "phone_number", Candidate.phone_number,
#                     "location", Candidate.location,
#                     "total_experience", Candidate.total_experience,
#                     "parsed_user_name", Users.name
#                 ).label("candidate_info")
#             )
#             .select_from(Candidate)
#             .join(
#                 Resume,
#                 Resume.candidate_id == Candidate.candidate_id
#             )
#             .join(
#                 Attachment,
#                 Attachment.attachment_id == Resume.attachment_id
#             )
#             .join(
#                 EmailLogs,
#                 EmailLogs.email_id == Attachment.email_id
#             )
#             .join(
#                 Users,
#                 Users.email_address == EmailLogs.source_mail
#             )
#             .order_by(Candidate.created_at.desc())
#             .limit(5)
#             .all()
#         )

#         parsed_count = (
#             db.query(
#                 func.count(Resume.attachment_id)
#                 .label("parsed_success_count"),

#                 func.count(
#                     case(
#                         (Resume.attachment_id == None, 1)
#                     )
#                 ).label("parsed_fail_count")
#             )
#             .select_from(Attachment)
#             .outerjoin(
#                 Resume,
#                 Attachment.attachment_id == Resume.attachment_id
#             )
#             .first()
#         )

#         email_share_success_count = (
#             db.query(func.count(EmailNotification.email_share_id))
#             .scalar()
#         )

#         data = {
#             "total_users": total_users,
#             "active_users": active_users,
#             "blocked_users": blocked_users,
#             "total_candidates": total_candidates,
#             "active_user_percentage": f"{active_user_percentage}%",
#             "blocked_user_percentage": f"{blocked_user_percentage}%",
#             "total_users_percentage": f"{active_user_percentage + blocked_user_percentage}%",
#             "scheduler_data": scheduler_data,
#             "roles": role_data,
#             "recent_candidate": [
#                 candidate.candidate_info
#                 for candidate in recent_candidate
#             ],
#             "parsed_success_count": parsed_count.parsed_success_count,
#             "parsed_fail_count": parsed_count.parsed_fail_count,
#             "total_parsed_count" : parsed_count.parsed_fail_count + email_share_success_count,
#             "email_share_success_count": email_share_success_count, 
#         }

#         return {
#             "status": status.HTTP_200_OK,
#             "message": "admin dashboard retrieved successfully",
#             "data": data
#         }

#     except Exception as e:
#         logger.error(
#             "[ERROR] in admin dashboard: %s",
#             str(e),
#             exc_info=True
#         )
#         raise Exception(
#             f"Error at admin_dashboard: {str(e)}"
#         )

#     finally:
#         db.close()


def admin_dashboard(admin_id):

    try:
        user_query = text("""
            SELECT 
                COUNT(*) AS total_users,
                COUNT(*) FILTER (WHERE is_blocked = false) AS active_users,
                COUNT(*) FILTER (WHERE is_blocked = true) AS blocked_users
            FROM users
            WHERE is_active = true
        """)

        user_data = db.execute(user_query).fetchone()

        total_users = user_data.total_users or 0
        active_users = user_data.active_users or 0
        blocked_users = user_data.blocked_users or 0

        active_user_percentage = round(
            (active_users / total_users) * 100, 2
        ) if total_users else 0

        blocked_user_percentage = round(
            (blocked_users / total_users) * 100, 2
        ) if total_users else 0

        scheduler_query = text("""
            SELECT config_id, schedule_type, interval_minutes, weekday, is_active
            FROM extraction_config
            WHERE is_active = true
            LIMIT 1
        """)

        scheduler_data = db.execute(scheduler_query).fetchone()

        candidate_query = text("""
            SELECT COUNT(*) AS total_candidates
            FROM candidates
            WHERE is_active = true
        """)

        candidate_data = db.execute(candidate_query).fetchone()

        total_candidates = candidate_data.total_candidates

        role_query = text("""
            SELECT
                LOWER(TRIM(candidate_role)) AS role,
                COUNT(*) AS role_count,
                ROUND(
                    COUNT(*) * 100.0
                    / SUM(COUNT(*)) OVER (),
                    2
                ) AS percentage
            FROM resumes
            WHERE candidate_role IS NOT NULL
            AND TRIM(candidate_role) <> ''
            GROUP BY LOWER(TRIM(candidate_role))
            ORDER BY role_count DESC
        """)

        role_result = db.execute(role_query).fetchall()

        top_roles = role_result[:5]

        top_role_count = sum(
            row.role_count for row in top_roles
        )

        top_role_percentage = sum(
            row.percentage for row in top_roles
        )

        total_role_count = sum(
            row.role_count for row in role_result
        )

        others_count = total_role_count - top_role_count

        others_percentage = round(
            100 - top_role_percentage,
            2
        )

        roles_data = [
            {
                "role": row.role,
                "no_of_candidate": row.role_count,
                "percentage": f"{row.percentage}%"
            }
            for row in top_roles
        ]

        if others_count > 0:
            roles_data.append({
                "role": "others",
                "no_of_candidate": others_count,
                "percentage": f"{others_percentage}%"
            })


        recent_candidate_query = text("""
            SELECT c.candidate_id, c.name, c.email_address, c.phone_number, c.location, c.total_experience, u.name AS parsed_user_name
            FROM candidates c
            JOIN resumes r ON c.candidate_id = r.candidate_id
            JOIN attachments a ON a.attachment_id = r.attachment_id
            JOIN email_logs e ON e.email_id = a.email_id
            JOIN users u ON u.email_address = e.source_mail
            ORDER BY c.created_at DESC
            LIMIT 5
        """)

        recent_candidate_result = db.execute(recent_candidate_query).fetchall()

        recent_candidate_data = [
            {
                "candidate_id": row.candidate_id,
                "name": row.name,
                "email_address": row.email_address,
                "phone_number": row.phone_number,
                "location": row.location,
                "total_experience": row.total_experience,
                "parsed_user_name": row.parsed_user_name
            }
            for row in recent_candidate_result
        ]

        parsed_query = text("""
            SELECT
                COUNT(r.attachment_id) AS parsed_success_count,             
                COUNT(
                    CASE
                        WHEN r.attachment_id IS NULL THEN 1
                    END
                ) AS parsed_fail_count
            FROM attachments a
            LEFT JOIN resumes r ON a.attachment_id = r.attachment_id
        """)

        parsed_data = db.execute(parsed_query).fetchone()

        email_query = text("""
            SELECT COUNT(*) AS share_count
            FROM email_notification
        """)

        email_data = db.execute(email_query).fetchone()

        data = {
            "total_users": total_users,
            "active_users": active_users,
            "blocked_users": blocked_users,
            "active_user_percentage": f"{active_user_percentage}%",
            "blocked_user_percentage": f"{blocked_user_percentage}%",
            "total_candidates": total_candidates,
            "scheduler_data": {
                "scheduler_id": scheduler_data.config_id if scheduler_data else None,
                "schedule_type": scheduler_data.schedule_type if scheduler_data else None,
                "interval_minutes": scheduler_data.interval_minutes if scheduler_data else None,
                "weekday": scheduler_data.weekday if scheduler_data else None,
                "is_active": scheduler_data.is_active if scheduler_data else None,
            },
            "roles": roles_data,
            "recent_candidate": recent_candidate_data,
            "parsed_success_count": parsed_data.parsed_success_count,
            "parsed_fail_count": parsed_data.parsed_fail_count,
            "total_parsed_count": (parsed_data.parsed_success_count + parsed_data.parsed_fail_count),
            "email_share_success_count": email_data.share_count
        }

        return {
            "status": status.HTTP_200_OK,
            "message": "admin dashboard retrieved successfully",
            "data": data
        }

    except Exception as e:
        logger.error( "[ERROR] in admin dashboard: %s", str(e), exc_info=True)
        raise Exception(f"Error at admin_dashboard: {str(e)}")
    finally:
        db.close()
