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
from src.auth.models import OauthCredentials
from fastapi import APIRouter, Depends, HTTPException, status
from src.resume_share.models import EmailNotification
from src.admin.models import (
    AiModel, AiModelversion, Users, AiModelConfig, ExtractionConfig
)
from src.resume_filter.models import Resume
from src.services.nl_search.service import _execute_search, _load_search_session
from src.utils.helper import decrypt_data
load_dotenv()
logger = logging.getLogger(__name__)
db = SessionLocal()

# def user_dashboard(user_mail):
#     try:

#         candidates = (
#             db.query(func.count(Candidate.candidate_id))
#             .filter(Candidate.is_active == True)
#             .scalar()
#         )

#         experience_data = [
#             {
#                 "experience": row.total_experience,
#                 "no_of_candidate": row.candidate_count,
#                 "percentage": (
#                     f"{round((row.candidate_count / candidates) * 100, 2)}%"
#                     if candidates > 0 else "0%"
#                 )
#             }
#             for row in (
#                 db.query(
#                     Candidate.total_experience,
#                     func.count(Candidate.candidate_id).label("candidate_count")
#                 )
#                 .group_by(Candidate.total_experience)
#                 .all()
#             )
#         ]    

#         role_data = [
#             {
#                 "candidate_role": row.candidate_role,
#                 "no_of_candidate": row.role_count,
#                 "percentage": (
#                     f"{round((row.role_count / candidates) * 100, 2)}%"
#                     if candidates > 0 else "0%"
#                 )
#             }
#             for row in (
#                 db.query(
#                     Resume.candidate_role,
#                     func.count().label("role_count")
#                 )
#                 .group_by(Resume.candidate_role)
#                 .all()
#             )
#         ]

#         recent_candidate = [
#             row.candidate_info
#             for row in (
#                 db.query(
#                     func.json_build_object(
#                         "candidate_id", Candidate.candidate_id,
#                         "name", Candidate.name,
#                         "email", Candidate.email_address,
#                         "phone_number", Candidate.phone_number,
#                         "location", Candidate.location,
#                         "total_experience", Candidate.total_experience,
#                     ).label("candidate_info")
#                 )
#                 .select_from(Candidate)
#                 .join(
#                     Resume,
#                     Resume.candidate_id == Candidate.candidate_id
#                 )
#                 .join(
#                     Attachment,
#                     Attachment.attachment_id == Resume.attachment_id
#                 )
#                 .join(
#                     EmailLogs,
#                     EmailLogs.email_id == Attachment.email_id
#                 )
#                 .join(
#                     Users,
#                     Users.email_address == EmailLogs.source_mail
#                 )
#                 .order_by(Candidate.created_at.desc())
#                 .limit(5)
#                 .all()
#             )
#         ]

#         parsed_count = (
#             db.query(
#                 func.count(Resume.attachment_id).label("parsed_success_count"),

#                 func.count().filter(
#                     Resume.attachment_id == None
#                 ).label("parsed_fail_count")
#             )
#             .select_from(Attachment)
#             .outerjoin(
#                 Resume,
#                 Attachment.attachment_id == Resume.attachment_id
#             )
#             .first()
#         )

#         shared_count = db.query(func.count(EmailNotification.email_share_id)).scalar()

#         active_model = (
#             db.query(
#                 func.json_build_object(
#                     "model_config_id", AiModelConfig.ai_model_config_id,
#                     "model_id", AiModelConfig.ai_model_id,
#                     "model_name", AiModel.model_name,
#                     "model_version_id", AiModelversion.ai_model_version_id,
#                     "model_version_name", AiModelversion.version_name,
#                     "apikey", AiModelConfig.apikey,
#                     "max_tokens", AiModelConfig.max_tokens,
#                     "admin_id", AiModelConfig.admin_id,
#                     "is_active", AiModelConfig.is_active
#                 )
#             )
#             .select_from(AiModelConfig)
#             .join(
#                 AiModel,
#                 AiModel.ai_model_id == AiModelConfig.ai_model_id
#             )
#             .join(
#                 AiModelversion,
#                 AiModelversion.ai_model_version_id == AiModelConfig.ai_model_version_id
#             )
#             .filter(AiModelConfig.is_active == True)
#             .scalar()
#         )

#         active_model_data = {}

#         if active_model:

#             raw_key = active_model["apikey"]
#             decrypted_key = None

#             try:
                
#                 decrypted_key = decrypt_data(raw_key)
#                 if isinstance(decrypted_key, bytes):
#                     decrypted_key = decrypted_key.decode("utf-8")
#             except Exception:
#                 if isinstance(raw_key, bytes):
#                     decrypted_key = raw_key.decode("utf-8", errors="ignore")
#                 else:
#                     decrypted_key = str(raw_key)

#             masked_api_key = (
#                 decrypted_key[:2] + "******" + decrypted_key[-2:]
#                 if decrypted_key and len(decrypted_key) > 4
#                 else "******"
#             )

#             active_model_data = {
#                 "model_config_id": active_model["model_config_id"],
#                 "model_id": active_model["model_id"],
#                 "model_name": active_model["model_name"],
#                 "version_id": active_model["model_version_id"],
#                 "version_name": active_model["model_version_name"],
#                 "apikey": masked_api_key,
#                 "max_tokens": active_model["max_tokens"],
#                 "admin_id": active_model["admin_id"],
#                 "is_active": active_model["is_active"]
#             }

#         last_sync_at = (
#             db.query(OauthCredentials.last_processed_at)
#             .filter(OauthCredentials.email == user_mail)
#             .scalar()
#         )

#         skill_data = [
#             {
#                 "skills": row.skill,
#                 "no_of_candidate": row.candidate_count,
#                 "percentage": (
#                     f"{round((row.candidate_count / candidates) * 100, 2)}%"
#                     if candidates > 0 else "0%"
#                 )
#             }
#             for row in (
#                 db.query(
#                     Skill.skill,
#                     func.count(
#                         func.distinct(Candidate.candidate_id)
#                     ).label("candidate_count")
#                 )
#                 .join(
#                     CandidateSkills,
#                     CandidateSkills.skill_id == Skill.skill_id
#                 )
#                 .join(
#                     Candidate,
#                     Candidate.candidate_id == CandidateSkills.candidate_id
#                 )
#                 .group_by(Skill.skill)
#                 .all()
#             )
#         ]

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

#         parsed_by_user = (
#             db.query(func.count(Candidate.candidate_id))
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
#             .filter(
#                 EmailLogs.source_mail == user_mail
#             )
#             .scalar()
#         )

#         data = {
#             "total_candidates": candidates,
#             "resume_parsed_by_user": parsed_by_user,
#             "last_sync_at": last_sync_at,
#             "experience": experience_data,
#             "active_ai_model": active_model_data,
#             "roles": role_data,
#             "scheduler_data": scheduler_data,
#             "skills": skill_data,
#             "recent_candidate": recent_candidate,
#             "parsed_success_count": parsed_count.parsed_success_count,
#             "parsed_fail_count": parsed_count.parsed_fail_count,
#             "total_parsed_count": parsed_count.parsed_success_count + parsed_count.parsed_fail_count,
#             "email_shared_count": shared_count
#         }

#         return {
#             "status": status.HTTP_200_OK,
#             "message": "user dashboard retrieved successfully",
#             "data": data
#         }

#     except Exception as e:
#         logger.error(
#             "[ERROR] in user dashboard: %s",
#             str(e),
#             exc_info=True
#         )
#         raise Exception(
#             f"Error at user_dashboard: {str(e)}"
#         )

#     finally:
#         db.close()




def user_dashboard(user_mail):
    try:

        last_sync_query = text("""
            SELECT last_processed_at AS last_sync
            FROM oauth_credentials
            WHERE email = :user_mail
        """)

        last_sync_data = db.execute(
            last_sync_query,
            {"user_mail": user_mail}
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
                "total_experience": row.total_experience
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
                "percentage": f"{exp.percentage}%"
            }
            for exp in experience_result
        ]

        # ---------------- SKILL DATA ---------------- #

        # skill_query = text("""
        #     SELECT
        #         LOWER(TRIM(s.skill)) AS skill,
        #         COUNT(DISTINCT cs.candidate_id) AS candidate_count,
        #         ROUND(
        #             COUNT(DISTINCT cs.candidate_id) * 100.0
        #             / SUM(COUNT(DISTINCT cs.candidate_id)) OVER (),
        #             2
        #         ) AS percentage
        #     FROM skills s
        #     JOIN candidate_skills cs
        #         ON cs.skill_id = s.skill_id
        #     WHERE s.skill IS NOT NULL
        #     AND TRIM(s.skill) <> ''
        #     GROUP BY LOWER(TRIM(s.skill))
        #     ORDER BY candidate_count DESC
        #     limit 10
        # """)

        # skill_result = db.execute(
        #     skill_query
        # ).fetchall()

        # skill_data = [
        #     {
        #         "skill": skill.skill,
        #         "no_of_candidate": skill.candidate_count,
        #         "percentage": f"{skill.percentage}%"
        #     }
        #     for skill in skill_result
        # ]


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

        others_count = total_skill_count - top_skill_count

        others_percentage = round(
            100 - top_skill_percentage,
            2
        )

        skill_data = [
            {
                "skill": skill.skill,
                "no_of_candidate": skill.candidate_count,
                "percentage": f"{skill.percentage}%"
            }
            for skill in top_skills
        ]

        if others_count > 0:
            skill_data.append({
                "skill": "others",
                "no_of_candidate": others_count,
                "percentage": f"{others_percentage}%"
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
                    decrypted_key = raw_key.decode(
                        "utf-8",
                        errors="ignore"
                    )
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
                "is_active": active_model.is_active
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
            {"user_mail": user_mail}
        ).fetchone()

        # ---------------- PARSED STATUS ---------------- #

        parsed_query = text("""
            SELECT
                COUNT(r.attachment_id) AS parsed_success_count,
                COUNT(*) FILTER (
                    WHERE r.attachment_id IS NULL
                ) AS parsed_fail_count
            FROM attachments a
            LEFT JOIN resumes r
                ON a.attachment_id = r.attachment_id
        """)

        parsed_data = db.execute(
            parsed_query
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
            "resume_parsed_by_user": parsed_mail_count.count_by_user,
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
            "parsed_success_count": parsed_data.parsed_success_count,
            "parsed_fail_count": parsed_data.parsed_fail_count,
            "total_parsed_count": parsed_data.parsed_success_count + parsed_data.parsed_fail_count,
            "email_shared_count": email_data.share_count
        }

        return {
            "status": status.HTTP_200_OK,
            "message": "user dashboard retrieved successfully",
            "data": data
        }

    except Exception as e:
        logger.error("[ERROR] in user dashboard: %s", str(e), exc_info=True)
        raise Exception(f"Error at user_dashboard: {str(e)}")

    finally:
        db.close()