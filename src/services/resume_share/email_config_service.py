"""Service layer for email provider config and email template CRUD.

Admin-only business logic for managing email sending configuration
and email templates.  Every public function uses its own database
session and raises ``ValueError`` on validation failures so the
API layer can translate them into appropriate HTTP responses.
"""

import re
from typing import Any, Dict
import logging

from fastapi import status
from sqlalchemy import asc, desc

from db.connection import SessionLocal
from src.resume_share.models import EmailProviderConfig, EmailTemplate
from src.utils.response import internal_server_error_response, serialize_response, error_response, not_found_response

logger = logging.getLogger(__name__)


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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
        errors = []

        if not isinstance(payload, dict):
            return error_response(
                400, [
                    {"field": "payload", "message": "Payload must be a dictionary"}
                ])
            # return {
            #     "status_code": 400,
            #     "errors": [
            #         {"field": "payload", "message": "Payload must be a dictionary"}
            #     ],
            # }

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
                "message": "provider_name is required"
            })

        if not from_email:
            errors.append({
                "field": "from_email",
                "message": "from_email is required"
            })
        elif not EMAIL_REGEX.match(from_email):
            errors.append({
                "field": "from_email",
                "message": "Invalid email format"
            })

        allowed_providers = {"SMTP", "SENDGRID", "SES", "MAILGUN"}

        provider_name_upper = provider_name.upper() if provider_name else ""

        if provider_name and provider_name_upper not in allowed_providers:
            errors.append({
                "field": "provider_name",
                "message": f"Invalid provider. Allowed: {list(allowed_providers)}"
            })

        if provider_name_upper == "SMTP":

            if not host:
                errors.append({
                    "field": "host",
                    "message": "host is required for SMTP provider"
                })

            if port is None:
                errors.append({
                    "field": "port",
                    "message": "port is required for SMTP provider"
                })
            else:
                try:
                    port = int(port)
                    if port <= 0 or port > 65535:
                        errors.append({
                            "field": "port",
                            "message": "port must be between 1 and 65535"
                        })
                except Exception:
                    errors.append({
                        "field": "port",
                        "message": "port must be a valid integer"
                    })

        if errors:
            return error_response(400, errors)
            # return {
            #     "status_code": 400,
            #     "errors": errors
            # }
        
        duplicate = (
            session.query(EmailProviderConfig)
            .filter(
                # EmailProviderConfig.provider_name == provider_name,
                EmailProviderConfig.from_email == from_email
            )
            .first()
        )

        if duplicate:
            return error_response(
                409, [{
                        "field": "provider_name",
                        "message": f"Provider '{from_email}' already exists"
                        }])
            # return {
            #     "status_code": status.HTTP_409_CONFLICT,
            #     "errors": [
            #         {
            #             "field": "provider_name",
            #             "message": f"Provider '{from_email}' already exists"
            #         }
            #     ]
            # }

        if is_active:
            session.query(EmailProviderConfig).filter(
                EmailProviderConfig.active.is_(True)
            ).update(
                {EmailProviderConfig.active: False},
                synchronize_session=False
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

        logger.info(
            "Admin created email provider config id=%s",
            new_config.id
        )

        return {
            "status": status.HTTP_201_CREATED,
            "message": "Email provider config created successfully",
            "data": _serialize_provider_config(new_config),
        }

    except Exception as e:
        session.rollback()
        logger.error(
            "[create_email_provider_config] Error: %s",
            str(e),
            exc_info=True
        )

        return internal_server_error_response(str(e))
        # return {
        #     "status_code": 500,
        #     "errors": [
        #         {
        #             "field": "server",
        #             "message": str(e)
        #         }
        #     ]
        # }

    finally:
        session.close()


def list_email_provider_configs(
    page,
    page_size,
    filter_column,
    filter_by,
    sort_by,
    sort_order
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

        # =========================
        # Pagination Validation
        # =========================

        if page is None:
            errors.append({
                "field": "page",
                "message": "page is required"
            })

        elif not isinstance(page, int) or page < 1:
            errors.append({
                "field": "page",
                "message": "page must be a positive integer"
            })

        if page_size is None:
            errors.append({
                "field": "page_size",
                "message": "page_size is required"
            })

        elif not isinstance(page_size, int) or page_size < 1:
            errors.append({
                "field": "page_size",
                "message": "page_size must be a positive integer"
            })

        elif page_size > 100:
            errors.append({
                "field": "page_size",
                "message": "page_size cannot exceed 100"
            })

        # =========================
        # Filter Validation
        # =========================

        if filter_column:

            if filter_column not in allowed_columns:
                errors.append({
                    "field": "filter_column",
                    "message": f"Invalid filter_column. Allowed values: {', '.join(allowed_columns.keys())}"
                })

            if filter_by in [None, ""]:
                errors.append({
                    "field": "filter_by",
                    "message": "filter_by is required when filter_column is provided"
                })

        # =========================
        # Sort Validation
        # =========================

        if sort_by:

            if sort_by not in allowed_columns:
                errors.append({
                    "field": "sort_by",
                    "message": f"Invalid sort_by. Allowed values: {', '.join(allowed_columns.keys())}"
                })

        if sort_order:

            sort_order = sort_order.lower()

            if sort_order not in ["asc", "desc"]:
                errors.append({
                    "field": "sort_order",
                    "message": "sort_order must be either 'asc' or 'desc'"
                })

        # =========================
        # Return Validation Errors
        # =========================

        if errors:
            return error_response(400, errors)
            # return {
            #     "status_code": status.HTTP_400_BAD_REQUEST,
            #     "errors": errors
            # }

        # =========================
        # Base Query
        # =========================

        query = session.query(EmailProviderConfig)

        # =========================
        # Filtering
        # =========================

        if filter_column and filter_by:

            column = allowed_columns[filter_column]

            query = query.filter(
                column.ilike(f"%{filter_by}%")
            )

        # =========================
        # Total Count
        # =========================

        total_records = query.count()

        # =========================
        # Sorting
        # =========================

        if sort_by:

            sort_column = allowed_columns[sort_by]

            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

        else:
            query = query.order_by(desc(EmailProviderConfig.created_at))

        # =========================
        # Pagination
        # =========================

        offset = (page - 1) * page_size

        configs = (
            query
            .offset(offset)
            .limit(page_size)
            .all()
        )

        if not configs:
            return not_found_response("email_provider_congigs", "No data found")
            # return {
            #     "status": status.HTTP_404_NOT_FOUND,
            #     "errors": [
            #         {
            #             "field": "email_provider_congigs",
            #             "message": "No data found"
            #         }
            #     ]
            # }
        
        
        # =========================
        # Response
        # =========================

        return {
            "status": status.HTTP_200_OK,
            "message": "Email provider configs retrieved successfully",
            "data": [_serialize_provider_config(config) for config in configs],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": total_records,
                "total_pages": (
                    (total_records + page_size - 1) // page_size
                ),
            },
        }

    except Exception as e:

        logger.error(
            "[list_email_provider_configs] Error: %s",
            str(e),
            exc_info=True
        )

        return internal_server_error_response(str(e))

    finally:
        session.close()

def get_email_provider_config(config_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        config = session.query(EmailProviderConfig).filter(
            EmailProviderConfig.id == config_id
        ).first()
        if not config:
            # raise ValueError("Email provider config not found")
            return not_found_response("config_id", "Email provider config not found")

        return {
            "status": status.HTTP_200_OK,
            "message": "Email provider config retrieved successfully",
            "data": _serialize_provider_config(config),
        }
    except ValueError:
        raise
    except Exception as e:
        logger.error("[get_email_provider_config] Error: %s", str(e), exc_info=True)
        # raise ValueError(str(e))
        return internal_server_error_response(str(e))
    finally:
        session.close()


def update_email_provider_config(config_id: str, payload: dict) -> Dict[str, Any]:
    session = SessionLocal()

    try:
        errors = []

        if not config_id:
            errors.append({
                "field": "config_id",
                "message": "config_id is required"
            })

        if not isinstance(payload, dict):
            return error_response(
                400, [{
                        "field": "payload",
                        "message": "Payload must be a dictionary"
                    }])
            # return {
            #     "status_code": status.HTTP_400_BAD_REQUEST,
            #     "errors": [
            #         {
            #             "field": "payload",
            #             "message": "Payload must be a dictionary"
            #         }
            #     ]
            # }

        if errors:
            return error_response(400, errors)
            # return {
            #     "status_code": status.HTTP_400_BAD_REQUEST,
            #     "errors": errors
            # }

        config = (
            session.query(EmailProviderConfig)
            .filter(EmailProviderConfig.id == config_id)
            .first()
        )

        if not config:
            return not_found_response("config_id", "Email provider config not found")
            # return {
            #     "status_code": status.HTTP_404_NOT_FOUND,
            #     "errors": [
            #         {
            #             "field": "config_id",
            #             "message": "Email provider config not found"
            #         }
            #     ]
            # }

        provider_name = payload.get("provider_name")

        if provider_name is not None:

            if not isinstance(provider_name, str):
                errors.append({
                    "field": "provider_name",
                    "message": "provider_name must be a string"
                })
            else:
                provider_name = provider_name.strip()

                if not provider_name:
                    errors.append({
                        "field": "provider_name",
                        "message": "provider_name cannot be empty"
                    })

        from_email = payload.get("from_email")

        if from_email is not None:

            if not isinstance(from_email, str):
                errors.append({
                    "field": "from_email",
                    "message": "from_email must be a string"
                })
            else:
                from_email = from_email.strip()

                if not from_email:
                    errors.append({
                        "field": "from_email",
                        "message": "from_email cannot be empty"
                    })

                elif not EMAIL_REGEX.match(from_email):
                    errors.append({
                        "field": "from_email",
                        "message": "Invalid email format"
                    })

        if "port" in payload and payload["port"] is not None:

            try:
                port = int(payload["port"])

                if port <= 0 or port > 65535:
                    errors.append({
                        "field": "port",
                        "message": "port must be between 1 and 65535"
                    })

            except (ValueError, TypeError):
                errors.append({
                    "field": "port",
                    "message": "port must be a valid integer"
                })

        if "tls_enabled" in payload and payload["tls_enabled"] is not None:
            if not isinstance(payload["tls_enabled"], bool):
                errors.append({
                    "field": "tls_enabled",
                    "message": "tls_enabled must be a boolean value"
                })

        if "active" in payload and payload["active"] is not None:
            if not isinstance(payload["active"], bool):
                errors.append({
                    "field": "active",
                    "message": "active must be a boolean value"
                })

        effective_provider = (
            provider_name.strip().upper()
            if provider_name is not None
            else (config.provider_name or "").upper()
        )

        effective_host = (
            payload.get("host")
            if "host" in payload
            else config.host
        )

        if effective_provider == "SMTP" and not effective_host:
            errors.append({
                "field": "host",
                "message": "host is required for SMTP provider"
            })

        if errors:
            return error_response(400, errors)
            # return {
            #     "status_code": status.HTTP_400_BAD_REQUEST,
            #     "errors": errors
            # }

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

        logger.info(
            "Admin updated email provider config id=%s",
            config_id
        )

        return {
            "status": status.HTTP_200_OK,
            "message": "Email provider config updated successfully",
            "data": _serialize_provider_config(config),
        }

    except Exception as e:
        session.rollback()

        logger.error(
            "[update_email_provider_config] Error: %s",
            str(e),
            exc_info=True,
        )

        return internal_server_error_response(str(e))

    finally:
        session.close()


def delete_email_provider_config(config_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        config = session.query(EmailProviderConfig).filter(
            EmailProviderConfig.id == config_id
        ).first()
        if not config:
            # raise ValueError("Email provider config not found")
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
        errors = []

        if not isinstance(payload, dict):
            # return {
            #     "status_code": status.HTTP_400_BAD_REQUEST,
            #     "errors": [
            #         {
            #             "field": "payload",
            #             "message": "Payload must be a dictionary"
            #         }
            #     ]
            # }
            return error_response(
                400, [{
                        "field": "payload",
                        "message": "Payload must be a dictionary"
                    }])

        template_name = (payload.get("template_name") or "").strip()
        body = (payload.get("body") or "").strip()
        subject = payload.get("subject")
        is_active = payload.get("is_active", True)

        if not template_name:
            errors.append({
                "field": "template_name",
                "message": "template_name is required"
            })

        if not body:
            errors.append({
                "field": "body",
                "message": "body is required"
            })

        if subject is not None and not isinstance(subject, str):
            errors.append({
                "field": "subject",
                "message": "subject must be a string"
            })

        if not isinstance(is_active, bool):
            errors.append({
                "field": "is_active",
                "message": "is_active must be a boolean"
            })

        if errors:
            return error_response(400, errors)
        #     return {
        #         "status_code": status.HTTP_400_BAD_REQUEST,
        #         "errors": errors
        #     }
            

        duplicate = (
            session.query(EmailTemplate)
            .filter(EmailTemplate.template_name == template_name, EmailTemplate.body == body)
            .first()
        )

        if duplicate:
            return error_response(
                409, [{
                        "field": "template_name",
                        "message": f"Template with name '{template_name}' already exists"
                    }])
            # return {
            #     "status_code": status.HTTP_409_CONFLICT,
            #     "errors": [
            #         {
            #             "field": "template_name",
            #             "message": f"Template with name '{template_name}' already exists"
            #         }
            #     ]
            # }

        new_template = EmailTemplate(
            template_name=template_name,
            subject=subject,
            body=body,
            is_active=is_active,
        )

        session.add(new_template)
        session.commit()
        session.refresh(new_template)

        logger.info(
            "Admin created email template id=%s",
            new_template.id
        )

        return {
            "status": status.HTTP_201_CREATED,
            "message": "Email template created successfully",
            "data": _serialize_template(new_template),
        }

    except Exception as e:
        session.rollback()

        logger.error(
            "[create_email_template] Error: %s",
            str(e),
            exc_info=True
        )

        return internal_server_error_response(str(e))

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
        return internal_server_error_response(str(e))
    finally:
        session.close()


def get_email_template(template_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        template = session.query(EmailTemplate).filter(
            EmailTemplate.id == template_id
        ).first()
        if not template:
            # raise ValueError("Email template not found")
            return not_found_response("template_id", "Email template not found")

        return {
            "status": status.HTTP_200_OK,
            "message": "Email template retrieved successfully",
            "data": _serialize_template(template),
        }
    except ValueError:
        raise
    except Exception as e:
        logger.error("[get_email_template] Error: %s", str(e), exc_info=True)
        return internal_server_error_response(str(e))
    finally:
        session.close()


def update_email_template(template_id: str, payload: dict) -> Dict[str, Any]:
    session = SessionLocal()

    try:
        errors = []

        if not template_id:
            errors.append({
                "field": "template_id",
                "message": "template_id is required"
            })

        if not isinstance(payload, dict):
            return error_response(
                400, [{
                        "field": "payload",
                        "message": "Payload must be a dictionary"
                    }])
            # return {
            #     "status_code": status.HTTP_400_BAD_REQUEST,
            #     "errors": [
            #         {
            #             "field": "payload",
            #             "message": "Payload must be a dictionary"
            #         }
            #     ]
            # }

        if errors:
            # return {
            #     "status_code": status.HTTP_400_BAD_REQUEST,
            #     "errors": errors
            # }
            return error_response(400, errors)

        template = (
            session.query(EmailTemplate)
            .filter(EmailTemplate.id == template_id)
            .first()
        )

        if not template:
            # return {
            #     "status_code": status.HTTP_404_NOT_FOUND,
            #     "errors": [
            #         {
            #             "field": "template_id",
            #             "message": "Email template not found"
            #         }
            #     ]
            # }
            return not_found_response("template_id", "Email template not found")

        if "template_name" in payload:

            template_name = payload.get("template_name")

            if template_name is None:
                errors.append({
                    "field": "template_name",
                    "message": "template_name cannot be null"
                })
            elif not isinstance(template_name, str):
                errors.append({
                    "field": "template_name",
                    "message": "template_name must be a string"
                })
            else:
                template_name = template_name.strip()

                if not template_name:
                    errors.append({
                        "field": "template_name",
                        "message": "template_name cannot be empty"
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
                            "message": f"Template with name '{template_name}' already exists"
                        })

        if "body" in payload:

            body = payload.get("body")

            if body is None:
                errors.append({
                    "field": "body",
                    "message": "body cannot be null"
                })
            elif not isinstance(body, str):
                errors.append({
                    "field": "body",
                    "message": "body must be a string"
                })
            elif not body.strip():
                errors.append({
                    "field": "body",
                    "message": "body cannot be empty"
                })

        if "is_active" in payload and payload.get("is_active") is not None:

            if not isinstance(payload.get("is_active"), bool):
                errors.append({
                    "field": "is_active",
                    "message": "is_active must be a boolean value"
                })

        if errors:
            # return {
            #     "status_code": status.HTTP_400_BAD_REQUEST,
            #     "errors": errors
            # }
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
            "data": _serialize_template(template),
        }

    except Exception as e:
        session.rollback()

        logger.error(
            "[update_email_template] Error: %s",
            str(e),
            exc_info=True
        )

        return internal_server_error_response(str(e))

    finally:
        session.close()


def delete_email_template(template_id: str) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        template = session.query(EmailTemplate).filter(
            EmailTemplate.id == template_id
        ).first()
        if not template:
            # raise ValueError("Email template not found")
            return not_found_response("template_id", "Email template not found")

        # if template.template_name == "Resume Template":
            # raise ValueError("Cannot delete the default system template 'Resume Template'")
            

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
