"""Admin dashboard service layer.

Provides aggregated analytics across users, extraction scheduling,
candidate statistics, role distributions, skill distributions, and recent parsing logs.
"""

from contextlib import contextmanager
import logging
from typing import Any, Dict, Generator, Optional

from dotenv import load_dotenv
from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.connection import SessionLocal

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
# 2. Admin Dashboard Service
# =============================================================================

class AdminDashboardService(BaseService):
    """Handles admin dashboard analytics aggregation."""

    def get_dashboard(self, admin_id: Any, session: Optional[Session] = None) -> Dict[str, Any]:
        """Aggregate system-wide metrics and stats for the admin dashboard.

        Args:
            admin_id: ID of the authenticated admin requesting dashboard stats.
            session: Optional existing SQLAlchemy session.

        Returns:
            Dict containing aggregated user, schedule, candidate, role, skill,
            and email share metrics.
        """
        with self.get_session(session) as db:
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
                    2
                )

                roles_data = [
                    {
                        "role": str(row.role).capitalize(),
                        "no_of_candidate": row.role_count,
                        "percentage": f"{row.percentage}%"
                    }
                    for row in top_roles
                ]

                if others_count > 0:
                    roles_data.append({
                        "role": "Others",
                        "no_of_candidate": others_count,
                        "percentage": f"{others_percentage}%"
                    })

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

                skill_result = db.execute(skill_query).fetchall()

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

                others_count = total_skill_count - top_skill_count

                others_percentage = round(
                    100 - top_skill_percentage,
                    2
                )

                skill_data = [
                    {
                        "skill": str(skill.skill).capitalize(),
                        "no_of_candidate": skill.candidate_count,
                        "percentage": f"{skill.percentage}%"
                    }
                    for skill in top_skills
                ]

                if others_count > 0:
                    skill_data.append({
                        "skill": "Others",
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
                    "skills": skill_data,
                    "recent_candidate": recent_candidate_data,
                    "email_share_success_count": email_data.share_count if email_data else 0
                }

                return {
                    "status": status.HTTP_200_OK,
                    "message": "admin dashboard retrieved successfully",
                    "data": data
                }

            except Exception as e:
                logger.error("[ERROR] in admin dashboard: %s", str(e), exc_info=True)
                raise Exception(f"Error at admin_dashboard: {str(e)}")

    def admin_dashboard(self, admin_id: Any, session: Optional[Session] = None) -> Dict[str, Any]:
        """Backward-compatible alias for get_dashboard."""
        return self.get_dashboard(admin_id, session=session)


# Global singleton instance
admin_dashboard_service = AdminDashboardService()


# =============================================================================
# 3. Backward-Compatible Function Exports
# =============================================================================

def admin_dashboard(admin_id: Any) -> Dict[str, Any]:
    """Backward-compatible function export delegating to admin_dashboard_service."""
    return admin_dashboard_service.get_dashboard(admin_id)


__all__ = [
    "BaseService",
    "AdminDashboardService",
    "admin_dashboard_service",
    "admin_dashboard",
]
