import os
import zipfile
from db.connection import SessionLocal
from src.auth.models import ist_now
from src.admin.models import AiModelConfig, AiModelUsage
import pikepdf
from dotenv import load_dotenv
import logging
import cryptography.fernet as fernet
import re
from rapidfuzz import fuzz
import phonenumbers

load_dotenv()
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY").encode()
cipher_suite = fernet.Fernet(SECRET_KEY)

def compress_pdf(input_path, output_path):
    try:
        with pikepdf.open(input_path) as pdf:
            pdf.save(
                output_path,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate
            )
        size = os.path.getsize(output_path)
        compressed_file_path = output_path.split('/')
        compressed_file_path = compressed_file_path[-1]
        logger.info(f"PDF compressed: {output_path} with size of {size}", compressed_file_path)
        return compressed_file_path
    except Exception as e:
        return(f"PDF compression failed: {e}")


def compress_docx(input_path, output_path):
    try:
        # DOCX is already a zip → recompress it
        with zipfile.ZipFile(input_path, 'r') as zin:
            with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    buffer = zin.read(item.filename)
                    zout.writestr(item, buffer)
        size = os.path.getsize(output_path)
        compressed_file_path = output_path.split('/')
        compressed_file_path = compressed_file_path[-1]
        logger.info(f"DOCX compressed: {output_path} with size of {size}")
        return compressed_file_path
    except Exception as e:
        return(f"DOCX compression failed: {e}")


def compress_file(input_file):
    if not os.path.exists(input_file):
        return("File does not exist")
        

    file_name, ext = os.path.splitext(input_file)
    ext = ext.lower()

    output_file = f"{file_name}_compressed{ext}"

    if ext == ".pdf":
        return compress_pdf(input_file, output_file)

    elif ext == ".docx":
        return compress_docx(input_file, output_file)

    else:
        return("Unsupported file type. Only PDF and DOCX allowed.")


def encrypt_data(data):
    encrypted_value = cipher_suite.encrypt(data.encode()).decode()
    return encrypted_value

def decrypt_data(encrypted_value):
    if not encrypted_value:
        return None

    try:
        if isinstance(encrypted_value, str):
            encrypted_value = encrypted_value.encode()

        return cipher_suite.decrypt(encrypted_value).decode()

    except fernet.InvalidToken:
        # Not a valid encrypted value (plain text or corrupted)
        return encrypted_value  # return as-is

    except Exception:
        return None

def clean_mobile_number(phone_number):
    try:
        # Remove spaces/dashes/brackets
        cleaned = re.sub(r"[^\d+]", "", phone_number)

        parsed = phonenumbers.parse(cleaned)

        return str(parsed.national_number)

    except Exception:
        return phone_number

from datetime import timedelta

def record_model_usage(model_config_id, tokens_used: int, name: str = None):
    """Increment usage COUNTERS for a model config and roll minute/day windows.

    Limits live in minute_requests / minute_tokens and are never touched here.
    Counters are minute_requests_received / minute_tokens_used (+ day/total).
    """
    tokens_used = tokens_used or 0

    db = SessionLocal()
    try:
        now = ist_now().replace(tzinfo=None)

        usage = db.query(AiModelUsage).filter(
            AiModelUsage.ai_model_config_id == model_config_id
        ).first()

        if not usage:
            usage = AiModelUsage(
                ai_model_config_id=model_config_id,
                minute_window_start=now,
                day_window_start=now,
            )
            db.add(usage)

        # ---- minute window: reset only the COUNTERS, keep the limits ----
        if not usage.minute_window_start or (now - usage.minute_window_start) >= timedelta(minutes=1):
            usage.minute_window_start = now
            usage.minute_requests_received = 0
            usage.minute_tokens_used = 0
            usage.is_rate_limited = False

        # ---- day window: reset day + total per your requirement ----
        if not usage.day_window_start or (now - usage.day_window_start) >= timedelta(hours=24):
            usage.day_window_start = now
            usage.total_requests = 0
            usage.total_tokens = 0
            usage.is_rate_limited = False

        # ---- increment counters only ----
        usage.minute_requests_received = (usage.minute_requests_received or 0) + 1
        usage.minute_tokens_used = (usage.minute_tokens_used or 0) + tokens_used

        usage.total_requests = (usage.total_requests or 0) + 1
        usage.total_tokens = (usage.total_tokens or 0) + tokens_used

        max_tokens = 0

        if usage.ai_model_config and usage.ai_model_config.max_tokens:
            max_tokens = usage.ai_model_config.max_tokens

        minute_exhausted = (usage.minute_tokens or 0) and (usage.minute_tokens_used or 0) + max_tokens > usage.minute_tokens
        day_exhausted = (usage.day_tokens or 0) and (usage.total_tokens or 0) + max_tokens > usage.day_tokens

        if minute_exhausted or day_exhausted:
            usage.is_rate_limited = True

        usage.last_used_at = now
        usage.updated_by = name
        db.commit()
        db.refresh(usage)

        total_token = usage.day_tokens
        token_consume = usage.total_tokens
        token_reamining = total_token - token_consume

        return (f'Total Tokens: {total_token}, Consumed: {token_consume}, Remaining: {token_reamining}')
    except Exception as e:
        db.rollback()
        logger.warning("[record_model_usage] Error: %s", str(e), exc_info=True)
    finally:
        db.close()

def calculate_match_score(
    jd_role,
    candidate_role,
    jd_skills,
    candidate_skills,
    required_exp,
    candidate_exp
):

    if isinstance(jd_role, list):
        jd_role = " ".join(map(str, jd_role))

    if isinstance(candidate_role, list):
        candidate_role = " ".join(map(str, candidate_role))

    jd_role = str(jd_role or "").lower().strip()
    candidate_role = str(candidate_role or "").lower().strip()

    title_score = fuzz.partial_ratio(
        jd_role,
        candidate_role
    )

    jd_skills = [
        str(skill).lower().strip()
        for skill in (jd_skills or [])
        if skill
    ]

    candidate_skills = [
        str(skill).lower().strip()
        for skill in (candidate_skills or [])
        if skill
    ]

    jd_skills = list(set(jd_skills))
    candidate_skills = list(set(candidate_skills))

    matched_skills = []

    for jd_skill in jd_skills:
        for candidate_skill in candidate_skills:
            if jd_skill.lower() == candidate_skill.lower():
                matched_skills.append(jd_skill)
  
    skill_score = (
        (len(matched_skills) / len(jd_skills)) * 100
        if jd_skills else 0
    )
    
    required_exp = float(required_exp or 0)
    candidate_exp = float(candidate_exp or 0)

    if required_exp == 0 and candidate_exp == 0:
        experience_score = 100
    elif candidate_exp >= required_exp:
        experience_score = 100
    else:
        experience_score = (
            candidate_exp / required_exp
        ) * 100
   
    final_score = (
        title_score * 0.1 +
        skill_score * 0.8 +
        experience_score * 0.1
    )
    final_score = round(final_score, 2)

    if final_score >= 85:
        stars = "5"
    elif final_score >= 70:
        stars = "4"
    elif final_score >= 55:
        stars = "3"
    elif final_score >= 40:
        stars = "2"
    else:
        stars = "1"
    
    return {
        "final_score": final_score,
        "star_rating": stars,
        "title_score": round(title_score, 2),
        "skill_score": round(skill_score, 2),
        "experience_score": round(experience_score, 2),
        "matched_skills": matched_skills
    }


from datetime import timedelta

def _is_model_available(usage, now, needed_tokens: int = 0) -> bool:
    """A model with no usage row yet is always available.
    needed_tokens = tokens the next request may consume; a model is skipped
    if serving that request would push it past a token limit.
    """
    if usage is None:
        return True

    minute_expired = (not usage.minute_window_start) or \
        (now - usage.minute_window_start) >= timedelta(minutes=1)
    day_expired = (not usage.day_window_start) or \
        (now - usage.day_window_start) >= timedelta(hours=24)

    # effective counters (0 if the window has rolled)
    m_req = 0 if minute_expired else (usage.minute_requests_received or 0)
    m_tok = 0 if minute_expired else (usage.minute_tokens_used or 0)
    d_req = 0 if day_expired else (usage.total_requests or 0)
    d_tok = 0 if day_expired else (usage.total_tokens or 0)

    # limits (0/None = "no limit configured" → never blocks)
    if (usage.minute_requests or 0) and m_req >= usage.minute_requests:
        return False
    if (usage.minute_tokens or 0) and (m_tok + needed_tokens) > usage.minute_tokens:
        return False
    if (usage.day_requests or 0) and d_req >= usage.day_requests:
        return False
    if (usage.day_tokens or 0) and (d_tok + needed_tokens) > usage.day_tokens:
        return False
    return True

def select_available_model(admin_id):
    """Runs on every request. Picks the highest-priority available model.
    Only writes to the DB when state actually changes (avoids per-request
    write load / lock contention).
    """
    db = SessionLocal()
    try:
        now = ist_now().replace(tzinfo=None)
        rows = (
            db.query(AiModelConfig, AiModelUsage)
            .outerjoin(
                AiModelUsage,
                AiModelUsage.ai_model_config_id == AiModelConfig.ai_model_config_id,
            )
            .filter(AiModelConfig.admin_id == admin_id)
            .order_by(
                AiModelConfig.prioprity_queue.asc().nullslast(),
                AiModelConfig.created_at.asc(),
            )
            .all()
        )
        chosen_config = None
        chosen_usage = None
        dirty = False
        for config, usage in rows:
            needed = config.max_tokens or 0
            if _is_model_available(usage, now, needed):
                chosen_config = config
                chosen_usage = usage
                break

            if usage and not usage.is_rate_limited:
                usage.is_rate_limited = True
                usage.retry_after = (usage.minute_window_start or now) + timedelta(minutes=1)
                dirty = True

        if chosen_config is None:
            already_all_off = all(not c.is_active for c, _ in rows)

            if not already_all_off:
                db.query(AiModelConfig).filter(
                    AiModelConfig.admin_id == admin_id
                ).update({AiModelConfig.is_active: False}, synchronize_session=False)
                dirty = True

            if dirty:
                db.commit()
            return None
        
        if not chosen_config.is_active:
            db.query(AiModelConfig).filter(
                AiModelConfig.admin_id == admin_id,
                AiModelConfig.ai_model_config_id != chosen_config.ai_model_config_id,
                AiModelConfig.is_active == True,
            ).update({AiModelConfig.is_active: False}, synchronize_session=False)
            chosen_config.is_active = True
            dirty = True

        if chosen_usage and chosen_usage.is_rate_limited:
            chosen_usage.is_rate_limited = False
            dirty = True

        if dirty:
            db.commit()

        model = chosen_config.ai_model
        version = chosen_config.ai_model_version

        return {
            "model_config_id": chosen_config.ai_model_config_id,
            "model_name": (model.model_name if model else "ollama"),
            "version_name": (version.version_name if version else None),
            "base_url": chosen_config.base_url,
            "apikey": chosen_config.apikey,
            "max_tokens": chosen_config.max_tokens,
        }
    
    except Exception as e:
        db.rollback()
        logger.warning("[select_available_model] Error: %s", str(e), exc_info=True)
        return None
    finally:
        db.close()

# def select_available_model(admin_id):
    # """Pick the highest-priority model under all its limits.

    # Returns a dict shaped like active_model()['data'], or None if every
    # configured model is exhausted.
    # """
    # db = SessionLocal()
    # try:
    #     now = ist_now().replace(tzinfo=None)

    #     configs = (
    #         db.query(AiModelConfig)
    #         .filter(AiModelConfig.admin_id == admin_id)
    #         .order_by(AiModelConfig.prioprity_queue.asc().nullslast())
    #         .all()
    #     )

    #     for config in configs:
    #         usage = db.query(AiModelUsage).filter(
    #             AiModelUsage.ai_model_config_id == config.ai_model_config_id
    #         ).first()

    #         if _is_model_available(usage, now):
                # optional: persist the switch so is_active reflects reality
                # db.query(AiModelConfig).update({AiModelConfig.is_active: False}, ...)
                # config.is_active = True
                # if usage: usage.is_rate_limited = False
                # db.commit()

                # model = config.ai_model      # relationship
                # version = config.ai_model_version
                # print(f"Selected model: {model.model_name}, version: {version.version_name if version else None}, config_id: {config.ai_model_config_id}")
                # return {
                #     "model_config_id": config.ai_model_config_id,
                #     "model_name": (model.model_name or "ollama"),
                #     "version_name": (version.version_name if version else None),
                #     "base_url": config.base_url,
                #     "apikey": config.apikey,   # still encrypted; decrypt at call site
                #     "max_tokens": config.max_tokens,
                # }

            # optional observability: mark it rate-limited + retry_after
            # if usage:
            #     usage.is_rate_limited = True
            #     usage.retry_after = (usage.minute_window_start or now) + timedelta(minutes=1)
            #     db.commit()

    #     return None  # everything exhausted
    # finally:
    #     db.close()