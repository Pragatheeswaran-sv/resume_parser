"""Service layer for email provider config and email template CRUD.

Admin-only business logic for managing email sending configuration
and email templates.  Every public function uses its own database
session and raises ``ValueError`` on validation failures so the
API layer can translate them into appropriate HTTP responses.
"""

from typing import Any, Dict
import logging

from fastapi import status

from db.connection import SessionLocal
from src.resume_share.models import EmailProviderConfig, EmailTemplate
from src.utils.response import serialize_response

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  Email Provider Config CRUD
# ═══════════════════════════════════════════════════════════════════════════

def _serialize_provider_config(config: EmailProviderConfig) -> dict:
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


def create_email_provider_config(payload: dict) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        provider_name = (payload.get("provider_name") or "").strip()
        from_email = (payload.get("from_email") or "").strip()
        host = payload.get("host")
        port = payload.get("port")

        if not provider_name:
            raise ValueError("provider_name is required")
        if not from_email:
            raise ValueError("from_email is required")
        if provider_name.upper() == "SMTP" and not host:
            raise ValueError("host is required for SMTP provider")

        is_active = payload.get("active", False)

        if is_active:
            session.query(EmailProviderConfig).filter(
                EmailProviderConfig.active.is_(True)
            ).update({EmailProviderConfig.active: False}, synchronize_session=False)
            logger.info("Deactivated all existing email provider configs")

        new_config = EmailProviderConfig(
            provider_name=provider_name,
            from_email=from_email,
            host=host,
            port=port,
            username=payload.get("username"),
            password=payload.get("password"),
            tls_enabled=payload.get("tls_enabled", True),
            active=is_active,
        )
        session.add(new_config)
        session.commit()
        session.refresh(new_config)

        logger.info("Admin created email provider config id=%s", new_config.id)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Email provider config created successfully",
            "data": _serialize_provider_config(new_config),
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("[create_email_provider_config] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def list_email_provider_configs() -> Dict[str, Any]:
    session = SessionLocal()
    try:
        configs = session.query(EmailProviderConfig).all()
        data = [_serialize_provider_config(c) for c in configs]
        return {
            "status": status.HTTP_200_OK,
            "message": "Email provider configs retrieved successfully",
            "data": data,
        }
    except Exception as e:
        logger.error("[list_email_provider_configs] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def get_email_provider_config(config_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        config = session.query(EmailProviderConfig).filter(
            EmailProviderConfig.id == config_id
        ).first()
        if not config:
            raise ValueError("Email provider config not found")

        return {
            "status": status.HTTP_200_OK,
            "message": "Email provider config retrieved successfully",
            "data": _serialize_provider_config(config),
        }
    except ValueError:
        raise
    except Exception as e:
        logger.error("[get_email_provider_config] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def update_email_provider_config(config_id: str, payload: dict) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        config = session.query(EmailProviderConfig).filter(
            EmailProviderConfig.id == config_id
        ).first()
        if not config:
            raise ValueError("Email provider config not found")

        provider_name = payload.get("provider_name")
        if provider_name is not None:
            provider_name = provider_name.strip()
            if not provider_name:
                raise ValueError("provider_name cannot be empty")
            config.provider_name = provider_name

        from_email = payload.get("from_email")
        if from_email is not None:
            from_email = from_email.strip()
            if not from_email:
                raise ValueError("from_email cannot be empty")
            config.from_email = from_email

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
                ).update({EmailProviderConfig.active: False}, synchronize_session=False)
                logger.info("Deactivated other email provider configs")
            config.active = payload["active"]

        session.commit()
        session.refresh(config)

        logger.info("Admin updated email provider config id=%s", config_id)
        return {
            "status": status.HTTP_200_OK,
            "message": "Email provider config updated successfully",
            "data": _serialize_provider_config(config),
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("[update_email_provider_config] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def delete_email_provider_config(config_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        config = session.query(EmailProviderConfig).filter(
            EmailProviderConfig.id == config_id
        ).first()
        if not config:
            raise ValueError("Email provider config not found")

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
        raise ValueError(str(e))
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════
#  Email Template CRUD
# ═══════════════════════════════════════════════════════════════════════════

def _serialize_template(template: EmailTemplate) -> dict:
    """Convert an EmailTemplate row to a JSON-safe dict."""
    return {
        "id": str(template.id),
        "template_name": template.template_name,
        "subject": template.subject,
        "body": template.body,
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def create_email_template(payload: dict) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        template_name = (payload.get("template_name") or "").strip()
        body = (payload.get("body") or "").strip()

        if not template_name:
            raise ValueError("template_name is required")
        if not body:
            raise ValueError("body is required")

        duplicate = session.query(EmailTemplate).filter(
            EmailTemplate.template_name == template_name
        ).first()
        if duplicate:
            raise ValueError(f"Template with name '{template_name}' already exists")

        new_template = EmailTemplate(
            template_name=template_name,
            subject=payload.get("subject"),
            body=body,
            is_active=payload.get("is_active", True),
        )
        session.add(new_template)
        session.commit()
        session.refresh(new_template)

        logger.info("Admin created email template id=%s", new_template.id)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Email template created successfully",
            "data": _serialize_template(new_template),
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("[create_email_template] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def list_email_templates() -> Dict[str, Any]:
    session = SessionLocal()
    try:
        templates = session.query(EmailTemplate).all()
        data = [_serialize_template(t) for t in templates]
        return {
            "status": status.HTTP_200_OK,
            "message": "Email templates retrieved successfully",
            "data": data,
        }
    except Exception as e:
        logger.error("[list_email_templates] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def get_email_template(template_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        template = session.query(EmailTemplate).filter(
            EmailTemplate.id == template_id
        ).first()
        if not template:
            raise ValueError("Email template not found")

        return {
            "status": status.HTTP_200_OK,
            "message": "Email template retrieved successfully",
            "data": _serialize_template(template),
        }
    except ValueError:
        raise
    except Exception as e:
        logger.error("[get_email_template] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def update_email_template(template_id: str, payload: dict) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        template = session.query(EmailTemplate).filter(
            EmailTemplate.id == template_id
        ).first()
        if not template:
            raise ValueError("Email template not found")

        template_name = payload.get("template_name")
        if template_name is not None:
            template_name = template_name.strip()
            if not template_name:
                raise ValueError("template_name cannot be empty")
            duplicate = session.query(EmailTemplate).filter(
                EmailTemplate.template_name == template_name,
                EmailTemplate.id != template_id,
            ).first()
            if duplicate:
                raise ValueError(f"Template with name '{template_name}' already exists")
            template.template_name = template_name

        if "subject" in payload:
            template.subject = payload["subject"]
        if "body" in payload and payload["body"] is not None:
            body = payload["body"].strip()
            if not body:
                raise ValueError("body cannot be empty")
            template.body = body
        if "is_active" in payload and payload["is_active"] is not None:
            template.is_active = payload["is_active"]

        session.commit()
        session.refresh(template)

        logger.info("Admin updated email template id=%s", template_id)
        return {
            "status": status.HTTP_200_OK,
            "message": "Email template updated successfully",
            "data": _serialize_template(template),
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("[update_email_template] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def delete_email_template(template_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        template = session.query(EmailTemplate).filter(
            EmailTemplate.id == template_id
        ).first()
        if not template:
            raise ValueError("Email template not found")

        if template.template_name == "Resume Template":
            raise ValueError("Cannot delete the default system template 'Resume Template'")

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
        raise ValueError(str(e))
    finally:
        session.close()
