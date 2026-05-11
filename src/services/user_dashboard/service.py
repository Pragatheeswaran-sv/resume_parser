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
from src.auth.models import OauthCredentials
from fastapi import APIRouter, Depends, HTTPException, status
from src.resume_share.models import EmailShareLogs
from src.admin.models import (
    AiModel, AiModelversion, Users, AiModelConfig, ExtractionConfig
)
from src.resume_filter.models import Resume
from src.services.nl_search.service import _execute_search, _load_search_session
from src.utils.helper import decrypt_data
load_dotenv()
logger = logging.getLogger(__name__)
db = SessionLocal()

def user_dashboard(user_mail):
    try:

        candidates = (
            db.query(func.count(Candidate.candidate_id))
            .filter(Candidate.is_active == True)
            .scalar()
        )

        experience_data = [
            {
                "experience": row.total_experience,
                "no_of_candidate": row.candidate_count,
                "percentage": (
                    f"{round((row.candidate_count / candidates) * 100, 2)}%"
                    if candidates > 0 else "0%"
                )
            }
            for row in (
                db.query(
                    Candidate.total_experience,
                    func.count(Candidate.candidate_id).label("candidate_count")
                )
                .group_by(Candidate.total_experience)
                .all()
            )
        ]    

        role_data = [
            {
                "candidate_role": row.candidate_role,
                "no_of_candidate": row.role_count,
                "percentage": (
                    f"{round((row.role_count / candidates) * 100, 2)}%"
                    if candidates > 0 else "0%"
                )
            }
            for row in (
                db.query(
                    Resume.candidate_role,
                    func.count().label("role_count")
                )
                .group_by(Resume.candidate_role)
                .all()
            )
        ]

        recent_candidate = [
            row.candidate_info
            for row in (
                db.query(
                    func.json_build_object(
                        "candidate_id", Candidate.candidate_id,
                        "name", Candidate.name,
                        "email", Candidate.email_address,
                        "phone_number", Candidate.phone_number,
                        "location", Candidate.location,
                        "total_experience", Candidate.total_experience,
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
        ]

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

        shared_count = db.query(func.count(EmailShareLogs.email_share_id)).scalar()

        active_model = (
            db.query(
                func.json_build_object(
                    "model_config_id", AiModelConfig.ai_model_config_id,
                    "model_id", AiModelConfig.ai_model_id,
                    "model_name", AiModel.model_name,
                    "model_version_id", AiModelversion.ai_model_version_id,
                    "model_version_name", AiModelversion.version_name,
                    "apikey", AiModelConfig.apikey,
                    "max_tokens", AiModelConfig.max_tokens,
                    "admin_id", AiModelConfig.admin_id,
                    "is_active", AiModelConfig.is_active
                )
            )
            .select_from(AiModelConfig)
            .join(
                AiModel,
                AiModel.ai_model_id == AiModelConfig.ai_model_id
            )
            .join(
                AiModelversion,
                AiModelversion.ai_model_version_id == AiModelConfig.ai_model_version_id
            )
            .filter(AiModelConfig.is_active == True)
            .scalar()
        )

        active_model_data = {}

        if active_model:

            raw_key = active_model["apikey"]
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
                decrypted_key[:2] + "******" + decrypted_key[-2:]
                if decrypted_key and len(decrypted_key) > 4
                else "******"
            )

            active_model_data = {
                "model_config_id": active_model["model_config_id"],
                "model_id": active_model["model_id"],
                "model_name": active_model["model_name"],
                "version_id": active_model["model_version_id"],
                "version_name": active_model["model_version_name"],
                "apikey": masked_api_key,
                "max_tokens": active_model["max_tokens"],
                "admin_id": active_model["admin_id"],
                "is_active": active_model["is_active"]
            }

        last_sync_at = (
            db.query(OauthCredentials.last_processed_at)
            .filter(OauthCredentials.email == user_mail)
            .scalar()
        )

        skill_data = [
            {
                "skills": row.skill,
                "no_of_candidate": row.candidate_count,
                "percentage": (
                    f"{round((row.candidate_count / candidates) * 100, 2)}%"
                    if candidates > 0 else "0%"
                )
            }
            for row in (
                db.query(
                    Skill.skill,
                    func.count(
                        func.distinct(Candidate.candidate_id)
                    ).label("candidate_count")
                )
                .join(
                    CandidateSkills,
                    CandidateSkills.skill_id == Skill.skill_id
                )
                .join(
                    Candidate,
                    Candidate.candidate_id == CandidateSkills.candidate_id
                )
                .group_by(Skill.skill)
                .all()
            )
        ]

        scheduler = (
            db.query(ExtractionConfig)
            .filter(ExtractionConfig.is_active == True)
            .first()
        )


        if scheduler:
            scheduler_data = {
                "scheduler_id": scheduler.config_id,
                "schedule_type": scheduler.schedule_type,
                "interval_minutes": scheduler.interval_minutes,
                "weekday": scheduler.weekday,
                "is_active": scheduler.is_active,
            }

        parsed_by_user = (
            db.query(func.count(Candidate.candidate_id))
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
            .filter(
                EmailLogs.source_mail == user_mail
            )
            .scalar()
        )

        data = {
            "total_candidates": candidates,
            "resume_parsed_by_user": parsed_by_user,
            "last_sync_at": last_sync_at,
            "experience": experience_data,
            "active_ai_model": active_model_data,
            "roles": role_data,
            "scheduler_data": scheduler_data,
            "skills": skill_data,
            "recent_candidate": recent_candidate,
            "parsed_success_count": parsed_count.parsed_success_count,
            "parsed_fail_count": parsed_count.parsed_fail_count,
            "total_parsed_count": parsed_count.parsed_success_count + parsed_count.parsed_fail_count,
            "email_shared_count": shared_count
        }

        return {
            "status": status.HTTP_200_OK,
            "message": "user dashboard retrieved successfully",
            "data": data
        }

    except Exception as e:
        logger.error(
            "[ERROR] in user dashboard: %s",
            str(e),
            exc_info=True
        )
        raise Exception(
            f"Error at user_dashboard: {str(e)}"
        )

    finally:
        db.close()