# from fastapi import status
# from uuid import UUID
# import re

# def validate_list_user(
#     page,
#     page_size,
#     sort_by,
#     sort_order,
#     filter_column,
#     filter_value
# ):
#     errors = []

#     # Page validation
#     if page is None:
#         errors.append({
#             "field": "page",
#             "message": "Page is required."
#         })
#     else:
#         try:
#             page = int(page)
#             if page < 1:
#                 errors.append({
#                     "field": "page",
#                     "message": "Page must be greater than 0."
#                 })
#         except (ValueError, TypeError):
#             errors.append({
#                 "field": "page",
#                 "message": "Page must be a valid integer."
#             })

#     # Page Size validation
#     if page_size is None:
#         errors.append({
#             "field": "page_size",
#             "message": "Page size is required."
#         })
#     else:
#         try:
#             page_size = int(page_size)
#             if page_size < 1:
#                 errors.append({
#                     "field": "page_size",
#                     "message": "Page size must be greater than 0."
#                 })
#         except (ValueError, TypeError):
#             errors.append({
#                 "field": "page_size",
#                 "message": "Page size must be a valid integer."
#             })

#     # Sort By validation
#     allowed_sort_columns = [
#         "name",
#         "email",
#         "phone_number",
#         "created_at",
#         "updated_at"
#     ]

#     if sort_by and sort_by not in allowed_sort_columns:
#         errors.append({
#             "field": "sort_by",
#             "message": f"Sort by must be one of {', '.join(allowed_sort_columns)}."
#         })

#     # Sort Order validation
#     if sort_order and sort_order.lower() not in ["asc", "desc"]:
#         errors.append({
#             "field": "sort_order",
#             "message": "Sort order must be either 'asc' or 'desc'."
#         })

#     # Filter Column validation
#     allowed_filter_columns = [
#         "name",
#         "email",
#         "phone_number",
#         "is_blocked"
#     ]

#     if filter_column and filter_column not in allowed_filter_columns:
#         errors.append({
#             "field": "filter_column",
#             "message": f"Filter column must be one of {', '.join(allowed_filter_columns)}."
#         })

#     # Filter value validation
#     if filter_column and not filter_value:
#         errors.append({
#             "field": "filter_value",
#             "message": "Filter value is required when filter column is provided."
#         })

#     if filter_value and not filter_column:
#         errors.append({
#             "field": "filter_column",
#             "message": "Filter column is required when filter value is provided."
#         })

#     if errors:
#         return {
#             "status_code": status.HTTP_400_BAD_REQUEST,
#             "errors": errors
#         }

#     return None

# def validate_new_auth(payload, admin_id):
#     errors = []

#     if not admin_id:
#         errors.append({
#             "field": "admin_id",
#             "message": "Admin ID must be provided."
#         })

#     name = payload.get("name")
#     email = payload.get("email")
#     phone_number = payload.get("phone_number")

#     # Name Validation
#     if not name or not str(name).strip():
#         errors.append({
#             "field": "name",
#             "message": "Name is required."
#         })

#     # Email Validation
#     if not email or not str(email).strip():
#         errors.append({
#             "field": "email",
#             "message": "Email is required."
#         })
#     else:
#         email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

#         if not re.match(email_regex, email):
#             errors.append({
#                 "field": "email",
#                 "message": "Invalid email format."
#             })

#     # Phone Validation
#     if not phone_number or not str(phone_number).strip():
#         errors.append({
#             "field": "phone_number",
#             "message": "Phone number is required."
#         })
#     else:
#         phone = str(phone_number).strip()

#         if not phone.isdigit():
#             errors.append({
#                 "field": "phone_number",
#                 "message": "Phone number must contain only digits."
#             })
#         elif len(phone) != 10:
#             errors.append({
#                 "field": "phone_number",
#                 "message": "Phone number must be exactly 10 digits."
#             })

#     if errors:
#         return {
#             "status_code": status.HTTP_400_BAD_REQUEST,
#             "errors": errors
#         }

#     return None

# def validate_delete_user(user_id, admin_id):
#     print("user_id:", user_id)

#     errors = []

#     if not admin_id:
#         errors.append({
#             "field": "admin_id",
#             "message": "Admin ID is required."
#         })

#     if not user_id or not str(user_id).strip():
#         errors.append({
#             "field": "user_id",
#             "message": "User ID is required."
#         })
#     else:
        
#         try:
#             UUID(str(user_id))
#             print("VALID UUID")
#         except Exception as e:
#             print("INVALID UUID:", e)

#             errors.append({
#                 "field": "user_id",
#                 "message": "Invalid User ID format."
#             })

#     if errors:
#         return {
#             "status_code": 400,
#             "errors": errors
#         }

#     return None

# def validate_update_user(payload, user_id, current_user_id, role):
#     errors = []

#     # User ID
#     if not user_id:
#         errors.append({
#             "field": "user_id",
#             "message": "User ID is required."
#         })
#     else:
#         try:
#             UUID(str(user_id))
#         except ValueError:
#             errors.append({
#                 "field": "user_id",
#                 "message": "Invalid User ID format."
#             })

#     # Current User ID
#     if not current_user_id:
#         errors.append({
#             "field": "current_user_id",
#             "message": "Current user ID is required."
#         })

#     # Role
#     if role not in ["admin", "user"]:
#         errors.append({
#             "field": "role",
#             "message": "Role must be either admin or user."
#         })

#     # Email Validation
#     if "email" in payload and payload.get("email"):
#         email = payload.get("email").strip()

#         email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

#         if not re.match(email_regex, email):
#             errors.append({
#                 "field": "email",
#                 "message": "Invalid email format."
#             })

#     # Phone Number Validation
#     if "phone_number" in payload and payload.get("phone_number"):
#         phone = str(payload.get("phone_number")).strip()

#         if not phone.isdigit():
#             errors.append({
#                 "field": "phone_number",
#                 "message": "Phone number must contain only digits."
#             })

#         elif len(phone) != 10:
#             errors.append({
#                 "field": "phone_number",
#                 "message": "Phone number must be exactly 10 digits."
#             })

#     # Name Validation
#     if "name" in payload:
#         name = payload.get("name")

#         if name is not None and not str(name).strip():
#             errors.append({
#                 "field": "name",
#                 "message": "Name cannot be empty."
#             })

#     # Password Validation
#     old_password = payload.get("old_password")
#     new_password = payload.get("new_password")

#     if old_password and not new_password:
#         errors.append({
#             "field": "new_password",
#             "message": "New password is required."
#         })

#     if new_password and not old_password:
#         errors.append({
#             "field": "old_password",
#             "message": "Old password is required."
#         })

#     # is_blocked validation
#     if "is_blocked" in payload:
#         if not isinstance(payload.get("is_blocked"), bool):
#             errors.append({
#                 "field": "is_blocked",
#                 "message": "is_blocked must be true or false."
#             })

#     if errors:
#         return {
#             "status_code": status.HTTP_400_BAD_REQUEST,
#             "errors": errors
#         }

#     return None

from datetime import datetime
from fastapi.responses import JSONResponse
from fastapi import status
from uuid import UUID
import re

from src.utils.response import error_response


EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
ALPHA_REGEX = r"^[A-Za-z]+$"
ALPHA_COLUMNS = ["name"]

def build_error(field, message):
    return {
        "field": field,
        "message": message
    }

def validation_response(errors):
    if errors:
        # return JSONResponse({
        #     "status_code": status.HTTP_400_BAD_REQUEST,
        #     "errors": errors
        # })
        return error_response(400, errors)
    return None

def validate_uuid(value, field_name, errors):
    if not value:
        errors.append(build_error(field_name, f"{field_name.replace('_', ' ').title()} is required."))
        return

    try:
        UUID(str(value).strip())
    except (ValueError, TypeError):
        errors.append(build_error(field_name, f"Invalid {field_name.replace('_', ' ').title()} format."))

def validate_email(email, errors):
    if not email or not str(email).strip():
        errors.append(build_error("email", "Email is required."))
        return

    if not re.match(EMAIL_REGEX, email):
        errors.append(build_error("email", "Invalid email format."))

def validate_phone(phone, errors):
    if not phone or not str(phone).strip():
        errors.append(build_error("phone_number", "Phone number is required."))
        return

    phone = str(phone).strip()

    if not phone.isdigit():
        errors.append(build_error("phone_number", "Phone number must contain only digits."))
        return

    if len(phone) != 10:
        errors.append(build_error("phone_number", "Phone number must be exactly 10 digits."))

def validate_sort_by(sort_by, allowed_columns, errors):
    if sort_by and sort_by not in allowed_columns:
        errors.append({
            "field": "sort_by",
            "message": f"Sort by must be one of {', '.join(allowed_columns)}."
        })

def validate_sort_order(sort_order, errors):
    if sort_order and str(sort_order).lower() not in ["asc", "desc"]:
        errors.append({
            "field": "sort_order",
            "message": "Sort order must be either 'asc' or 'desc'."
        })

def validate_filter(
    filter_column,
    filter_value,
    allowed_columns,
    errors
):
    if filter_column and filter_column not in allowed_columns:
        errors.append({
            "field": "filter_column",
            "message": f"Filter column must be one of {', '.join(allowed_columns)}."
        })

    if filter_column and (
        filter_value is None or str(filter_value).strip() == ""
    ):
        errors.append({
            "field": "filter_value",
            "message": "Filter value is required when filter column is provided."
        })

    if filter_value and not filter_column:
        errors.append({
            "field": "filter_column",
            "message": "Filter column is required when filter value is provided."
        })

def validate_positive_integer(value, field_name, errors):
    try:
        value = int(value)

        if value < 1:
            errors.append(build_error(field_name, f"{field_name.replace('_', ' ').title()} must be greater than 0."))
    except (ValueError, TypeError):
        errors.append(build_error(field_name, f"{field_name.replace('_', ' ').title()} must be a valid integer."))


def validate_list_user(
    page,
    page_size,
    sort_by,
    sort_order,
    filter_column,
    filter_value
):
    errors = []

    validate_positive_integer(page, "page", errors)
    validate_positive_integer(page_size, "page_size", errors)

    allowed_columns = {
        "name",
        "email",
        "phone_number",
        "created_at",
        "updated_at"
    }
    if sort_by:
        if sort_by not in allowed_columns:
            errors.append(
                build_error(
                    "sort_by",
                    f"Sort by must be one of {', '.join(allowed_columns)}."
                )
            )

        if sort_order and sort_order.lower() not in {"asc", "desc"}:
            errors.append(
                build_error(
                    "sort_order",
                    "Sort order must be either 'asc' or 'desc'."
                )
            )

    allowed_filter_columns = {
        "name",
        "email",
        "phone_number",
        "is_blocked"
    }

    if filter_column:
        if filter_column not in allowed_filter_columns:
            errors.append(
                build_error(
                    "filter_column",
                    f"Filter column must be one of {', '.join(allowed_filter_columns)}."
                )
            )

        if filter_value is None or str(filter_value).strip() == "":
            errors.append(
                build_error(
                    "filter_value",
                    "Filter value is required when filter column is provided."
                )
            )

    elif filter_value:
        errors.append(
            build_error(
                "filter_column",
                "Filter column is required when filter value is provided."
            )
        )

    return validation_response(errors)

def validate_new_auth(payload, admin_id):
    errors = []

    if not admin_id:
        errors.append(
            build_error(
                "admin_id",
                "Admin ID must be provided."
            )
        )

    name = payload.get("name")
    

    if not name or not str(name).strip():
        errors.append(
            build_error(
                "name",
                "Name is required."
            )
        )
        
    elif "name" in ALPHA_COLUMNS:
        if bool(re.match(ALPHA_REGEX, name)) == False:
            # return JSONResponse({
            #     "field": "name",
            #     "message": f"{"Name"} should not allow numbers/special_characters."
            # })
            errors.append(
                build_error(
                    "name",
                    f"{"Name"} should not allow numbers/special_characters."
                )
            )
            # return error_response(400, )

    validate_email(payload.get("email"), errors)
    validate_phone(payload.get("phone_number"), errors)

    return validation_response(errors)

def validate_delete_user(user_id, admin_id):
    errors = []

    if not admin_id:
        errors.append(
            build_error(
                "admin_id",
                "Admin ID is required."
            )
        )

    validate_uuid(user_id, "user_id", errors)

    return validation_response(errors)

def validate_update_user(payload, user_id, current_user_id, role):
    errors = []

    validate_uuid(user_id, "user_id", errors)

    if not current_user_id:
        errors.append(
            build_error(
                "current_user_id",
                "Current user ID is required."
            )
        )

    if role not in {"admin", "user"}:
        errors.append(
            build_error(
                "role",
                "Role must be either admin or user."
            )
        )

    if payload.get("email"):
        validate_email(payload.get("email"), errors)

    if payload.get("phone_number"):
        validate_phone(payload.get("phone_number"), errors)

    if "name" in payload and not str(payload.get("name", "")).strip():
        errors.append(
            build_error(
                "name",
                "Name cannot be empty."
            )
        )
    name = str(payload.get("name", "")).strip()
    
    old_password = payload.get("old_password")
    new_password = payload.get("new_password")

    if old_password and not new_password:
        errors.append(
            build_error(
                "new_password",
                "New password is required."
            )
        )

    if new_password and not old_password:
        errors.append(
            build_error(
                "old_password",
                "Old password is required."
            )
        )

    if "is_blocked" in payload and not isinstance(payload.get("is_blocked"), bool):
        errors.append(
            build_error(
                "is_blocked",
                "is_blocked must be true or false."
            )
        )

    if "name" in ALPHA_COLUMNS and name != '':
        
        if bool(re.match(ALPHA_REGEX, name)) == False:
            
            errors.append(
                build_error(
                    "name",
                    f"{"Name"} should not allow numbers/special_characters."
                )
            )

    return validation_response(errors)

def validate_get_user(user_id):
    errors = []

    validate_uuid(user_id, "user_id", errors)

    return validation_response(errors)

def validate_get_user_by_id(user_id, admin_id):
    errors = []

    validate_uuid(user_id, "user_id", errors)
    validate_uuid(admin_id, "admin_id", errors)

    return validation_response(errors)

def validate_new_job(payload, admin_id):
    errors = []

    if not admin_id:
        errors.append({
            "field": "admin_id",
            "message": "Admin ID is required."
        })

    interval_minutes = payload.get("interval_minutes")
    is_paused = payload.get("is_paused")
    window_enabled = payload.get("window_enabled")
    window_start_time = payload.get("window_start_time")
    schedule_type = payload.get("schedule_type")
    weekday = payload.get("weekday")

    allowed_schedule_types = ["hourly", "daily", "weekly"]

    if not schedule_type:
        errors.append({
            "field": "schedule_type",
            "message": "Schedule type is required."
        })
    elif schedule_type not in allowed_schedule_types:
        errors.append({
            "field": "schedule_type",
            "message": f"schedule_type must be one of {allowed_schedule_types}."
        })

    if is_paused is not None and not isinstance(is_paused, bool):
        errors.append({
            "field": "is_paused",
            "message": "is_paused must be true or false."
        })

    if window_enabled is not None and not isinstance(window_enabled, bool):
        errors.append({
            "field": "window_enabled",
            "message": "window_enabled must be true or false."
        })

    if schedule_type == "hourly":

        if weekday or window_start_time:
            errors.append({
                "field": "schedule_type",
                "message": "For hourly schedule, weekday and window_start_time are not allowed."
            })

        if interval_minutes is None:
            errors.append({
                "field": "interval_minutes",
                "message": "interval_minutes is required for hourly schedule."
            })
        else:
            try:
                interval_minutes = int(interval_minutes)

                if interval_minutes <= 0:
                    errors.append({
                        "field": "interval_minutes",
                        "message": "interval_minutes must be greater than 0."
                    })

            except (ValueError, TypeError):
                errors.append({
                    "field": "interval_minutes",
                    "message": "interval_minutes must be a valid integer."
                })

    elif schedule_type == "daily":

        if weekday or window_start_time:
            errors.append({
                "field": "schedule_type",
                "message": "For daily schedule, weekday are not allowed."
            })

        if not window_start_time:
            errors.append({
                "field": "window_start_time",
                "message": "window_start_time is required for daily schedule."
            })
        else:
            try:
                datetime.strptime(
                    str(window_start_time),
                    "%H:%M:%S"
                )
            except ValueError:
                errors.append({
                    "field": "window_start_time",
                    "message": "Time must be in HH:MM:SS format."
                })

    elif schedule_type == "weekly":

        allowed_weekdays = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday"
        ]

        if not weekday:
            errors.append({
                "field": "weekday",
                "message": "weekday is required for weekly schedule."
            })

        elif weekday.lower() not in allowed_weekdays:
            errors.append({
                "field": "weekday",
                "message": f"weekday must be one of {allowed_weekdays}."
            })

        if not window_start_time:
            errors.append({
                "field": "window_start_time",
                "message": "window_start_time is required for weekly schedule."
            })
        else:
            try:
                datetime.strptime(
                    str(window_start_time),
                    "%H:%M:%S"
                )
            except ValueError:
                errors.append({
                    "field": "window_start_time",
                    "message": "Time must be in HH:MM:SS format."
                })

    if errors:
        # return JSONResponse({
        #     "status_code": status.HTTP_400_BAD_REQUEST,
        #     "errors": errors
        # })
        return error_response(400, errors)

    return None

def validate_alpha(value, field_name, errors):
    if value and not re.fullmatch(r"[A-Za-z ]+", str(value).strip()):
        errors.append({
            "field": field_name,
            "message": f"{field_name.replace('_', ' ').title()} must contain only alphabets and spaces."
        })


def validate_alphanumeric(value, field_name, errors):
    if value and not re.fullmatch(r"[A-Za-z0-9-./]+", str(value).strip()):
        errors.append({
            "field": field_name,
            "message": f"{field_name.replace('_', ' ').title()} must be alphanumeric."
        })

def validate_create_model(payload):
    errors = []

    model_name = payload.get("model_name")
    version_name = payload.get("version_name")

    if not model_name or not str(model_name).strip():
        errors.append({
            "field": "model_name",
            "message": "Model name is required."
        })
    else:
        validate_alpha(
            model_name,
            "model_name",
            errors
        )

    if not version_name or not str(version_name).strip():
        errors.append({
            "field": "version_name",
            "message": "Version name is required."
        })
    else:
        validate_alphanumeric(
            version_name,
            "version_name",
            errors
        )

    if errors:
        # return JSONResponse({
        #     "status_code": status.HTTP_400_BAD_REQUEST,
        #     "errors": errors
        # })
        return error_response(400, errors)
    return None

def validate_create_model(payload):
    errors = []

    model_name = payload.get("model_name")
    version_name = payload.get("version_name")

    if not model_name or not str(model_name).strip():
        errors.append({
            "field": "model_name",
            "message": "Model name is required."
        })
    else:
        validate_alpha(
            model_name,
            "model_name",
            errors
        )

    if not version_name or not str(version_name).strip():
        errors.append({
            "field": "version_name",
            "message": "Version name is required."
        })
    else:
        validate_alphanumeric(
            version_name,
            "version_name",
            errors
        )

    if errors:
        # return JSONResponse({
        #     "status_code": status.HTTP_400_BAD_REQUEST,
        #     "errors": errors
        # })
        return error_response(400, errors)

    return None

def validate_model_version(model_id):
    errors = []

    validate_uuid(model_id, "model_id", errors)

    return validation_response(errors)

# def validate_model_config(payload, admin_id):
#     errors = []

#     model_id = payload.get("model_id")
#     model_version_id = payload.get("model_version_id")
#     apikey = payload.get("apikey")
#     max_tokens = payload.get("max_tokens")
#     temperature = payload.get("temperature")

#     validate_uuid(admin_id, "admin_id", errors)

#     validate_uuid(model_id, "model_id", errors)

#     validate_uuid(model_version_id, "model_version_id", errors)

#     if not apikey or not str(apikey).strip():
#         errors.append({
#             "field": "apikey",
#             "message": "API key is required."
#         })

#     if max_tokens is not None:
#         try:
#             max_tokens = int(max_tokens)

#             if max_tokens <= 0:
#                 errors.append({
#                     "field": "max_tokens",
#                     "message": "Max tokens must be greater than 0."
#                 })

#         except (ValueError, TypeError):
#             errors.append({
#                 "field": "max_tokens",
#                 "message": "Max tokens must be a valid integer."
#             })

#     if temperature is not None:
#         try:
#             temperature = float(temperature)

#             if temperature < 0 or temperature > 2:
#                 errors.append({
#                     "field": "temperature",
#                     "message": "Temperature must be between 0 and 2."
#                 })

#         except (ValueError, TypeError):
#             errors.append({
#                 "field": "temperature",
#                 "message": "Temperature must be a valid number."
#             })

#     rate_limit_fields = [
#         ("request_per_minute", payload.get("request_per_minute")),
#         ("request_per_day", payload.get("request_per_day")),
#         ("token_per_minute", payload.get("token_per_minute")),
#         ("token_per_day", payload.get("token_per_day")),
#     ]

#     parsed = {}
#     for field_name, value in rate_limit_fields:
#         if value is None:
#             continue

#         if not isinstance(value, int) or isinstance(value, bool):
#             errors.append({
#                 "field": field_name,
#                 "message": f"{field_name.replace('_', ' ').title()} must be an integer."
#             })
#             continue

#         if value <= 0:
#             errors.append({
#                 "field": field_name,
#                 "message": f"{field_name.replace('_', ' ').title()} must be greater than 0."
#             })
#             continue

#         parsed[field_name] = value

#     if "request_per_minute" in parsed and "request_per_day" in parsed:
#         if parsed["request_per_minute"] > parsed["request_per_day"]:
#             errors.append({
#                 "field": "request_per_minute",
#                 "message": "Requests per minute cannot exceed requests per day."
#             })

#     if "token_per_minute" in parsed and "token_per_day" in parsed:
#         if parsed["token_per_minute"] > parsed["token_per_day"]:
#             errors.append({
#                 "field": "token_per_minute",
#                 "message": "Tokens per minute cannot exceed tokens per day."
#             })

#     return validation_response(errors)

def validate_model_config(payload, admin_id):
    errors = []

    model_id = payload.get("model_id")
    model_version_id = payload.get("model_version_id")
    apikey = payload.get("apikey")
    max_tokens = payload.get("max_tokens")
    temperature = payload.get("temperature")

    validate_uuid(admin_id, "admin_id", errors)

    validate_uuid(model_id, "model_id", errors)

    validate_uuid(model_version_id, "model_version_id", errors)

    if not apikey or not str(apikey).strip():
        errors.append({
            "field": "apikey",
            "message": "API key is required."
        })

    if max_tokens is not None:
        try:
            max_tokens = int(max_tokens)

            if max_tokens <= 0:
                errors.append({
                    "field": "max_tokens",
                    "message": "Max tokens must be greater than 0."
                })

        except (ValueError, TypeError):
            errors.append({
                "field": "max_tokens",
                "message": "Max tokens must be a valid integer."
            })

    if temperature is not None:
        try:
            temperature = float(temperature)

            if temperature < 0 or temperature > 2:
                errors.append({
                    "field": "temperature",
                    "message": "Temperature must be between 0 and 2."
                })

        except (ValueError, TypeError):
            errors.append({
                "field": "temperature",
                "message": "Temperature must be a valid number."
            })

    rate_limit_fields = [
        ("request_per_minute", payload.get("request_per_minute")),
        ("request_per_day", payload.get("request_per_day")),
        ("token_per_minute", payload.get("token_per_minute")),
        ("token_per_day", payload.get("token_per_day")),
    ]

    parsed = {}
    for field_name, value in rate_limit_fields:
        if value is None:
            continue

        if not isinstance(value, int) or isinstance(value, bool):
            errors.append({
                "field": field_name,
                "message": f"{field_name.replace('_', ' ').title()} must be an integer."
            })
            continue

        if value <= 0:
            errors.append({
                "field": field_name,
                "message": f"{field_name.replace('_', ' ').title()} must be greater than 0."
            })
            continue

        parsed[field_name] = value

    if "request_per_minute" in parsed and "request_per_day" in parsed:
        if parsed["request_per_minute"] > parsed["request_per_day"]:
            errors.append({
                "field": "request_per_minute",
                "message": "Requests per minute cannot exceed requests per day."
            })

    if "token_per_minute" in parsed and "token_per_day" in parsed:
        if parsed["token_per_minute"] > parsed["token_per_day"]:
            errors.append({
                "field": "token_per_minute",
                "message": "Tokens per minute cannot exceed tokens per day."
            })

    priority_queue = payload.get("priority_queue")
    if priority_queue is not None:
        if not isinstance(priority_queue, int) or isinstance(priority_queue, bool):
            errors.append({
                "field": "priority_queue",
                "message": "Priority queue must be an integer."
            })
        elif priority_queue <= 0:
            errors.append({
                "field": "priority_queue",
                "message": "Priority queue must be greater than 0."
            })

    return validation_response(errors)

def validate_get_model(
    page,
    page_size,
    sort_by,
    sort_order,
    filter_column,
    filter_value,
    admin_id
):
    errors = []

    validate_uuid(admin_id, "admin_id", errors)

    validate_positive_integer(page, "page", errors)
    validate_positive_integer(page_size, "page_size", errors)

    allowed_sort_columns = [
        "name",
        "version_name",
        "api_key",
        "max_tokens",
        "temperature",
        "created_at",
        "updated_at"
    ]

    validate_sort_by(
        sort_by,
        allowed_sort_columns,
        errors
    )

    validate_sort_order(
        sort_order,
        errors
    )

    allowed_filter_columns = [
        "model_config_id",
        "model_id",
        "model_name",
        "model_version_id",
        "model_version_name",
        "admin_id",
        "apikey",
        "max_tokens",
        "temperature",
        "is_active"
    ]

    validate_filter(
        filter_column,
        filter_value,
        allowed_filter_columns,
        errors
    )

    return validation_response(errors)

def validate_toggle_model(model_config_id, admin_id):
    errors = []

    validate_uuid(
        model_config_id,
        "model_config_id",
        errors
    )

    validate_uuid(
        admin_id,
        "admin_id",
        errors
    )

    return validation_response(errors)

def validate_active_model(admin_id):
    errors = []

    validate_uuid(
        admin_id,
        "admin_id",
        errors
    )

    return validation_response(errors)