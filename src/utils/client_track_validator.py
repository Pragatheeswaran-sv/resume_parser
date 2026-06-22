# from uuid import UUID


# def validate_required(value, field_name, display_name=None):
#     display_name = display_name or field_name

#     if value is None:
#         return {
#             "field": field_name,
#             "message": f"{display_name} is required."
#         }

#     if isinstance(value, str) and not value.strip():
#         return {
#             "field": field_name,
#             "message": f"{display_name} cannot be empty."
#         }

#     return None


# def validate_uuid(value, field_name, display_name=None):
#     display_name = display_name or field_name

#     try:
#         UUID(str(value))
#         return None
#     except Exception:
#         return {
#             "field": field_name,
#             "message": f"{display_name} must be a valid UUID."
#             }

# import re

# EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"


# def validate_add_client(payload, user_name):
#     errors = []

#     company_name = payload.get("company_name")
#     contact_person = payload.get("contact_person")
#     location = payload.get("location")
#     email_address = payload.get("email_address")
#     phone_number = payload.get("phone_number")

#     required_fields = {
#         "company_name": company_name,
#         "contact_person": contact_person,
#         "location": location,
#         "email_address": email_address,
#         "phone_number": phone_number,
#     }

#     for field, value in required_fields.items():
#         if value is None or (
#             isinstance(value, str) and not value.strip()
#         ):
#             errors.append(
#                 {
#                     "field": field,
#                     "message": f"{field.replace('_', ' ').title()} is required.",
#                 }
#             )

#     if not user_name or not str(user_name).strip():
#         errors.append(
#             {
#                 "field": "user_name",
#                 "message": "User name is required.",
#             }
#         )

#     # Company Name
#     if company_name and len(company_name.strip()) > 255:
#         errors.append(
#             {
#                 "field": "company_name",
#                 "message": "Company name cannot exceed 255 characters.",
#             }
#         )

#     # Contact Person
#     if contact_person and len(contact_person.strip()) > 100:
#         errors.append(
#             {
#                 "field": "contact_person",
#                 "message": "Contact person cannot exceed 100 characters.",
#             }
#         )

#     # Location
#     if location and len(location.strip()) > 255:
#         errors.append(
#             {
#                 "field": "location",
#                 "message": "Location cannot exceed 255 characters.",
#             }
#         )

#     # Email
#     if email_address and not re.match(
#         EMAIL_REGEX,
#         str(email_address),
#     ):
#         errors.append(
#             {
#                 "field": "email_address",
#                 "message": "Invalid email address.",
#             }
#         )

#     # Phone
#     if phone_number:
#         phone = str(phone_number).strip()

#         if not phone.isdigit():
#             errors.append(
#                 {
#                     "field": "phone_number",
#                     "message": "Phone number must contain only digits.",
#                 }
#             )

#         elif len(phone) < 10 or len(phone) > 15:
#             errors.append(
#                 {
#                     "field": "phone_number",
#                     "message": "Phone number must be between 10 and 15 digits.",
#                 }
#             )

#     return errors

# import re
# from uuid import UUID


# EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"


# def validate_modify_client(payload, client_id, user_name):
#     errors = []

#     # client_id validation
#     if not client_id:
#         errors.append(
#             {
#                 "field": "client_id",
#                 "message": "Client ID is required.",
#             }
#         )
#     else:
#         try:
#             UUID(str(client_id))
#         except ValueError:
#             errors.append(
#                 {
#                     "field": "client_id",
#                     "message": "Client ID must be a valid UUID.",
#                 }
#             )

#     # user validation
#     if not user_name or not str(user_name).strip():
#         errors.append(
#             {
#                 "field": "user_name",
#                 "message": "User name is required.",
#             }
#         )

#     company_name = payload.get("company_name")
#     contact_person = payload.get("contact_person")
#     location = payload.get("location")
#     email_address = payload.get("email_address")
#     phone_number = payload.get("phone_number")

#     # company_name validation
#     if company_name is not None:
#         if not str(company_name).strip():
#             errors.append(
#                 {
#                     "field": "company_name",
#                     "message": "Company name cannot be empty.",
#                 }
#             )
#         elif len(company_name.strip()) > 255:
#             errors.append(
#                 {
#                     "field": "company_name",
#                     "message": "Company name cannot exceed 255 characters.",
#                 }
#             )

#     # contact_person validation
#     if contact_person is not None:
#         if not str(contact_person).strip():
#             errors.append(
#                 {
#                     "field": "contact_person",
#                     "message": "Contact person cannot be empty.",
#                 }
#             )
#         elif len(contact_person.strip()) > 100:
#             errors.append(
#                 {
#                     "field": "contact_person",
#                     "message": "Contact person cannot exceed 100 characters.",
#                 }
#             )

#     # location validation
#     if location is not None:
#         if not str(location).strip():
#             errors.append(
#                 {
#                     "field": "location",
#                     "message": "Location cannot be empty.",
#                 }
#             )
#         elif len(location.strip()) > 255:
#             errors.append(
#                 {
#                     "field": "location",
#                     "message": "Location cannot exceed 255 characters.",
#                 }
#             )

#     # email validation
#     if email_address is not None:
#         if not re.match(EMAIL_REGEX, str(email_address)):
#             errors.append(
#                 {
#                     "field": "email_address",
#                     "message": "Invalid email address.",
#                 }
#             )

#     # phone validation
#     if phone_number is not None:
#         phone = str(phone_number).strip()

#         if not phone.isdigit():
#             errors.append(
#                 {
#                     "field": "phone_number",
#                     "message": "Phone number must contain only digits.",
#                 }
#             )

#         elif len(phone) < 10 or len(phone) > 15:
#             errors.append(
#                 {
#                     "field": "phone_number",
#                     "message": "Phone number must be between 10 and 15 digits.",
#                 }
#             )

#     return errors


# def validate_remove_client(client_id, user_name):
#     errors = []

#     if not client_id:
#         errors.append(
#             {
#                 "field": "client_id",
#                 "message": "Client ID is required.",
#             }
#         )
#     else:
#         try:
#             UUID(str(client_id))
#         except ValueError:
#             errors.append(
#                 {
#                     "field": "client_id",
#                     "message": "Client ID must be a valid UUID.",
#                 }
#             )

#     if not user_name or not str(user_name).strip():
#         errors.append(
#             {
#                 "field": "user_name",
#                 "message": "User name is required.",
#             }
#         )

#     return errors


# from datetime import datetime
# from urllib.parse import urlparse
# from uuid import UUID


# VALID_INTERVIEW_STATUSES = {
#     "scheduled",
#     "in_progress",
#     "completed",
#     "rejected",
#     "cancelled",
# }

# def validate_add_interview(payload, user_name):
#     errors = []

#     resume_id = payload.get("resume_id")
#     client_id = payload.get("client_id")
#     experience = payload.get("experience")
#     status_value = payload.get("status")
#     role = payload.get("role")

#     # Required fields
#     required_fields = {
#         "resume_id": resume_id,
#         "client_id": client_id,
#         "experience": experience,
#         "status": status_value,
#         "role": role,
#     }

#     for field, value in required_fields.items():
#         if value is None or (
#             isinstance(value, str) and not value.strip()
#         ):
#             errors.append(
#                 {
#                     "field": field,
#                     "message": f"{field.replace('_', ' ').title()} is required.",
#                 }
#             )

#     # User validation
#     if not user_name or not str(user_name).strip():
#         errors.append(
#             {
#                 "field": "user_name",
#                 "message": "User name is required.",
#             }
#         )

#     # UUID validation
#     for field, value in {
#         "resume_id": resume_id,
#         "client_id": client_id,
#     }.items():
#         if value:
#             try:
#                 UUID(str(value))
#             except ValueError:
#                 errors.append(
#                     {
#                         "field": field,
#                         "message": f"{field.replace('_', ' ').title()} must be a valid UUID.",
#                     }
#                 )

#     # Experience validation
#     if experience is not None:
#         try:
#             experience = float(experience)

#             if experience < 0:
#                 errors.append(
#                     {
#                         "field": "experience",
#                         "message": "Experience cannot be negative.",
#                     }
#                 )

#         except (TypeError, ValueError):
#             errors.append(
#                 {
#                     "field": "experience",
#                     "message": "Experience must be a valid number.",
#                 }
#             )

#     # Role validation
#     if role and len(role.strip()) > 100:
#         errors.append(
#             {
#                 "field": "role",
#                 "message": "Role cannot exceed 100 characters.",
#             }
#         )

#     # Status validation
#     if (
#         status_value
#         and status_value.lower() not in VALID_INTERVIEW_STATUSES
#     ):
#         errors.append(
#             {
#                 "field": "status",
#                 "message": f"Status must be one of: {', '.join(sorted(VALID_INTERVIEW_STATUSES))}.",
#             }
#         )

#     return errors

# VALID_STATUSES = {
#     "scheduled",
#     "cleared",
#     "rejected",
#     "rescheduled",
#     "cancelled",
#     "completed",
# }

# def validate_add_interview_status(payload, user_name):
#     errors = []

#     interview_id = payload.get("interview_id")
#     round_id = payload.get("round_id")
#     round_no = payload.get("round_no")
#     scheduled_date = payload.get("scheduled_date")
#     meeting_link = payload.get("meeting_link")
#     status_value = payload.get("status")
#     feedback = payload.get("feedback")

#     # Required fields
#     required_fields = {
#         "interview_id": interview_id,
#         "round_id": round_id,
#         "round_no": round_no,
#         "scheduled_date": scheduled_date,
#         "meeting_link": meeting_link,
#         "status": status_value,
#     }

#     for field, value in required_fields.items():
#         if value is None or (
#             isinstance(value, str) and not value.strip()
#         ):
#             errors.append(
#                 {
#                     "field": field,
#                     "message": f"{field.replace('_', ' ').title()} is required.",
#                 }
#             )

#     # User validation
#     if not user_name or not str(user_name).strip():
#         errors.append(
#             {
#                 "field": "user_name",
#                 "message": "User name is required.",
#             }
#         )

#     # UUID validation
#     for field, value in {
#         "interview_id": interview_id,
#         "round_id": round_id,
#     }.items():
#         if value:
#             try:
#                 UUID(str(value))
#             except ValueError:
#                 errors.append(
#                     {
#                         "field": field,
#                         "message": f"{field.replace('_', ' ').title()} must be a valid UUID.",
#                     }
#                 )

#     # Round number validation
#     if round_no is not None:

#         if not isinstance(round_no, str):
#             errors.append(
#                 {
#                     "field": "round_no",
#                     "message": "Round number must be a string."
#                 }
#             )

#         elif not round_no.strip():
#             errors.append(
#                 {
#                     "field": "round_no",
#                     "message": "Round number cannot be empty."
#                 }
#             )

#         elif not round_no.isdigit():
#             errors.append(
#                 {
#                     "field": "round_no",
#                     "message": "Round number must contain only numeric characters."
#                 }
#             )

#         elif int(round_no) <= 0:
#             errors.append(
#                 {
#                     "field": "round_no",
#                     "message": "Round number must be greater than 0."
#                 }
#             )

#     # Meeting URL validation
#     if meeting_link:
#         parsed = urlparse(str(meeting_link))

#         if not parsed.scheme or not parsed.netloc:
#             errors.append(
#                 {
#                     "field": "meeting_link",
#                     "message": "Meeting link should be a valid URL.",
#                 }
#             )

#     # Scheduled date validation
#     if scheduled_date:
#         try:
#             if isinstance(scheduled_date, str):
#                 interview_date = datetime.fromisoformat(
#                     scheduled_date.replace("Z", "+00:00")
#                 )
#             else:
#                 interview_date = scheduled_date

#             if interview_date < datetime.now(interview_date.tzinfo):
#                 errors.append(
#                     {
#                         "field": "scheduled_date",
#                         "message": "Interview date cannot be in the past.",
#                     }
#                 )

#         except Exception:
#             errors.append(
#                 {
#                     "field": "scheduled_date",
#                     "message": "Scheduled date must be a valid datetime.",
#                 }
#             )

#     # Status validation
#     if status_value and status_value.lower() not in VALID_STATUSES:
#         errors.append(
#             {
#                 "field": "status",
#                 "message": f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}.",
#             }
#         )

#     # Feedback validation
#     if feedback and len(str(feedback)) > 2000:
#         errors.append(
#             {
#                 "field": "feedback",
#                 "message": "Feedback cannot exceed 2000 characters.",
#             }
#         )

#     return errors


from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID
import re

EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

VALID_STATUSES = {
    "scheduled",
    "cleared",
    "rejected",
    "rescheduled",
    "cancelled",
    "completed",
}

VALID_INTERVIEW_STATUSES = {
    "scheduled",
    "in_progress",
    "completed",
    "cleared",
    "rejected",
    "cancelled",
}

PAGINATION_VALIDATION = {
    "page": {
        "required": False,
        "type": int,
        "min": 1,
        "default": 1,
    },
    "per_page": {
        "required": False,
        "type": int,
        "min": 1,
        "max": 100,
        "default": 10,
    }
}

VALID_SORT_ORDERS = {"asc", "desc"}
# ALPHA_VALUR_COLUMN = ["company_name", "contact_person", "status", "candidate_name", "role", "round_name"]
alpha_column = ["company_name", "contact_person", "status", "candidate_name", "role", "round_name"]

def validate_required(value, field_name, display_name=None):
    display_name = display_name or str(field_name).lower() #field_name.replace("_", " ").title()
    pattern = r"^[A-Za-z]+(?: [A-Za-z]+)*$"
    if display_name == "round_name":
        pattern = r"^[A-Za-z]+(?:\s+[A-Za-z]+)*(?:\s+L\d+)?$"
    
    # print(display_name)
    # if display_name in alpha_column:
    #     try:
    #         data = int(value)
    #         print(data)
    #         if data:
    #             return {
    #                 "field": field_name,
    #                 "message": f"{display_name} should not contain only numbers."
    #             }
        # except Exception as e:
        #     if not str(value).isalnum():
        #         return {
        #             "field": field_name,
        #             "message": f"{display_name} should not contain special characters."
        #         }

    if value is None:
        return {
            "field": field_name,
            "message": f"{display_name} is required."
        }

    if isinstance(value, str) and not value.strip():
        return {
            "field": field_name,
            "message": f"{display_name} cannot be empty."
        }
    
    if display_name in alpha_column:
        if bool(re.match(pattern, value)) == False:
            return {
                "field": field_name,
                "message": f"{display_name} should not allow numbers/special_characters."
            }

    return None


def validate_uuid(value, field_name, display_name=None):
    display_name = display_name or field_name.replace("_", " ").title()

    try:
        UUID(str(value))
        return None
    except Exception:
        return {
            "field": field_name,
            "message": f"{display_name} must be a valid UUID."
        }

def validate_alphanumeric(value, field_name, errors):
    if value and not re.fullmatch(r"[A-Za-z0-9]+", str(value).strip()):
        errors.append({
            "field": field_name,
            "message": f"{field_name.replace('_', ' ').title()} must be alphanumeric."
        })

def validate_email(email, field_name="email_address"):
    if email and not re.match(EMAIL_REGEX, str(email)):
        return {
            "field": field_name,
            "message": "Invalid email address."
        }

    return None


def validate_phone(phone, field_name="phone_number"):
    number_pattern = r"^[0-9+ ]+$"
    if phone is None:
        return None

    phone = str(phone).strip()

    # if not phone.isdigit():
    #     return {
    #         "field": field_name,
    #         "message": "Phone number must contain only digits."
    #     }
    

    if len(phone) < 10 or len(phone) > 15:
        return {
            "field": field_name,
            "message": "Phone number must be between 10 and 15 digits."
        }
    
    if bool(re.match(number_pattern, phone)) == False:
        return {
            "field": field_name,
            "message": "Invalid mobile number."
        }

    return None


def validate_length(value, field_name, max_length):
    if value and len(str(value).strip()) > max_length:
        return {
            "field": field_name,
            "message": f"{field_name.replace('_', ' ').title()} cannot exceed {max_length} characters."
        }

    return None


def validate_user(user_name):
    return validate_required(
        user_name,
        "user_name",
        # "User Name"
    )

def validate_add_round(payload, user_name):
    errors = []

    round_name = payload.get("round_name")

    error = validate_required(
        round_name,
        "round_name",
        # "Round Name"
    )


    if error:
        errors.append(error)

    error = validate_user(user_name)

    if error:
        errors.append(error)

    if round_name:

        round_name = round_name.strip()

        if len(round_name) < 2:
            errors.append(
                {
                    "field": "round_name",
                    "message": (
                        "Round name must contain at least "
                        "2 characters."
                    ),
                }
            )

        if len(round_name) > 100:
            errors.append(
                {
                    "field": "round_name",
                    "message": (
                        "Round name cannot exceed "
                        "100 characters."
                    ),
                }
            )

    return errors

def validate_update_round(payload, round_id, user_name):
    errors = []

    round_name = payload.get("round_name")

    error = validate_required(
        round_id,
        "round_id",
        # "Round ID",
    )

    if error:
        errors.append(error)

    elif round_id:
        error = validate_uuid(
            round_id,
            "round_id",
            "Round ID",
        )

        if error:
            errors.append(error)

    error = validate_required(
        round_name,
        "round_name",
        # "Round Name",
    )

    if error:
        errors.append(error)

    error = validate_user(user_name)

    if error:
        errors.append(error)

    if round_name:

        round_name = round_name.strip()

        if len(round_name) < 2:
            errors.append(
                {
                    "field": "round_name",
                    "message": "Round name must contain at least 2 characters.",
                }
            )

        if len(round_name) > 100:
            errors.append(
                {
                    "field": "round_name",
                    "message": "Round name cannot exceed 100 characters.",
                }
            )

    return errors

def validate_add_client(payload, user_name):
    errors = []

    company_name = payload.get("company_name")
    contact_person = payload.get("contact_person")
    location = payload.get("location")
    email_address = payload.get("email_address")
    phone_number = payload.get("phone_number")

    required_fields = {
        "company_name": company_name,
        "contact_person": contact_person,
        "location": location,
        "email_address": email_address,
        "phone_number": phone_number,
    }

    for field, value in required_fields.items():
        error = validate_required(value, field)

        if error:
            errors.append(error)

    error = validate_user(user_name)
    if error:
        errors.append(error)

    for validation in [
        validate_length(company_name, "company_name", 255),
        validate_length(contact_person, "contact_person", 100),
        validate_length(location, "location", 255),
        validate_email(email_address),
        validate_phone(phone_number),
    ]:
        if validation:
            errors.append(validation)

    return errors

def validate_modify_client(payload, client_id, user_name):
    errors = []

    error = validate_uuid(client_id, "client_id")
    if error:
        errors.append(error)

    error = validate_user(user_name)
    if error:
        errors.append(error)

    company_name = payload.get("company_name")
    contact_person = payload.get("contact_person")
    location = payload.get("location")
    email_address = payload.get("email_address")
    phone_number = payload.get("phone_number")

    required_fields = {
        "company_name": company_name,
        "contact_person": contact_person,
        "location": location,
        "email_address": email_address,
        "phone_number": phone_number,
    }

    for field, value in required_fields.items():
        if field in payload:
            print(payload)
            error = validate_required(value, field)

        if error:
            errors.append(error)

    validations = [
        validate_length(company_name, "company_name", 255),
        validate_length(contact_person, "contact_person", 100),
        validate_length(location, "location", 255),
        validate_email(email_address),
        validate_phone(phone_number),
    ]

    for validation in validations:
        if validation:
            errors.append(validation)

    return errors

def validate_add_interview(payload, user_name):
    errors = []

    resume_id = payload.get("resume_id")
    client_id = payload.get("client_id")
    experience = payload.get("experience")
    status_value = payload.get("status")
    role = payload.get("role")

    required_fields = {
        "resume_id": resume_id,
        "client_id": client_id,
        "experience": experience,
        "status": status_value,
        "role": role,
    }

    for field, value in required_fields.items():

        error = validate_required(
            value,
            field,
            # field.replace("_", " ").title()
        )

        if error:
            errors.append(error)

    error = validate_user(user_name)

    if error:
        errors.append(error)

    if resume_id:

        error = validate_uuid(
            resume_id,
            "resume_id",
            "Resume ID"
        )

        if error:
            errors.append(error)

    if client_id:

        error = validate_uuid(
            client_id,
            "client_id",
            "Client ID"
        )

        if error:
            errors.append(error)

    if experience is not None:

        try:
            experience = float(experience)

            if experience < 0:
                errors.append(
                    {
                        "field": "experience",
                        "message": "Experience cannot be negative.",
                    }
                )

            if experience > 50:
                errors.append(
                    {
                        "field": "experience",
                        "message": "Experience cannot exceed 50 years.",
                    }
                )

        except (TypeError, ValueError):
            errors.append(
                {
                    "field": "experience",
                    "message": "Experience must be a valid number.",
                }
            )

    if role:

        role = role.strip()

        if len(role) < 2:
            errors.append(
                {
                    "field": "role",
                    "message": "Role must contain at least 2 characters.",
                }
            )

        if len(role) > 100:
            errors.append(
                {
                    "field": "role",
                    "message": "Role cannot exceed 100 characters.",
                }
            )

    if (
        status_value
        and status_value.lower()
        not in VALID_INTERVIEW_STATUSES
    ):
        errors.append(
            {
                "field": "status",
                "message": (
                    f"Status must be one of: "
                    f"{', '.join(sorted(VALID_INTERVIEW_STATUSES))}."
                ),
            }
        )

    return errors

def validate_add_interview_status(payload, user_name):
    errors = []

    interview_id = payload.get("interview_id")
    round_id = payload.get("round_id")
    round_no = payload.get("round_no")
    scheduled_date = payload.get("scheduled_date")
    meeting_link = payload.get("meeting_link")
    status_value = payload.get("status")
    feedback = payload.get("feedback")

    required_fields = {
        "interview_id": interview_id,
        "round_id": round_id,
        "round_no": round_no,
        "scheduled_date": scheduled_date,
        "meeting_link": meeting_link,
        "status": status_value,
    }

    for field, value in required_fields.items():
        if value is None or (
            isinstance(value, str) and not value.strip()
        ):
            errors.append(
                {
                    "field": field,
                    "message": f"{field.replace('_', ' ').title()} is required.",
                }
            )

    if not user_name or not str(user_name).strip():
        errors.append(
            {
                "field": "user_name",
                "message": "User name is required.",
            }
        )

    for field, value in {
        "interview_id": interview_id,
        "round_id": round_id,
    }.items():
        if value:
            try:
                UUID(str(value))
            except ValueError:
                errors.append(
                    {
                        "field": field,
                        "message": f"{field.replace('_', ' ').title()} must be a valid UUID.",
                    }
                )

    if round_no is not None:

        if not isinstance(round_no, str):
            errors.append(
                {
                    "field": "round_no",
                    "message": "Round number must be a string."
                }
            )

        elif not round_no.strip():
            errors.append(
                {
                    "field": "round_no",
                    "message": "Round number cannot be empty."
                }
            )

        elif not round_no.isdigit():
            errors.append(
                {
                    "field": "round_no",
                    "message": "Round number must contain only numeric characters."
                }
            )

        elif int(round_no) <= 0:
            errors.append(
                {
                    "field": "round_no",
                    "message": "Round number must be greater than 0."
                }
            )

    if meeting_link:
        parsed = urlparse(str(meeting_link))

        if not parsed.scheme or not parsed.netloc:
            errors.append(
                {
                    "field": "meeting_link",
                    "message": "Meeting link should be a valid URL.",
                }
            )

    if scheduled_date:
            try:
                if isinstance(scheduled_date, str):
                    interview_date = datetime.strptime(
                        scheduled_date,
                        "%Y-%m-%d %H:%M:%S"
                    )
                else:
                    interview_date = scheduled_date

                if interview_date < datetime.now():
                    errors.append({
                        "field": "scheduled_date",
                        "message": "Interview date cannot be in the past.",
                    })

            except ValueError:
                errors.append({
                    "field": "scheduled_date",
                    "message": "Scheduled date must be in format YYYY-MM-DD HH:MM:SS.",
                })

    if status_value and status_value.lower() not in VALID_STATUSES:
        errors.append(
            {
                "field": "status",
                "message": f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}.",
            }
        )

    if feedback and len(str(feedback)) > 2000:
        errors.append(
            {
                "field": "feedback",
                "message": "Feedback cannot exceed 2000 characters.",
            }
        )

    return errors

def validate_modify_interview_status(
    payload,
    interview_status_id,
    user_name,
):
    errors = []

    for field, value in payload.items():

        if value is None:
            errors.append({
                "field": field,
                "message": f"{field} cannot be null."
            })
            continue

        if isinstance(value, str) and not value.strip():
            errors.append({
                "field": field,
                "message": f"{field} cannot be empty."
            })

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

    if not user_name or not str(user_name).strip():
        errors.append({
            "field": "user_name",
            "message": "User name is required.",
        })

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
                interview_date = datetime.strptime(
                    scheduled_date,
                    "%Y-%m-%d %H:%M:%S"
                )
            else:
                interview_date = scheduled_date

            if interview_date < datetime.now():
                errors.append({
                    "field": "scheduled_date",
                    "message": "Interview date cannot be in the past.",
                })

        except ValueError:
            errors.append({
                "field": "scheduled_date",
                "message": (
                    "Scheduled date must be in format "
                    "YYYY-MM-DD HH:MM:SS."
                ),
            })

    if (
        status_value
        and status_value.lower() not in VALID_STATUSES
    ):
        errors.append({
            "field": "status",
            "message":
                f"Status must be one of: "
                f"{', '.join(sorted(VALID_STATUSES))}.",
        })

    return errors

def validate_pagination(page, per_page):
    if page is not None and page < 1:
        return {
            "field": "page",
            "message": "Page must be greater than 0."
        }

    if per_page is not None and per_page < 1:
        return {
            "field": "per_page",
            "message": "Per page must be greater than 0."
        }

    if per_page is not None and per_page > 100:
        return {
            "field": "per_page",
            "message": "Per page cannot exceed 100."
        }

    return None

CLIENT_COLUMNS = {
    "company_name",
    "contact_person",
    "email_address",
    "phone_number",
    "location",
}

INTERVIEW_COLUMNS = {
    "candidate_name",
    "role",
    "status",
    "experience",
}


def validate_client_columns(filter_column, sort_by):
    errors = []

    if filter_column and filter_column not in CLIENT_COLUMNS:
        errors.append({
            "field": "filter_column",
            "message": f"Allowed values: {', '.join(CLIENT_COLUMNS)}"
        })

    if sort_by and sort_by not in CLIENT_COLUMNS:
        errors.append({
            "field": "sort_by",
            "message": f"Allowed values: {', '.join(CLIENT_COLUMNS)}"
        })

    return errors

def validate_interview_columns(filter_column, sort_by):
    errors = []

    if filter_column and filter_column not in INTERVIEW_COLUMNS:
        errors.append({
            "field": "filter_column",
            "message": f"Allowed values: {', '.join(INTERVIEW_COLUMNS)}"
        })

    if sort_by and sort_by not in INTERVIEW_COLUMNS:
        errors.append({
            "field": "sort_by",
            "message": f"Allowed values: {', '.join(INTERVIEW_COLUMNS)}"
        })

    return errors

def validate_sort_order(sort_order):
    if sort_order and sort_order.lower() not in VALID_SORT_ORDERS:
        return {
            "field": "sort_order",
            "message": "Sort order must be either 'asc' or 'desc'."
        }

    return None