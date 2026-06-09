from typing import Any, Dict, List, Optional
import logging
import datetime
from datetime import timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from src.candidate.models import Candidate
from src.resume_filter.models import Resume
from src.auth.models import OauthCredentials
from datetime import timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import UUID, String, asc, desc, func, cast, inspect
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.admin.models import Admin, Users, ExtractionConfig, ist_now
from src.auth.jwt import create_access_token, hash_password, verify_password
from fastapi import status
from src.client_track.models import CandidateInterviews, Clients, InterviewRounds, InterviewStatus
from src.utils.helper import encrypt_data, decrypt_data
from src.utils.client_track_validator import VALID_STATUSES, validate_add_client, validate_add_interview, validate_add_interview_status, validate_add_round, validate_interview_columns, validate_modify_client, validate_pagination, validate_required, validate_sort_order, validate_update_round, validate_user, validate_uuid
from src.utils.response import internal_server_error_response, not_found_response, success_response, validation_error_response

load_dotenv()
logger = logging.getLogger(__name__)

db = SessionLocal()

def rounds():
    try:

        interview_rounds = (
            db.query(InterviewRounds)
            .filter(
                InterviewRounds.is_active.is_(True)
            )
            .all()
        )

        if not interview_rounds:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "rounds",
                        "message": "No interview rounds found.",
                    }
                ],
            }

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Interview rounds retrieved successfully.",
            "data": [
                {
                    "round_id": str(round_data.round_id),
                    "round_name": round_data.round_name,
                    "created_by": round_data.created_by,
                    "updated_by": round_data.updated_by,
                    "is_active": round_data.is_active,
                }
                for round_data in interview_rounds
            ],
        }

    except Exception as e:

        logger.exception(
            f"Error while retrieving interview rounds: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()
    
def add_round(payload, user_name):
    try:

        errors = validate_add_round(
            payload,
            user_name,
        )

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        round_name = payload.get(
            "round_name"
        ).strip()

        existing_round = (
            db.query(InterviewRounds)
            .filter(
                InterviewRounds.round_name == round_name,
                InterviewRounds.is_active.is_(True),
            )
            .first()
        )

        if existing_round:
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "round_name",
                        "message": (
                            "Interview round already exists."
                        ),
                    }
                ],
            }

        interview_round = InterviewRounds(
            round_name=round_name,
            created_by=user_name,
            updated_by=user_name,
        )

        db.add(interview_round)
        db.commit()
        db.refresh(interview_round)

        return {
            "status_code": status.HTTP_201_CREATED,
            "message": (
                "Interview round created successfully."
            ),
            "data": {
                "round_id": str(
                    interview_round.round_id
                ),
                "round_name": (
                    interview_round.round_name
                ),
                "created_by": (
                    interview_round.created_by
                ),
                "updated_by": (
                    interview_round.updated_by
                ),
                "is_active": (
                    interview_round.is_active
                ),
            },
        }

    except Exception as e:

        db.rollback()

        logger.exception(
            f"Error while creating interview round: {str(e)}"
        )

        return {
            "status_code": (
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            "errors": [
                {
                    "field": "server",
                    "message": (
                        "An unexpected error occurred."
                    ),
                }
            ],
        }

    finally:
        db.close()

def update_round(payload, round_id, user_name):
    try:

        errors = validate_update_round(
            payload,
            round_id,
            user_name,
        )

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        round_name = payload.get(
            "round_name"
        ).strip()

        interview_round = (
            db.query(InterviewRounds)
            .filter(
                InterviewRounds.round_id == round_id,
                InterviewRounds.is_active.is_(True),
            )
            .first()
        )

        if not interview_round:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "round_id",
                        "message": "Interview round not found.",
                    }
                ],
            }

        if (
            interview_round.round_name.strip().lower()
            == round_name.lower()
        ):
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "round_name",
                        "message": "Round name is already the same as the existing value.",
                    }
                ],
            }

        # Check duplicate round name
        existing_round = (
            db.query(InterviewRounds)
            .filter(
                InterviewRounds.round_name == round_name,
                InterviewRounds.is_active.is_(True),
                InterviewRounds.round_id != round_id,
            )
            .first()
        )

        if existing_round:
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "round_name",
                        "message": "Interview round already exists.",
                    }
                ],
            }

        interview_round.round_name = round_name
        interview_round.updated_by = user_name

        db.add(interview_round)
        db.commit()
        db.refresh(interview_round)

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Interview round updated successfully.",
            "data": {
                "round_id": str(interview_round.round_id),
                "round_name": interview_round.round_name,
                "created_by": interview_round.created_by,
                "updated_by": interview_round.updated_by,
                "is_active": interview_round.is_active,
            },
        }

    except Exception as e:

        db.rollback()

        logger.exception(
            f"Error while updating interview round: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()

def delete_round(round_id, user_name):
    try:

        errors = []

        # Round ID validation
        error = validate_required(
            round_id,
            "round_id",
            "Round ID"
        )

        if error:
            errors.append(error)

        elif round_id:
            error = validate_uuid(
                round_id,
                "round_id",
                "Round ID"
            )

            if error:
                errors.append(error)

        # User validation
        error = validate_user(user_name)

        if error:
            errors.append(error)

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        interview_round = (
            db.query(InterviewRounds)
            .filter(
                InterviewRounds.round_id == round_id,
                InterviewRounds.is_active.is_(True),
            )
            .first()
        )

        if not interview_round:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "round_id",
                        "message": "Interview round not found.",
                    }
                ],
            }

        # Business Validation
        active_interviews = (
            db.query(InterviewStatus)
            .filter(
                InterviewStatus.round_id == round_id,
                InterviewStatus.is_active.is_(True),
            )
            .count()
        )

        if active_interviews > 0:
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "round_id",
                        "message": (
                            "Cannot delete round because "
                            "it is associated with interview statuses."
                        ),
                    }
                ],
            }

        interview_round.is_active = False
        interview_round.updated_by = user_name

        db.add(interview_round)
        db.commit()
        db.refresh(interview_round)

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Interview round deleted successfully.",
            "data": {
                "round_id": str(interview_round.round_id),
                "round_name": interview_round.round_name,
                "created_by": interview_round.created_by,
                "updated_by": interview_round.updated_by,
                "is_active": interview_round.is_active,
            },
        }

    except Exception as e:

        db.rollback()

        logger.exception(
            f"Error while deleting interview round: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()


def view_clients(page, page_size, filter_column, filter_by, sort_by, sort_order):
    try:
        errors = []

        pagination_error = validate_pagination(page, page_size)
        if pagination_error:
            errors.append(pagination_error)

        errors.extend(
            validate_interview_columns(filter_column, sort_by)
        )

        sort_error = validate_sort_order(sort_order)
        if sort_error:
            errors.append(sort_error)

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors
            }
        query = (
            db.query(Clients)
            .filter(Clients.is_active.is_(True))
        )

        column_map = {
            "company_name": Clients.company_name,
            "contact_person": Clients.contact_person,
            "email_address": Clients.email_address,
            "phone_number": Clients.phone_number,
            "location": Clients.location,
        }

        if filter_by and filter_column:
            column = column_map.get(filter_column)

            if column is not None:
                query = query.filter(
                    column.ilike(f"%{filter_by}%")
                )

        if sort_by:
            column = column_map.get(sort_by)

            if column is not None:
                if sort_order and sort_order.lower() == "desc":
                    query = query.order_by(desc(column))
                else:
                    query = query.order_by(asc(column))
        else:
            query = query.order_by(Clients.company_name.asc())

        total_count = query.count()

        # Pagination
        if page and page_size:
            offset = (page - 1) * page_size

            query = query.offset(offset).limit(page_size)

        clients = query.all()

        if not clients:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "clients",
                        "message": "No clients found."
                    }
                ]
            }

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Clients retrieved successfully.",
            "page": page,
            "page_size": page_size,
            "total_records": total_count,
            "data": [
                {
                    "client_id": str(client.client_id),
                    "company_name": client.company_name,
                    "contact_person": client.contact_person,
                    "location": client.location,
                    "email_address": client.email_address,
                    "phone_number": client.phone_number,
                    "created_by": client.created_by,
                    "updated_by": client.updated_by,
                    "is_active": client.is_active,
                }
                for client in clients
            ]
        }

    except Exception as e:

        logger.exception(
            f"Error while retrieving clients: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred."
                }
            ]
        }

    finally:
        db.close()

def add_client(payload, user_name):
    try:

        errors = validate_add_client(
            payload=payload,
            user_name=user_name,
        )

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        company_name = payload.get("company_name").strip()
        contact_person = payload.get("contact_person").strip()
        location = payload.get("location").strip()
        email_address = payload.get("email_address").strip().lower()
        phone_number = str(payload.get("phone_number")).strip()

        # Duplicate validation
        existing_client = (
            db.query(Clients)
            .filter(
                Clients.is_active.is_(True),
                (
                    (Clients.email_address == email_address)
                    |
                    (Clients.phone_number == phone_number)
                )
            )
            .first()
        )

        if existing_client:

            validation_errors = []

            if existing_client.email_address == email_address:
                validation_errors.append(
                    {
                        "field": "email_address",
                        "message": "Email address already exists.",
                    }
                )

            if existing_client.phone_number == phone_number:
                validation_errors.append(
                    {
                        "field": "phone_number",
                        "message": "Phone number already exists.",
                    }
                )

            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": validation_errors,
            }

        new_client = Clients(
            company_name=company_name,
            contact_person=contact_person,
            location=location,
            email_address=email_address,
            phone_number=phone_number,
            created_by=user_name,
            updated_by=user_name,
        )

        db.add(new_client)
        db.commit()
        db.refresh(new_client)

        return {
            "status_code": status.HTTP_201_CREATED,
            "message": "Client created successfully.",
            "data": {
                "client_id": str(new_client.client_id),
                "company_name": new_client.company_name,
                "contact_person": new_client.contact_person,
                "location": new_client.location,
                "email_address": new_client.email_address,
                "phone_number": new_client.phone_number,
                "created_by": new_client.created_by,
                "updated_by": new_client.updated_by,
                "is_active": new_client.is_active,
            },
        }

    except Exception as e:
        db.rollback()

        logger.exception(
            f"Error while creating client: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()

def modify_client(payload, client_id, user_name):
    try:

        errors = validate_modify_client(
            payload=payload,
            client_id=client_id,
            user_name=user_name,
        )

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        client = (
            db.query(Clients)
            .filter(
                Clients.client_id == client_id,
                Clients.is_active.is_(True),
            )
            .first()
        )

        if not client:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "client_id",
                        "message": "Client not found.",
                    }
                ],
            }

        company_name = payload.get(
            "company_name",
            client.company_name,
        )

        contact_person = payload.get(
            "contact_person",
            client.contact_person,
        )

        location = payload.get(
            "location",
            client.location,
        )

        email_address = payload.get(
            "email_address",
            client.email_address,
        )

        phone_number = payload.get(
            "phone_number",
            client.phone_number,
        )

        # No changes detected
        if (
            client.company_name == company_name
            and client.contact_person == contact_person
            and client.location == location
            and client.email_address == email_address
            and client.phone_number == phone_number
        ):
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "payload",
                        "message": "No changes detected.",
                    }
                ],
            }

        # Duplicate company/email validation
        duplicate_client = (
            db.query(Clients)
            .filter(
                Clients.client_id != client_id,
                Clients.is_active.is_(True),
                Clients.email_address == email_address,
            )
            .first()
        )

        if duplicate_client:
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "email_address",
                        "message": "Email address already exists.",
                    }
                ],
            }

        client.company_name = company_name
        client.contact_person = contact_person
        client.location = location
        client.email_address = email_address
        client.phone_number = phone_number
        client.updated_by = user_name

        db.add(client)
        db.commit()
        db.refresh(client)

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Client updated successfully.",
            "data": {
                "client_id": str(client.client_id),
                "company_name": client.company_name,
                "contact_person": client.contact_person,
                "location": client.location,
                "email_address": client.email_address,
                "phone_number": client.phone_number,
                "created_by": client.created_by,
                "updated_by": client.updated_by,
                "is_active": client.is_active,
            },
        }

    except Exception as e:
        db.rollback()

        logger.exception(
            f"Error while updating client: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()

def remove_client(client_id, user_name):
    try:

        errors = []

        # Client ID required validation
        error = validate_required(
            client_id,
            "client_id",
            "Client ID"
        )

        if error:
            errors.append(error)

        # Client ID UUID validation
        elif client_id:
            error = validate_uuid(
                client_id,
                "client_id",
                "Client ID"
            )

            if error:
                errors.append(error)

        # User validation
        error = validate_user(user_name)

        if error:
            errors.append(error)

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        client = (
            db.query(Clients)
            .filter(
                Clients.client_id == client_id,
                Clients.is_active.is_(True),
            )
            .first()
        )

        if not client:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "client_id",
                        "message": "Client not found.",
                    }
                ],
            }

        # Business Validation
        active_interviews = (
            db.query(CandidateInterviews)
            .filter(
                CandidateInterviews.client_id == client_id,
                CandidateInterviews.is_active.is_(True),
            )
            .count()
        )

        if active_interviews > 0:
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "client_id",
                        "message": (
                            "Cannot delete client because active "
                            "interviews exist."
                        ),
                    }
                ],
            }

        client.is_active = False
        client.updated_by = user_name

        db.add(client)
        db.commit()
        db.refresh(client)

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Client deleted successfully.",
            "data": {
                "client_id": str(client.client_id),
                "company_name": client.company_name,
                "contact_person": client.contact_person,
                "location": client.location,
                "email_address": client.email_address,
                "phone_number": client.phone_number,
                "created_by": client.created_by,
                "updated_by": client.updated_by,
                "is_active": client.is_active,
            },
        }

    except Exception as e:

        db.rollback()

        logger.exception(
            f"Error while deleting client: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()

def view_interviews(page, page_size, filter_column, filter_by, sort_by, sort_order):
    try:
        errors = []

        pagination_error = validate_pagination(page, page_size)
        if pagination_error:
            errors.append(pagination_error)

        errors.extend(
            validate_interview_columns(filter_column, sort_by)
        )

        sort_error = validate_sort_order(sort_order)
        if sort_error:
            errors.append(sort_error)

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors
            }

        query = (
            db.query(CandidateInterviews)
            .join(
                Resume,
                Resume.resume_id == CandidateInterviews.resume_id
            )
            .join(
                Candidate,
                Candidate.candidate_id == Resume.candidate_id
            )
            .filter(
                CandidateInterviews.is_active.is_(True)
            )
        )

        column_map = {
            "candidate_name": Candidate.name,
            "role": CandidateInterviews.role,
            "status": CandidateInterviews.status,
            "experience": CandidateInterviews.experience,
            "created_at": CandidateInterviews.created_at,
        }

        # Filtering
        if filter_column and filter_by:
            column = column_map.get(filter_column)

            if column is not None:
                query = query.filter(
                    column.ilike(f"%{filter_by}%")
                )

        # Sorting
        if sort_by:
            column = column_map.get(sort_by)

            if column is not None:
                if sort_order and sort_order.lower() == "desc":
                    query = query.order_by(desc(column))
                else:
                    query = query.order_by(asc(column))
        else:
            query = query.order_by(
                CandidateInterviews.created_at.desc()
            )

        total_count = query.count()

        # Pagination
        if page and page_size:
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

        interviews = query.all()

        if not interviews:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "interviews",
                        "message": "No interviews found."
                    }
                ]
            }

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Candidate interviews retrieved successfully.",
            "page": page,
            "page_size": page_size,
            "total_records": total_count,
            "data": [
                {
                    "interview_id": str(interview.interview_id),
                    "resume_id": str(interview.resume_id),
                    "client_id": str(interview.client_id),
                    "candidate_name": (
                        interview.resume.candidate.name
                        if interview.resume and interview.resume.candidate
                        else None
                    ),
                    "experience": interview.experience,
                    "status": interview.status,
                    "role": interview.role,
                    "created_by": interview.created_by,
                    "updated_by": interview.updated_by,
                    "is_active": interview.is_active,
                }
                for interview in interviews
            ]
        }

    except Exception as e:

        logger.exception(
            f"Error while fetching interviews: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred."
                }
            ]
        }

    finally:
        db.close()

def add_interview(payload, user_name):
    try:

        errors = validate_add_interview(
            payload=payload,
            user_name=user_name,
        )

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        resume_id = payload.get("resume_id")
        client_id = payload.get("client_id")
        experience = payload.get("experience")
        status_value = payload.get("status")
        role = payload.get("role")

        # Resume validation
        resume = (
            db.query(Resume)
            .filter(
                Resume.resume_id == resume_id,
                Resume.is_active.is_(True),
            )
            .first()
        )

        if not resume:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "resume_id",
                        "message": "Resume not found.",
                    }
                ],
            }

        # Duplicate interview validation
        existing_interview = (
            db.query(CandidateInterviews)
            .filter(
                CandidateInterviews.resume_id == resume_id,
                CandidateInterviews.client_id == client_id,
                CandidateInterviews.is_active.is_(True),
            )
            .first()
        )

        if existing_interview:
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "resume_id",
                        "message": "Interview already exists for this resume and client.",
                    }
                ],
            }

        new_interview = CandidateInterviews(
            resume_id=resume_id,
            client_id=client_id,
            experience=experience,
            status=status_value,
            role=role,
            created_by=user_name,
            updated_by=user_name,
        )

        db.add(new_interview)
        db.commit()
        db.refresh(new_interview)

        return {
            "status_code": status.HTTP_201_CREATED,
            "message": "Interview created successfully.",
            "data": {
                "interview_id": str(new_interview.interview_id),
                "resume_id": str(new_interview.resume_id),
                "client_id": str(new_interview.client_id),
                "experience": new_interview.experience,
                "status": new_interview.status,
                "role": new_interview.role,
                "created_by": new_interview.created_by,
                "updated_by": new_interview.updated_by,
                "is_active": new_interview.is_active,
            },
        }

    except Exception as e:
        db.rollback()

        logger.exception(
            f"Error while creating interview: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()


def remove_interview(interview_id, user_name):
    try:
        errors = []

        # interview_id validation
        if not interview_id:
            errors.append({
                "field": "interview_id",
                "message": "Interview ID is required.",
            })
        else:
            try:
                UUID(str(interview_id))
            except ValueError:
                errors.append({
                    "field": "interview_id",
                    "message": "Interview ID must be a valid UUID.",
                })

        # user validation
        if not user_name or not str(user_name).strip():
            errors.append({
                "field": "user_name",
                "message": "User name is required.",
            })

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        interview = (
            db.query(CandidateInterviews)
            .filter(
                CandidateInterviews.interview_id == interview_id,
                CandidateInterviews.is_active.is_(True),
            )
            .first()
        )

        if not interview:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "interview_id",
                        "message": "Interview not found.",
                    }
                ],
            }

        # Optional business rule:
        # Prevent deletion if candidate already cleared/rejected

        if interview.status and interview.status.lower() in [
            "rejected",
            "cleared",
        ]:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": [
                    {
                        "field": "status",
                        "message": f"Cannot delete interview with status '{interview.status}'.",
                    }
                ],
            }

        interview.is_active = False
        interview.updated_by = user_name

        db.add(interview)

        # Optional: deactivate all interview statuses
        db.query(InterviewStatus).filter(
            InterviewStatus.interview_id == interview_id,
            InterviewStatus.is_active.is_(True),
        ).update(
            {
                "is_active": False,
                "updated_by": user_name,
            },
            synchronize_session=False,
        )

        db.commit()
        db.refresh(interview)

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Interview deleted successfully.",
            "data": {
                "interview_id": str(interview.interview_id),
                "resume_id": str(interview.resume_id),
                "client_id": str(interview.client_id),
                "experience": interview.experience,
                "role": interview.role,
                "status": interview.status,
                "created_by": interview.created_by,
                "updated_by": interview.updated_by,
                "is_active": interview.is_active,
            },
        }

    except Exception as e:
        db.rollback()

        logger.exception(
            f"Error while deleting interview: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()

def view_interview_status(interview_id):
    try:
        errors = []

        required_error = validate_required(
            interview_id,
            "interview_id",
            "Interview ID"
        )

        if required_error:
            errors.append(required_error)
        else:
            uuid_error = validate_uuid(
                interview_id,
                "interview_id",
                "Interview ID"
            )

            if uuid_error:
                errors.append(uuid_error)

        if errors:
            return validation_error_response(errors)

        # interview_status = (
        #     db.query(InterviewStatus)
        #     .filter(
        #         InterviewStatus.interview_id == interview_id,
        #         InterviewStatus.is_active.is_(True)
        #     )
        #     .join(InterviewRounds, InterviewStatus.round_id == InterviewRounds.round_id)
        #     .order_by(InterviewStatus.created_at)
        #     .all()
        # )

        interview_status = (
            db.query(
                InterviewStatus.interview_status_id,
                InterviewStatus.interview_id,
                InterviewStatus.round_id,
                InterviewStatus.round_no,
                InterviewStatus.scheduled_date,
                InterviewStatus.meeting_link,
                InterviewStatus.feedback,
                InterviewStatus.status,
                InterviewStatus.created_by,
                InterviewStatus.updated_by,
                InterviewStatus.is_active,
                InterviewRounds.round_name
            )
            .join(InterviewRounds, InterviewStatus.round_id == InterviewRounds.round_id)
            .filter(InterviewStatus.interview_id == interview_id)
            .order_by(InterviewStatus.round_no)
            .all()
        )
        if not interview_status:
            return not_found_response(
                "interview_id",
                "Interview status not found."
            )

        return success_response(
            "Candidate interview status retrieved successfully.",
            [
                {
                    "interview_status_id": str(interview.interview_status_id),
                    "interview_id": str(interview.interview_id),
                    "round_id": str(interview.round_id),
                    "round_no": interview.round_no,
                    "round_name": interview.round_name,
                    "scheduled_date": interview.scheduled_date,
                    "meeting_link": interview.meeting_link,
                    "feedback": interview.feedback,
                    "status": interview.status,
                    "created_by": interview.created_by,
                    "updated_by": interview.updated_by,
                    "is_active": interview.is_active,
                }
                for interview in interview_status
            ]
        )

    except Exception:
        logger.exception("Error while retrieving interview status")
        return internal_server_error_response()

    finally:
        db.close()

def add_interview_status(payload, user_name):
    try:
        errors = validate_add_interview_status(payload, user_name)

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        interview_id = payload.get("interview_id")
        round_id = payload.get("round_id")
        round_no = payload.get("round_no")
        scheduled_date = payload.get("scheduled_date")
        meeting_link = payload.get("meeting_link")
        feedback = payload.get("feedback") or ""
        interview_status_value = payload.get("status")

        candidate_interview = (
            db.query(CandidateInterviews)
            .filter(
                CandidateInterviews.interview_id == interview_id,
                CandidateInterviews.is_active.is_(True),
            )
            .first()
        )

        if not candidate_interview:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "interview_id",
                        "message": "Interview not found.",
                    }
                ],
            }

        latest_status = (
            db.query(InterviewStatus)
            .filter(
                InterviewStatus.interview_id == interview_id,
                InterviewStatus.is_active.is_(True),
            )
            .order_by(InterviewStatus.updated_at.desc())
            .first()
        )

        # Check duplicate round_id
        existing_round_id = (
            db.query(InterviewStatus)
            .filter(
                InterviewStatus.interview_id == interview_id,
                InterviewStatus.round_id == round_id,
                InterviewStatus.is_active.is_(True),
            )
            .first()
        )

        # Check duplicate round_no
        existing_round_no = (
            db.query(InterviewStatus)
            .filter(
                InterviewStatus.interview_id == interview_id,
                InterviewStatus.round_no == round_no,
                InterviewStatus.is_active.is_(True),
            )
            .first()
        )

        validation_errors = []

        if existing_round_id:
            validation_errors.append(
                {
                    "field": "round_id",
                    "message": "This round ID already exists for the interview.",
                }
            )

        if existing_round_no:
            validation_errors.append(
                {
                    "field": "round_no",
                    "message": "This round number already exists for the interview.",
                }
            )

        if validation_errors:
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": validation_errors,
            }

        if latest_status:

            previous_status = (latest_status.status or "").lower()

            if previous_status == "rejected":
                return {
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": [
                        {
                            "field": "status",
                            "message": "Cannot schedule interview. Candidate was rejected in the previous round.",
                        }
                    ],
                }

            if previous_status != "cleared":
                return {
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": [
                        {
                            "field": "status",
                            "message": "Cannot schedule interview. Previous round has not been cleared.",
                        }
                    ],
                }

        new_interview_status = InterviewStatus(
            interview_id=interview_id,
            round_id=round_id,
            round_no=round_no,
            scheduled_date=scheduled_date,
            meeting_link=meeting_link,
            feedback=feedback,
            status=interview_status_value,
            created_by=user_name,
            updated_by=user_name,
        )

        db.add(new_interview_status)
        db.commit()
        db.refresh(new_interview_status)

        return {
            "status_code": status.HTTP_201_CREATED,
            "message": "Interview status added successfully.",
            "data": {
                "interview_status_id": str(new_interview_status.interview_status_id),
                "interview_id": str(new_interview_status.interview_id),
                "round_id": str(new_interview_status.round_id),
                "round_no": new_interview_status.round_no,
                "scheduled_date": new_interview_status.scheduled_date,
                "meeting_link": new_interview_status.meeting_link,
                "feedback": new_interview_status.feedback,
                "status": new_interview_status.status,
                "created_by": new_interview_status.created_by,
                "updated_by": new_interview_status.updated_by,
                "is_active": new_interview_status.is_active,
            },
        }

    except Exception as e:
        db.rollback()

        logger.exception(
            f"Error occurred while adding interview status: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()

def modify_interview_status(payload, interview_status_id, user_name):
    try:
        errors = []

        # interview_status_id validation
        if not interview_status_id:
            errors.append({
                "field": "interview_status_id",
                "message": "Interview status ID is required.",
            })
        else:
            try:
                UUID(str(interview_status_id))
            except ValueError:
                errors.append({
                    "field": "interview_status_id",
                    "message": "Interview status ID must be a valid UUID.",
                })

        # user_name validation
        if not user_name or not str(user_name).strip():
            errors.append({
                "field": "user_name",
                "message": "User name is required.",
            })

        # payload validations
        feedback = payload.get("feedback")
        scheduled_date = payload.get("scheduled_date")
        meeting_link = payload.get("meeting_link")
        status_value = payload.get("status")

        if feedback and len(str(feedback)) > 2000:
            errors.append({
                "field": "feedback",
                "message": "Feedback cannot exceed 2000 characters.",
            })

        if meeting_link:
            parsed = urlparse(str(meeting_link))
            if not parsed.scheme or not parsed.netloc:
                errors.append({
                    "field": "meeting_link",
                    "message": "Meeting link should be a valid URL.",
                })

        if scheduled_date:
            try:
                if isinstance(scheduled_date, str):
                    interview_date = datetime.fromisoformat(
                        scheduled_date.replace("Z", "+00:00")
                    )
                else:
                    interview_date = scheduled_date

                if interview_date < datetime.now(interview_date.tzinfo):
                    errors.append({
                        "field": "scheduled_date",
                        "message": "Interview date cannot be in the past.",
                    })

            except Exception:
                errors.append({
                    "field": "scheduled_date",
                    "message": "Scheduled date must be a valid datetime.",
                })

        if status_value and status_value.lower() not in VALID_STATUSES:
            errors.append({
                "field": "status",
                "message": f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}.",
            })

        if errors:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": errors,
            }

        interview_status = (
            db.query(InterviewStatus)
            .filter(
                InterviewStatus.interview_status_id == interview_status_id,
                InterviewStatus.is_active.is_(True),
            )
            .first()
        )

        if not interview_status:
            return {
                "status_code": status.HTTP_404_NOT_FOUND,
                "errors": [
                    {
                        "field": "interview_status_id",
                        "message": "Interview status not found.",
                    }
                ],
            }
        
        if interview_status.status and interview_status.status.lower() == "rejected":
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": [
                    {
                        "field": "status",
                        "message": "Interview status cannot be modified because the candidate has already been rejected."
                    }
                ]
            }
        
        if interview_status.status and interview_status.status.lower() == "cleared":
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": [
                    {
                        "field": "status",
                        "message": "Interview status cannot be modified because the candidate has already cleard the round."
                    }
                ]
            }

        feedback = payload.get("feedback", interview_status.feedback)
        scheduled_date = payload.get(
            "scheduled_date",
            interview_status.scheduled_date,
        )
        meeting_link = payload.get(
            "meeting_link",
            interview_status.meeting_link,
        )
        status_value = payload.get(
            "status",
            interview_status.status,
        )

        # No changes check
        if (
            interview_status.scheduled_date == scheduled_date
            and interview_status.meeting_link == meeting_link
            and interview_status.status == status_value
            and interview_status.feedback == feedback
        ):
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "errors": [
                    {
                        "field": "payload",
                        "message": "No changes detected.",
                    }
                ],
            }

        interview_status.scheduled_date = scheduled_date
        interview_status.feedback = feedback
        interview_status.meeting_link = meeting_link
        interview_status.status = status_value
        interview_status.updated_by = user_name

        db.add(interview_status)
        db.commit()
        db.refresh(interview_status)

        interview_id = interview_status.interview_id
        round_no = interview_status.round_no

        candidate_interview = (
            db.query(CandidateInterviews)
            .filter(
                CandidateInterviews.interview_id == interview_id,
                CandidateInterviews.is_active.is_(True),
            )
            .first()
        )

        if candidate_interview:

            current_status = str(status_value).lower()

            if current_status == "completed":
                candidate_interview.status = (
                    f"round {round_no} completed"
                )

            elif current_status == "cleared":
                candidate_interview.status = (
                    f"round {round_no} cleared"
                )

            elif current_status == "rejected":
                candidate_interview.status = "rejected"

            candidate_interview.updated_by = user_name

            db.add(candidate_interview)
            db.commit()
            db.refresh(candidate_interview)

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Candidate interview status updated successfully.",
            "data": {
                "interview_status_id": str(interview_status.interview_status_id),
                "interview_id": str(interview_status.interview_id),
                "round_id": str(interview_status.round_id),
                "round_no": str(interview_status.round_no),
                "scheduled_date": interview_status.scheduled_date,
                "meeting_link": interview_status.meeting_link,
                "feedback": interview_status.feedback,
                "status": interview_status.status,
                "created_by": interview_status.created_by,
                "updated_by": interview_status.updated_by,
                "is_active": interview_status.is_active,
            },
        }

    except Exception as e:
        db.rollback()

        logger.exception(
            f"Error while updating interview status: {str(e)}"
        )

        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": [
                {
                    "field": "server",
                    "message": "An unexpected error occurred.",
                }
            ],
        }

    finally:
        db.close()
