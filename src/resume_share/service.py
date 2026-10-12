import datetime
import logging
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from db.connection import SessionLocal
from src.candidate.models import (
    Candidate,
    CandidateEducation,
    CandidateSkills,
    Education,
    Skill,
    WorkExperience,
    Company,
    Role,
    Resume,
)
from src.email_reader.models import Attachment
from src.resume_share.models import (
    EmailNotification,
    EmailProviderConfig,
    EmailTemplate,
    ist_now,
)
from src.integrations.email_sender import email_sender_service
from src.utils.response import (
    internal_server_error_response,
    serialize_response,
    error_response,
    not_found_response,
)

logger = logging.getLogger(__name__)

ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR", "attachments")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ResumeShareError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ResumeShareService:
    """Consolidated service class for resume sharing, email providers, and email templates."""

    def _fetch_candidate_details(self, db: Session, candidate_id: str) -> dict:
        """Return a dict of candidate fields; only populated values are included."""
        candidate = db.query(Candidate).filter_by(candidate_id=candidate_id).first()
        if not candidate:
            raise ResumeShareError("Candidate not found", status_code=404)

        details = {}
        if candidate.name:
            details["name"] = candidate.name
        if candidate.email_address:
            details["email"] = candidate.email_address
        if candidate.phone_number:
            details["phone"] = candidate.phone_number
        if candidate.location:
            details["location"] = candidate.location
        if candidate.total_experience is not None:
            details["total_experience"] = f"{candidate.total_experience} Years"

        educations = (
            db.query(Education.education, CandidateEducation.institution)
            .join(
                CandidateEducation,
                Education.education_id == CandidateEducation.education_id,
            )
            .filter(CandidateEducation.candidate_id == candidate_id)
            .all()
        )
        if educations:
            edu_parts = []
            for edu in educations:
                part = edu.education
                if edu.institution:
                    part += f" ({edu.institution})"
                edu_parts.append(part)
            details["education"] = ", ".join(edu_parts)

        skills = (
            db.query(Skill.skill)
            .join(CandidateSkills, Skill.skill_id == CandidateSkills.skill_id)
            .filter(CandidateSkills.candidate_id == candidate_id)
            .all()
        )
        if skills:
            details["skills"] = ", ".join(s.skill for s in skills)

        work_exps = (
            db.query(
                Role.role,
                Company.company_name,
                WorkExperience.start_date,
                WorkExperience.end_date,
            )
            .join(WorkExperience, Role.role_id == WorkExperience.role_id)
            .join(Company, Company.company_id == WorkExperience.company_id)
            .filter(WorkExperience.candidate_id == candidate_id)
            .order_by(WorkExperience.start_date.desc())
            .all()
        )
        if work_exps:
            exp_parts = []
            for we in work_exps:
                end = we.end_date.strftime("%b %Y") if we.end_date else "Present"
                start = we.start_date.strftime("%b %Y") if we.start_date else ""
                exp_parts.append(f"{we.role} at {we.company_name} ({start} - {end})")
            details["work_experience"] = "; ".join(exp_parts)
            details["current_company"] = work_exps[0].company_name
            details["job_role"] = work_exps[0].role

        return details

    def _fetch_resume_and_attachment(
        self, db: Session, resume_id: str, candidate_id: str
    ) -> tuple:
        """Return (file_path, file_name, candidate_role) for the given resume."""
        resume = db.query(Resume).filter_by(resume_id=resume_id).first()
        if not resume:
            raise ResumeShareError("Resume not found", status_code=404)

        if str(resume.candidate_id) != str(candidate_id):
            raise ResumeShareError(
                "Resume does not belong to the specified candidate", status_code=400
            )

        if not resume.attachment_id:
            raise ResumeShareError("Resume has no attached file", status_code=404)

        attachment = (
            db.query(Attachment).filter_by(attachment_id=resume.attachment_id).first()
        )
        if not attachment:
            raise ResumeShareError("Attachment record not found", status_code=404)

        file_path = os.path.join(ATTACHMENT_DIR, attachment.file_name)
        if not os.path.exists(file_path):
            raise ResumeShareError(
                f"Attachment file not found on disk: {attachment.file_name}",
                status_code=404,
            )

        return file_path, attachment.file_name, resume.candidate_role

    def _render_template(self, template_body: str, candidate_details: dict) -> str:
        """Render the email template, omitting any field whose value is empty/None."""
        field_labels = {
            "name": "Name",
            "email": "Email",
            "phone": "Phone Number",
            "job_role": "Job Role",
            "location": "Location",
            "total_experience": "Total Experience",
            "education": "Education",
            "skills": "Skills",
            "work_experience": "Work Experience",
            "current_company": "Current Company",
            "notice_period": "Notice Period",
            "current_ctc": "Current CTC",
            "expected_ctc": "Expected CTC",
        }

        rendered_fields = []
        for key, label in field_labels.items():
            value = candidate_details.get(key)
            if value:
                rendered_fields.append(f"<b>{label}:</b> {value}")

        fields_html = "<br>".join(rendered_fields)

        result = template_body
        result = result.replace("{{candidate_fields}}", fields_html)

        for key, label in field_labels.items():
            placeholder = "{{" + key + "}}"
            value = candidate_details.get(key)
            if value:
                result = result.replace(placeholder, f"<b>{label}:</b> {value}")
            else:
                lines = result.split("\n")
                lines = [line for line in lines if placeholder not in line]
                result = "\n".join(lines)

        return result

    def share_resume_via_email(
        self,
        candidate_id: str,
        resume_id: str,
        to_address: str,
        share_log_id,
        cc_address: Optional[List[str]] = None,
    ) -> dict:
        """Orchestrate fetching data, rendering template, and sending email."""
        db = SessionLocal()
        try:
            logger.info(
                "Share resume request received — candidate=%s, resume=%s, to=%s",
                candidate_id,
                resume_id,
                to_address,
            )

            provider_config = db.query(EmailProviderConfig).filter_by(active=True).first()
            if not provider_config:
                raise ResumeShareError(
                    "No active email provider configuration found", status_code=400
                )
            logger.info("Email provider selected: %s", provider_config.provider_name)

            candidate_details = self._fetch_candidate_details(db, candidate_id)
            logger.info(
                "Candidate fetched: %s", candidate_details.get("name", candidate_id)
            )

            file_path, file_name, candidate_role = self._fetch_resume_and_attachment(
                db, resume_id, candidate_id
            )
            if candidate_role and "job_role" not in candidate_details:
                candidate_details["job_role"] = candidate_role
            logger.info("Resume attachment resolved: %s", file_name)

            template = db.query(EmailTemplate).filter_by(is_active=True).first()
            if not template:
                raise ResumeShareError("No active email template found", status_code=404)
            logger.info("Template loaded: %s", template.template_name)

            email_body = self._render_template(template.body, candidate_details)

            candidate_name = candidate_details.get("name", "Candidate")
            subject = template.subject or f"Resume - {candidate_name}"
            subject = subject.replace("{{name}}", candidate_name)

            ext = os.path.splitext(file_name)[1] or ".pdf"
            friendly_filename = candidate_name.strip().replace(" ", "_") + "_Resume" + ext

            email_notification = (
                db.query(EmailNotification)
                .filter(EmailNotification.email_share_id == share_log_id)
                .first()
            )
            if email_notification is not None:
                email_notification.subject = subject
                email_notification.mail_body = email_body
                db.add(email_notification)
                db.commit()
                db.refresh(email_notification)

            config_dict = {
                "provider_name": provider_config.provider_name,
                "from_email": provider_config.from_email,
                "host": provider_config.host,
                "port": provider_config.port,
                "username": provider_config.username,
                "password": provider_config.password,
                "tls_enabled": provider_config.tls_enabled,
            }

            result = email_sender_service.send_email(
                config=config_dict,
                to_address=to_address,
                cc_address=cc_address,
                subject=subject,
                html_body=email_body,
                attachment_path=file_path,
                attachment_filename=friendly_filename,
            )

            if not result["success"]:
                logger.error("Email send failed: %s", result.get("error"))
                raise ResumeShareError(
                    f"Email send failed: {result.get('error')}", status_code=500
                )

            logger.info("Email sent successfully: %s", result)
            logger.info("Email sent successfully — message_id=%s", result["message_id"])
            return {
                "success": True,
                "message": "Email sent successfully",
                "email_id": result["message_id"],
            }

        finally:
            db.close()

    def share_resume_email(
        self,
        candidate_id: str,
        resume_id: str,
        to_address: str,
        cc_address: Optional[Any] = None,
        share: bool = False,
    ) -> dict:
        """Validate request, create EmailNotification record, and queue Celery task."""
        from src.celery.tasks import share_mail_to_client

        db = SessionLocal()
        try:
            share_log = (
                db.query(EmailNotification)
                .filter(
                    EmailNotification.resume_id == resume_id,
                    EmailNotification.to_address == to_address,
                )
                .order_by(EmailNotification.created_at.desc())
                .first()
            )

            date = datetime.datetime.now()
            past_five_days = date - datetime.timedelta(days=7)
            if share_log and share_log.created_at > past_five_days and not share:
                return {
                    "success": False,
                    "message": f"Candidate profile already shared to {to_address} at {share_log.created_at}",
                    "email_id": "",
                }

            share_log = EmailNotification(
                resume_id=resume_id,
                to_address=to_address,
                cc_address=str(cc_address) if cc_address else None,
            )

            db.add(share_log)
            db.commit()
            db.refresh(share_log)

            cc_list = cc_address if isinstance(cc_address, list) else ([str(cc_address)] if cc_address else None)
            share_mail_to_client.delay(
                candidate_id=str(candidate_id),
                resume_id=str(resume_id),
                to_address=to_address,
                cc_address=cc_list,
                share_log_id=str(share_log.email_share_id),
            )

            return {
                "success": True,
                "message": "resume shared successfully",
                "email_id": to_address,
            }
        finally:
            db.close()

    def retry_share_emails(self, email_share_ids: List[str]) -> dict:
        """Manually retry multiple failed email shares."""
        from src.celery.tasks import share_mail_to_client

        db = SessionLocal()
        try:
            if not email_share_ids:
                return {
                    "success": False,
                    "message": "No email_share_ids provided",
                    "results": [],
                }

            results = []
            queued_count = 0
            skipped_count = 0

            for i, email_share_id in enumerate(email_share_ids):
                share_log = (
                    db.query(EmailNotification)
                    .filter(EmailNotification.email_share_id == email_share_id)
                    .first()
                )

                if not share_log:
                    results.append(
                        {
                            "email_share_id": email_share_id,
                            "success": False,
                            "message": "Email share log not found",
                        }
                    )
                    skipped_count += 1
                    continue

                if share_log.status not in ("failed",):
                    results.append(
                        {
                            "email_share_id": email_share_id,
                            "success": False,
                            "message": f"Cannot retry — current status is '{share_log.status}'. Only 'failed' emails can be retried.",
                        }
                    )
                    skipped_count += 1
                    continue

                share_log.retry_count = 0
                share_log.status = "Pending"
                share_log.failed_at = None
                share_log.updated_at = ist_now()
                db.flush()

                share_mail_to_client.apply_async(
                    args=(
                        str(share_log.resume.candidate_id),
                        str(share_log.resume_id),
                        share_log.to_address,
                        share_log.cc_address.split(",") if share_log.cc_address else None,
                        str(share_log.email_share_id),
                    ),
                    countdown=i * 15,
                )

                results.append(
                    {
                        "email_share_id": email_share_id,
                        "success": True,
                        "message": "Retry queued successfully",
                    }
                )
                queued_count += 1

            db.commit()

            return {
                "success": queued_count > 0,
                "message": f"{queued_count} email(s) queued for retry, {skipped_count} skipped",
                "results": results,
            }
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def _serialize_provider_config(self, config: EmailProviderConfig) -> dict:
        """Convert an EmailProviderConfig row to a JSON-safe dict."""
        return {
            "id": str(config.id),
            "provider_name": config.provider_name,
            "from_email": config.from_email,
            "host": config.host,
            "port": config.port,
            "username": config.username,
            "password": config.password,
            "tls_enabled": config.tls_enabled,
            "active": config.active,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

    def create_email_provider_config(self, payload: dict) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            errors = []

            if not isinstance(payload, dict):
                return error_response(
                    400, [{"field": "payload", "message": "Payload must be a dictionary"}]
                )

            provider_name = (payload.get("provider_name") or "").strip()
            from_email = (payload.get("from_email") or "").strip()
            host = payload.get("host")
            port = payload.get("port")
            username = payload.get("username")
            password = payload.get("password")
            is_active = payload.get("active", False)
            tls_enabled = payload.get("tls_enabled", True)

            if not provider_name:
                errors.append({
                    "field": "provider_name",
                    "message": "provider_name is required",
                })

            if not from_email:
                errors.append({
                    "field": "from_email",
                    "message": "from_email is required",
                })
            elif not EMAIL_REGEX.match(from_email):
                errors.append({
                    "field": "from_email",
                    "message": "Invalid email format",
                })

            allowed_providers = {"SMTP", "SENDGRID", "SES", "MAILGUN"}
            provider_name_upper = provider_name.upper() if provider_name else ""

            if provider_name and provider_name_upper not in allowed_providers:
                errors.append({
                    "field": "provider_name",
                    "message": f"Invalid provider. Allowed: {list(allowed_providers)}",
                })

            if provider_name_upper == "SMTP":
                if not host:
                    errors.append({
                        "field": "host",
                        "message": "host is required for SMTP provider",
                    })

                if port is None:
                    errors.append({
                        "field": "port",
                        "message": "port is required for SMTP provider",
                    })
                else:
                    try:
                        port = int(port)
                        if port <= 0 or port > 65535:
                            errors.append({
                                "field": "port",
                                "message": "port must be between 1 and 65535",
                            })
                    except Exception:
                        errors.append({
                            "field": "port",
                            "message": "port must be a valid integer",
                        })

            if errors:
                return error_response(400, errors)

            duplicate = (
                session.query(EmailProviderConfig)
                .filter(EmailProviderConfig.from_email == from_email)
                .first()
            )

            if duplicate:
                return error_response(
                    409,
                    [{
                        "field": "provider_name",
                        "message": f"Provider '{from_email}' already exists",
                    }],
                )

            if is_active:
                session.query(EmailProviderConfig).filter(
                    EmailProviderConfig.active.is_(True)
                ).update(
                    {EmailProviderConfig.active: False},
                    synchronize_session=False,
                )
                logger.info("Deactivated all existing email provider configs")

            new_config = EmailProviderConfig(
                provider_name=provider_name,
                from_email=from_email,
                host=host,
                port=port,
                username=username,
                password=password,
                tls_enabled=bool(tls_enabled),
                active=bool(is_active),
            )

            session.add(new_config)
            session.commit()
            session.refresh(new_config)

            logger.info("Admin created email provider config id=%s", new_config.id)

            return {
                "status": status.HTTP_201_CREATED,
                "message": "Email provider config created successfully",
                "data": self._serialize_provider_config(new_config),
            }

        except Exception as e:
            session.rollback()
            logger.error("[create_email_provider_config] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def list_email_provider_configs(
        self,
        page,
        page_size,
        filter_column,
        filter_by,
        sort_by,
        sort_order,
    ) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            errors = []
            allowed_columns = {
                "provider_name": EmailProviderConfig.provider_name,
                "from_email": EmailProviderConfig.from_email,
                "host": EmailProviderConfig.host,
                "port": EmailProviderConfig.port,
                "username": EmailProviderConfig.username,
                "active": EmailProviderConfig.active,
            }

            if page is None:
                errors.append({"field": "page", "message": "page is required"})
            elif not isinstance(page, int) or page < 1:
                errors.append({"field": "page", "message": "page must be a positive integer"})

            if page_size is None:
                errors.append({"field": "page_size", "message": "page_size is required"})
            elif not isinstance(page_size, int) or page_size < 1:
                errors.append({"field": "page_size", "message": "page_size must be a positive integer"})
            elif page_size > 100:
                errors.append({"field": "page_size", "message": "page_size cannot exceed 100"})

            if filter_column:
                if filter_column not in allowed_columns:
                    errors.append({
                        "field": "filter_column",
                        "message": f"Invalid filter_column. Allowed values: {', '.join(allowed_columns.keys())}",
                    })
                if filter_by in [None, ""]:
                    errors.append({
                        "field": "filter_by",
                        "message": "filter_by is required when filter_column is provided",
                    })

            if sort_by:
                if sort_by not in allowed_columns:
                    errors.append({
                        "field": "sort_by",
                        "message": f"Invalid sort_by. Allowed values: {', '.join(allowed_columns.keys())}",
                    })

            if sort_order:
                sort_order = sort_order.lower()
                if sort_order not in ["asc", "desc"]:
                    errors.append({
                        "field": "sort_order",
                        "message": "sort_order must be either 'asc' or 'desc'",
                    })

            if errors:
                return error_response(400, errors)

            query = session.query(EmailProviderConfig)

            if filter_column and filter_by:
                column = allowed_columns[filter_column]
                query = query.filter(column.ilike(f"%{filter_by}%"))

            total_records = query.count()

            if sort_by:
                sort_column = allowed_columns[sort_by]
                if sort_order == "desc":
                    query = query.order_by(desc(sort_column))
                else:
                    query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(EmailProviderConfig.created_at))

            offset = (page - 1) * page_size
            configs = query.offset(offset).limit(page_size).all()

            if not configs:
                return not_found_response("email_provider_congigs", "No data found")

            return {
                "status": status.HTTP_200_OK,
                "message": "Email provider configs retrieved successfully",
                "data": [self._serialize_provider_config(config) for config in configs],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_records": total_records,
                    "total_pages": ((total_records + page_size - 1) // page_size),
                },
            }

        except Exception as e:
            logger.error("[list_email_provider_configs] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def get_email_provider_config(self, config_id: str) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            config = session.query(EmailProviderConfig).filter(
                EmailProviderConfig.id == config_id
            ).first()
            if not config:
                return not_found_response("config_id", "Email provider config not found")

            return {
                "status": status.HTTP_200_OK,
                "message": "Email provider config retrieved successfully",
                "data": self._serialize_provider_config(config),
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error("[get_email_provider_config] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def update_email_provider_config(self, config_id: str, payload: dict) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            errors = []

            if not config_id:
                errors.append({"field": "config_id", "message": "config_id is required"})

            if not isinstance(payload, dict):
                return error_response(
                    400, [{"field": "payload", "message": "Payload must be a dictionary"}]
                )

            if errors:
                return error_response(400, errors)

            config = (
                session.query(EmailProviderConfig)
                .filter(EmailProviderConfig.id == config_id)
                .first()
            )

            if not config:
                return not_found_response("config_id", "Email provider config not found")

            provider_name = payload.get("provider_name")
            if provider_name is not None:
                if not isinstance(provider_name, str):
                    errors.append({
                        "field": "provider_name",
                        "message": "provider_name must be a string",
                    })
                else:
                    provider_name = provider_name.strip()
                    if not provider_name:
                        errors.append({
                            "field": "provider_name",
                            "message": "provider_name cannot be empty",
                        })

            from_email = payload.get("from_email")
            if from_email is not None:
                if not isinstance(from_email, str):
                    errors.append({
                        "field": "from_email",
                        "message": "from_email must be a string",
                    })
                else:
                    from_email = from_email.strip()
                    if not from_email:
                        errors.append({
                            "field": "from_email",
                            "message": "from_email cannot be empty",
                        })
                    elif not EMAIL_REGEX.match(from_email):
                        errors.append({
                            "field": "from_email",
                            "message": "Invalid email format",
                        })

            if "port" in payload and payload["port"] is not None:
                try:
                    port = int(payload["port"])
                    if port <= 0 or port > 65535:
                        errors.append({
                            "field": "port",
                            "message": "port must be between 1 and 65535",
                        })
                except (ValueError, TypeError):
                    errors.append({
                        "field": "port",
                        "message": "port must be a valid integer",
                    })

            if "tls_enabled" in payload and payload["tls_enabled"] is not None:
                if not isinstance(payload["tls_enabled"], bool):
                    errors.append({
                        "field": "tls_enabled",
                        "message": "tls_enabled must be a boolean value",
                    })

            if "active" in payload and payload["active"] is not None:
                if not isinstance(payload["active"], bool):
                    errors.append({
                        "field": "active",
                        "message": "active must be a boolean value",
                    })

            effective_provider = (
                provider_name.strip().upper()
                if provider_name is not None
                else (config.provider_name or "").upper()
            )

            effective_host = (
                payload.get("host") if "host" in payload else config.host
            )

            if effective_provider == "SMTP" and not effective_host:
                errors.append({
                    "field": "host",
                    "message": "host is required for SMTP provider",
                })

            if errors:
                return error_response(400, errors)

            if provider_name is not None:
                config.provider_name = provider_name.strip()

            if from_email is not None:
                config.from_email = from_email.strip()

            if "host" in payload:
                config.host = payload["host"]

            if "port" in payload:
                config.port = payload["port"]

            if "username" in payload:
                config.username = payload["username"]

            if "password" in payload:
                config.password = payload["password"]

            if "tls_enabled" in payload and payload["tls_enabled"] is not None:
                config.tls_enabled = payload["tls_enabled"]

            if "active" in payload and payload["active"] is not None:
                if payload["active"]:
                    session.query(EmailProviderConfig).filter(
                        EmailProviderConfig.id != config_id,
                        EmailProviderConfig.active.is_(True),
                    ).update(
                        {EmailProviderConfig.active: False},
                        synchronize_session=False,
                    )
                    logger.info("Deactivated other email provider configs")
                config.active = payload["active"]

            session.commit()
            session.refresh(config)

            logger.info("Admin updated email provider config id=%s", config_id)

            return {
                "status": status.HTTP_200_OK,
                "message": "Email provider config updated successfully",
                "data": self._serialize_provider_config(config),
            }

        except Exception as e:
            session.rollback()
            logger.error("[update_email_provider_config] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def delete_email_provider_config(self, config_id: str) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            config = session.query(EmailProviderConfig).filter(
                EmailProviderConfig.id == config_id
            ).first()
            if not config:
                return not_found_response("config_id", "Email provider config not found")

            session.delete(config)
            session.commit()

            logger.info("Admin deleted email provider config id=%s", config_id)
            return {
                "status": status.HTTP_200_OK,
                "message": "Email provider config deleted successfully",
            }
        except ValueError:
            raise
        except Exception as e:
            session.rollback()
            logger.error("[delete_email_provider_config] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def _serialize_template(self, template: EmailTemplate) -> dict:
        """Convert an EmailTemplate row to a JSON-safe dict."""
        return {
            "id": str(template.id),
            "template_name": str(template.template_name).capitalize(),
            "subject": str(template.subject).capitalize(),
            "body": template.body,
            "is_active": template.is_active,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }

    def create_email_template(self, payload: dict) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            errors = []

            if not isinstance(payload, dict):
                return error_response(
                    400, [{"field": "payload", "message": "Payload must be a dictionary"}]
                )

            template_name = (payload.get("template_name") or "").strip()
            body = (payload.get("body") or "").strip()
            subject = payload.get("subject")
            is_active = payload.get("is_active", True)

            if not template_name:
                errors.append({
                    "field": "template_name",
                    "message": "template_name is required",
                })

            if not body:
                errors.append({"field": "body", "message": "body is required"})

            if not subject:
                errors.append({"field": "subject", "message": "subject is required"})

            if subject is not None and not isinstance(subject, str):
                errors.append({"field": "subject", "message": "subject must be a string"})

            if not isinstance(is_active, bool):
                errors.append({"field": "is_active", "message": "is_active must be a boolean"})

            if errors:
                return error_response(400, errors)

            duplicate = (
                session.query(EmailTemplate)
                .filter(EmailTemplate.template_name == template_name, EmailTemplate.body == body)
                .first()
            )

            if duplicate:
                return error_response(
                    409,
                    [{
                        "field": "template_name",
                        "message": f"Template with name '{template_name}' already exists",
                    }],
                )

            new_template = EmailTemplate(
                template_name=template_name,
                subject=subject,
                body=body,
                is_active=is_active,
            )

            session.add(new_template)
            session.commit()
            session.refresh(new_template)

            logger.info("Admin created email template id=%s", new_template.id)

            return {
                "status": status.HTTP_201_CREATED,
                "message": "Email template created successfully",
                "data": self._serialize_template(new_template),
            }

        except Exception as e:
            session.rollback()
            logger.error("[create_email_template] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def list_email_templates(self) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            templates = session.query(EmailTemplate).all()
            data = [self._serialize_template(t) for t in templates]
            return {
                "status": status.HTTP_200_OK,
                "message": "Email templates retrieved successfully",
                "data": data,
            }
        except Exception as e:
            logger.error("[list_email_templates] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def get_email_template(self, template_id: str) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            template = session.query(EmailTemplate).filter(
                EmailTemplate.id == template_id
            ).first()
            if not template:
                return not_found_response("template_id", "Email template not found")

            return {
                "status": status.HTTP_200_OK,
                "message": "Email template retrieved successfully",
                "data": self._serialize_template(template),
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error("[get_email_template] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def update_email_template(self, template_id: str, payload: dict) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            errors = []

            if not template_id:
                errors.append({"field": "template_id", "message": "template_id is required"})

            if not isinstance(payload, dict):
                return error_response(
                    400, [{"field": "payload", "message": "Payload must be a dictionary"}]
                )

            if errors:
                return error_response(400, errors)

            template = (
                session.query(EmailTemplate)
                .filter(EmailTemplate.id == template_id)
                .first()
            )

            if not template:
                return not_found_response("template_id", "Email template not found")

            if "template_name" in payload:
                template_name = payload.get("template_name")
                if template_name is None:
                    errors.append({
                        "field": "template_name",
                        "message": "template_name cannot be null",
                    })
                elif not isinstance(template_name, str):
                    errors.append({
                        "field": "template_name",
                        "message": "template_name must be a string",
                    })
                else:
                    template_name = template_name.strip()
                    if not template_name:
                        errors.append({
                            "field": "template_name",
                            "message": "template_name cannot be empty",
                        })
                    else:
                        duplicate = (
                            session.query(EmailTemplate)
                            .filter(
                                EmailTemplate.template_name == template_name,
                                EmailTemplate.id != template_id,
                            )
                            .first()
                        )
                        if duplicate:
                            errors.append({
                                "field": "template_name",
                                "message": f"Template with name '{template_name}' already exists",
                            })

            if "body" in payload:
                body = payload.get("body")
                if body is None:
                    errors.append({"field": "body", "message": "body cannot be null"})
                elif not isinstance(body, str):
                    errors.append({"field": "body", "message": "body must be a string"})
                elif not body.strip():
                    errors.append({"field": "body", "message": "body cannot be empty"})

            if "is_active" in payload and payload.get("is_active") is not None:
                if not isinstance(payload.get("is_active"), bool):
                    errors.append({
                        "field": "is_active",
                        "message": "is_active must be a boolean value",
                    })

            if errors:
                return error_response(400, errors)

            if "template_name" in payload:
                template.template_name = payload["template_name"].strip()

            if "subject" in payload:
                template.subject = payload["subject"]

            if "body" in payload:
                template.body = payload["body"].strip()

            if "is_active" in payload and payload["is_active"] is not None:
                template.is_active = payload["is_active"]

            session.commit()
            session.refresh(template)

            logger.info("Admin updated email template id=%s", template_id)

            return {
                "status": status.HTTP_200_OK,
                "message": "Email template updated successfully",
                "data": self._serialize_template(template),
            }

        except Exception as e:
            session.rollback()
            logger.error("[update_email_template] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()

    def delete_email_template(self, template_id: str) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            template = session.query(EmailTemplate).filter(
                EmailTemplate.id == template_id
            ).first()
            if not template:
                return not_found_response("template_id", "Email template not found")

            session.delete(template)
            session.commit()

            logger.info("Admin deleted email template id=%s", template_id)
            return {
                "status": status.HTTP_200_OK,
                "message": "Email template deleted successfully",
            }
        except ValueError:
            raise
        except Exception as e:
            session.rollback()
            logger.error("[delete_email_template] Error: %s", str(e), exc_info=True)
            return internal_server_error_response(str(e))
        finally:
            session.close()


ResumeShare = ResumeShareService
resume_share_service = ResumeShareService()

# Backward-compatible function references
share_resume_via_email = resume_share_service.share_resume_via_email
share_resume_email = resume_share_service.share_resume_email
retry_share_emails = resume_share_service.retry_share_emails
create_email_provider_config = resume_share_service.create_email_provider_config
list_email_provider_configs = resume_share_service.list_email_provider_configs
get_email_provider_config = resume_share_service.get_email_provider_config
update_email_provider_config = resume_share_service.update_email_provider_config
delete_email_provider_config = resume_share_service.delete_email_provider_config
create_email_template = resume_share_service.create_email_template
list_email_templates = resume_share_service.list_email_templates
get_email_template = resume_share_service.get_email_template
update_email_template = resume_share_service.update_email_template
delete_email_template = resume_share_service.delete_email_template
