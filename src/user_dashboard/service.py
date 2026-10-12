"""User dashboard service layer.

Provides aggregated analytics tailored to an individual authenticated user,
including parsed resumes count, last sync status, candidates, roles, skills,
experience distributions, and active AI model information.
"""

from contextlib import contextmanager
import logging
from typing import Any, Dict, Generator, Optional

from dotenv import load_dotenv
from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.connection import SessionLocal
from src.utils.helper import decrypt_data

load_dotenv()
logger = logging.getLogger(__name__)


# =============================================================================
# 1. Base Service
# =============================================================================

class BaseService:
    """Base service offering transactional DB session management."""

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    @contextmanager
    def get_session(self, session: Optional[Session] = None) -> Generator[Session, None, None]:
        """Provide a transactional database session scope."""
        if session is not None:
            yield session
            return
        if self._db is not None:
            yield self._db
            return
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


# =============================================================================
# 2. User Dashboard Service
# =============================================================================

class UserDashboardService(BaseService):
    """Handles user dashboard metrics aggregation."""

    def get_dashboard(self, user_mail: str, session: Optional[Session] = None) -> Dict[str, Any]:
        """Aggregate dashboard metrics for an authenticated user.

        Args:
            user_mail: Email address of the requesting user.
            session: Optional existing SQLAlchemy session.

        Returns:
            Dict containing aggregated candidates, experience, roles, scheduler,
            skills, recent candidates, active AI model, and user parsing statistics.
        """
        with self.get_session(session) as db:
            try:
                last_sync_query = text("""
                    SELECT last_processed_at AS last_sync
                    FROM oauth_credentials
                    WHERE email = :user_mail
                """)

                last_sync_data = db.execute(
                    last_sync_query,
                    {"user_mail": user_mail},
                ).fetchone()

                scheduler_query = text("""
                    SELECT
                        config_id,
                        schedule_type,
                        interval_minutes,
                        weekday,
                        is_active
                    FROM extraction_config
                    WHERE is_active = true
                    LIMIT 1
                """)

                scheduler_data = db.execute(
                    scheduler_query
                ).fetchone()

                candidate_query = text("""
                    SELECT COUNT(*) AS total_candidates
                    FROM candidates
                    WHERE is_active = true
                """)

                candidate_data = db.execute(
                    candidate_query
                ).fetchone()

                total_candidates = candidate_data.total_candidates if candidate_data else 0

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
                    2,
                )

                roles_data = [
                    {
                        "role": str(row.role).capitalize(),
                        "no_of_candidate": row.role_count,
                        "percentage": f"{row.percentage}%",
                    }
                    for row in top_roles
                ]

                if others_count > 0:
                    roles_data.append({
                        "role": "Others",
                        "no_of_candidate": others_count,
                        "percentage": f"{others_percentage}%",
                    })

                # ---------------- RECENT CANDIDATES ---------------- #

                recent_candidate_query = text("""
                    SELECT DISTINCT ON (c.candidate_id)
                        c.candidate_id,
                        c.name,
                        c.email_address,
                        c.phone_number,
                        c.location,
                        c.total_experience,
                        u.name AS parsed_user_name
                    FROM candidates c
                    JOIN resumes r
                        ON c.candidate_id = r.candidate_id
                    JOIN attachments a
                        ON a.attachment_id = r.attachment_id
                    JOIN email_logs e
                        ON e.email_id = a.email_id
                    JOIN users u
                        ON u.email_address = e.source_mail
                    ORDER BY c.candidate_id, c.created_at DESC
                    LIMIT 5
                """)

                recent_candidate_result = db.execute(
                    recent_candidate_query
                ).fetchall()

                recent_candidate_data = [
                    {
                        "candidate_id": row.candidate_id,
                        "name": row.name,
                        "email_address": row.email_address,
                        "phone_number": row.phone_number,
                        "location": row.location,
                        "total_experience": row.total_experience,
                    }
                    for row in recent_candidate_result
                ]

                # ---------------- EXPERIENCE DATA ---------------- #

                experience_query = text("""
                    SELECT
                        total_experience,
                        COUNT(candidate_id) AS count_of_experience,
                        ROUND(
                            COUNT(candidate_id) * 100.0
                            / SUM(COUNT(candidate_id)) OVER (),
                            2
                        ) AS percentage
                    FROM candidates
                    WHERE total_experience IS NOT NULL
                    GROUP BY total_experience
                    ORDER BY total_experience
                """)

                experience_result = db.execute(
                    experience_query
                ).fetchall()

                experience_data = [
                    {
                        "experience": exp.total_experience,
                        "no_of_candidate": exp.count_of_experience,
                        "percentage": f"{exp.percentage}%",
                    }
                    for exp in experience_result
                ]

                # ---------------- SKILL DATA ---------------- #

                skill_query = text("""
                    SELECT
                        LOWER(TRIM(s.skill)) AS skill,
                        COUNT(DISTINCT cs.candidate_id) AS candidate_count,
                        ROUND(
                            COUNT(DISTINCT cs.candidate_id) * 100.0
                            / SUM(COUNT(DISTINCT cs.candidate_id)) OVER (),
                            2
                        ) AS percentage
                    FROM skills s
                    JOIN candidate_skills cs
                        ON cs.skill_id = s.skill_id
                    WHERE s.skill IS NOT NULL
                    AND TRIM(s.skill) <> ''
                    GROUP BY LOWER(TRIM(s.skill))
                    ORDER BY candidate_count DESC
                """)

                skill_result = db.execute(
                    skill_query
                ).fetchall()

                top_skills = skill_result[:10]

                top_skill_count = sum(
                    skill.candidate_count for skill in top_skills
                )

                top_skill_percentage = sum(
                    skill.percentage for skill in top_skills
                )

                total_skill_count = sum(
                    skill.candidate_count for skill in skill_result
                )

                others_skill_count = total_skill_count - top_skill_count

                others_skill_percentage = round(
                    100 - top_skill_percentage,
                    2,
                )

                skill_data = [
                    {
                        "skill": str(skill.skill).capitalize(),
                        "no_of_candidate": skill.candidate_count,
                        "percentage": f"{skill.percentage}%",
                    }
                    for skill in top_skills
                ]

                if others_skill_count > 0:
                    skill_data.append({
                        "skill": "Others",
                        "no_of_candidate": others_skill_count,
                        "percentage": f"{others_skill_percentage}%",
                    })

                # ---------------- ACTIVE MODEL ---------------- #

                active_model_query = text("""
                    SELECT
                        c.ai_model_config_id,
                        m.ai_model_id,
                        m.model_name,
                        v.ai_model_version_id,
                        v.version_name,
                        c.apikey,
                        c.max_tokens,
                        c.temparature,
                        c.admin_id,
                        c.is_active
                    FROM ai_model_configs c
                    JOIN ai_models m
                        ON m.ai_model_id = c.ai_model_id
                    JOIN ai_model_version v
                        ON v.ai_model_version_id = c.ai_model_version_id
                    WHERE c.is_active = true
                """)

                active_model = db.execute(
                    active_model_query
                ).fetchone()

                active_model_data = None

                if active_model:
                    raw_key = active_model.apikey
                    decrypted_key = None

                    try:
                        decrypted_key = decrypt_data(raw_key)
                        if isinstance(decrypted_key, bytes):
                            decrypted_key = decrypted_key.decode("utf-8")
                    except Exception:
                        if isinstance(raw_key, bytes):
                            decrypted_key = raw_key.decode("utf-8", errors="ignore")
                        else:
                            decrypted_key = str(raw_key)

                    masked_api_key = (
                        decrypted_key[:2]
                        + "******"
                        + decrypted_key[-2:]
                        if decrypted_key and len(decrypted_key) > 4
                        else "******"
                    )

                    active_model_data = {
                        "model_config_id": active_model.ai_model_config_id,
                        "model_id": active_model.ai_model_id,
                        "model_name": active_model.model_name,
                        "version_id": active_model.ai_model_version_id,
                        "version_name": active_model.version_name,
                        "apikey": masked_api_key,
                        "max_tokens": active_model.max_tokens,
                        "admin_id": active_model.admin_id,
                        "is_active": active_model.is_active,
                    }

                # ---------------- PARSED MAIL COUNT ---------------- #

                parsed_mail_count_query = text("""
                    SELECT
                        COUNT(DISTINCT c.candidate_id) AS count_by_user
                    FROM candidates c
                    JOIN resumes r
                        ON r.candidate_id = c.candidate_id
                    JOIN attachments a
                        ON a.attachment_id = r.attachment_id
                    JOIN email_logs e
                        ON e.email_id = a.email_id
                    WHERE e.source_mail = :user_mail
                """)

                parsed_mail_count = db.execute(
                    parsed_mail_count_query,
                    {"user_mail": user_mail},
                ).fetchone()

                # ---------------- EMAIL SHARE COUNT ---------------- #

                email_query = text("""
                    SELECT COUNT(*) AS share_count
                    FROM email_notification
                """)

                email_data = db.execute(
                    email_query
                ).fetchone()

                # ---------------- FINAL RESPONSE ---------------- #

                data = {
                    "total_candidates": total_candidates,
                    "resume_parsed_by_user": parsed_mail_count.count_by_user if parsed_mail_count else 0,
                    "last_sync_at": last_sync_data.last_sync if last_sync_data else None,
                    "experience": experience_data,
                    "active_ai_model": active_model_data,
                    "roles": roles_data,
                    "scheduler_data": {
                        "scheduler_id": scheduler_data.config_id if scheduler_data else None,
                        "schedule_type": scheduler_data.schedule_type if scheduler_data else None,
                        "interval_minutes": scheduler_data.interval_minutes if scheduler_data else None,
                        "weekday": scheduler_data.weekday if scheduler_data else None,
                        "is_active": scheduler_data.is_active if scheduler_data else None,
                    },
                    "skills": skill_data,
                    "recent_candidate": recent_candidate_data,
                    "email_shared_count": email_data.share_count if email_data else 0,
                }

                return {
                    "status": status.HTTP_200_OK,
                    "message": "user dashboard retrieved successfully",
                    "data": data,
                }

            except Exception as e:
                logger.error("[ERROR] in user dashboard: %s", str(e), exc_info=True)
                raise Exception(f"Error at user_dashboard: {str(e)}")

    def user_dashboard(self, user_mail: str, session: Optional[Session] = None) -> Dict[str, Any]:
        """Backward-compatible alias for get_dashboard."""
        return self.get_dashboard(user_mail, session=session)


# Global singleton instance
user_dashboard_service = UserDashboardService()


# =============================================================================
# 3. Backward-Compatible Function Exports
# =============================================================================

def user_dashboard(user_mail: str) -> Dict[str, Any]:
    return user_dashboard_service.get_dashboard(user_mail)


__all__ = [
    "BaseService",
    "UserDashboardService",
    "user_dashboard_service",
    "user_dashboard",
]