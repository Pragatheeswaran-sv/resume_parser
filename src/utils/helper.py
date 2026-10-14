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
        logger.info("Decrypted: %s", cipher_suite.decrypt(encrypted_value).decode())
        return cipher_suite.decrypt(encrypted_value).decode()

    except fernet.InvalidToken:
        # Not a valid encrypted value (plain text or corrupted)
        logger.warning("Decryption failed: Invalid token for value: %s", encrypted_value)
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

def _normalize_role_tokens(text):
    return re.findall(r"[a-zA-Z0-9+#]+", str(text or "").lower())


def _compare_single_roles(target, candidate):
    t = str(target or "").lower().strip()
    c = str(candidate or "").lower().strip()
    if not t:
        return 100.0
    if not c:
        return 0.0
    if t == c:
        return 100.0

    tsr = fuzz.token_set_ratio(t, c)
    if tsr == 100.0:
        return 100.0

    sort_r = fuzz.token_sort_ratio(t, c)
    return round((tsr * 0.70) + (sort_r * 0.30), 2)


SKILL_ALIASES = [
    {"react", "reactjs", "react.js", "react js"},
    {"node", "nodejs", "node.js", "node js"},
    {"vue", "vuejs", "vue.js", "vue js"},
    {"next", "nextjs", "next.js", "next js"},
    {"angular", "angularjs", "angular.js", "angular js"},
    {"postgres", "postgresql"},
    {"mongo", "mongodb"},
    {"aws", "amazon web services"},
    {"gcp", "google cloud platform", "google cloud"},
    {"k8s", "kubernetes"},
    {"docker", "containerization", "containers"},
    {"golang", "go"},
    {"js", "javascript"},
    {"ts", "typescript"},
    {"py", "python"},
    {"rest", "restful", "rest api", "restful api", "rest apis", "restful apis"},
    {"ci/cd", "cicd", "ci cd"},
    {"nlp", "natural language processing"},
    {"ml", "machine learning"},
    {"ai", "artificial intelligence"},
    {"dl", "deep learning"},
    {"tf", "tensorflow"},
]

SKILL_ALIAS_MAP = {}
for group in SKILL_ALIASES:
    primary = sorted(group, key=len)[0]
    for name in group:
        SKILL_ALIAS_MAP[name.lower().strip()] = primary


def _norm_skill(s):
    return re.sub(r"[^a-z0-9+#]", "", str(s).lower())


def _match_single_skill(jd_skill_raw, candidate_skills):
    jd_raw = str(jd_skill_raw).lower().strip()
    jd_norm = _norm_skill(jd_raw)
    jd_alias = SKILL_ALIAS_MAP.get(jd_raw) or SKILL_ALIAS_MAP.get(jd_norm)

    for c_s in candidate_skills:
        c_raw = str(c_s).lower().strip()
        if not c_raw:
            continue
        if jd_raw == c_raw:
            return True
        c_norm = _norm_skill(c_raw)
        if jd_norm and jd_norm == c_norm:
            return True
        c_alias = SKILL_ALIAS_MAP.get(c_raw) or SKILL_ALIAS_MAP.get(c_norm)
        if jd_alias and c_alias and jd_alias == c_alias:
            return True
        if len(jd_norm) >= 4 and len(c_norm) >= 4:
            if fuzz.ratio(jd_norm, c_norm) >= 88:
                return True
            if re.search(r"\b" + re.escape(jd_raw) + r"\b", c_raw):
                return True
    return False


def calculate_match_score(
    jd_role=None,
    candidate_role=None,
    jd_skills=None,
    candidate_skills=None,
    required_exp=None,
    candidate_exp=None,
):
    """
    Calculate candidate match score based on skills and role only.

    Weights
    -------
    Skills : 85 points
    Role   : 15 points
    Total  : 100 points

    When only one signal is provided the full 100 pts collapse onto that
    signal so the scale stays consistent.
    required_exp / candidate_exp are accepted for backward-compatibility
    but are not used in scoring.
    """
    if isinstance(jd_role, str):
        jd_roles = [jd_role.strip()] if jd_role.strip() else []
    elif isinstance(jd_role, (list, tuple, set)):
        jd_roles = [str(r).strip() for r in jd_role if str(r).strip()]
    else:
        jd_roles = []

    if isinstance(candidate_role, str):
        cand_roles = [candidate_role.strip()] if candidate_role.strip() else []
    elif isinstance(candidate_role, (list, tuple, set)):
        cand_roles = [str(r).strip() for r in candidate_role if str(r).strip()]
    else:
        cand_roles = []

    if not jd_roles:
        role_score = 100.0
        has_role = False
    elif not cand_roles:
        role_score = 0.0
        has_role = True
    else:
        has_role = True
        scores = [
            _compare_single_roles(target, cand)
            for target in jd_roles
            for cand in cand_roles
        ]
        role_score = max(scores) if scores else 0.0

    jd_skills_clean = []
    if isinstance(jd_skills, (list, tuple, set)):
        jd_skills_clean = list(dict.fromkeys([str(s).strip() for s in jd_skills if str(s).strip()]))
    elif isinstance(jd_skills, str) and jd_skills.strip():
        jd_skills_clean = [jd_skills.strip()]

    cand_skills_clean = []
    if isinstance(candidate_skills, (list, tuple, set)):
        cand_skills_clean = list(dict.fromkeys([str(s).strip() for s in candidate_skills if str(s).strip()]))
    elif isinstance(candidate_skills, str) and candidate_skills.strip():
        cand_skills_clean = [candidate_skills.strip()]

    matched_skills = []
    if not jd_skills_clean:
        skill_score = 100.0
        has_skills = False
    else:
        has_skills = True
        for s in jd_skills_clean:
            if _match_single_skill(s, cand_skills_clean):
                matched_skills.append(s)
        skill_score = (len(matched_skills) / len(jd_skills_clean)) * 100.0

    # ── Weighted final score & star rating ──────────────────────────────────
    if has_skills and has_role:
        # Score based on both existing skills and role
        final_score = (skill_score * 0.70) + (role_score * 0.30)
        final_score = round(final_score, 2)
        if final_score >= 85:
            stars = "5"
        elif final_score >= 70:
            stars = "4"
        elif final_score >= 50:
            stars = "3"
        elif final_score >= 25:
            stars = "2"
        else:
            stars = "1"

    elif has_skills:
        # Score based on skills only
        final_score = round(skill_score, 2)
        if final_score == 100.0:
            stars = "5"
        elif final_score >= 75:
            stars = "4"
        elif final_score >= 50:
            stars = "3"
        elif final_score >= 25:
            stars = "2"
        else:
            stars = "1"

    elif has_role:
        # Role only: full star if role exists, otherwise 2.5 or 3 stars
        if role_score >= 70.0:
            final_score = 100.0
            stars = "5"
        elif role_score >= 50.0:
            final_score = 60.0
            stars = "3"
        else:
            final_score = 50.0
            stars = "2.5"

    else:
        # Neither skills nor role filtered
        final_score = 100.0
        stars = "5"

    return {
        "final_score": final_score,
        "star_rating": stars,
        "skill_score": round(skill_score, 2),
        "role_score": round(role_score, 2),
        "title_score": round(role_score, 2),
        "matched_skills": matched_skills,
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

def select_available_model(admin_id, exclude_ids: set = None):
    """Runs on every request. Picks the highest-priority available model.
    Only writes to the DB when state actually changes (avoids per-request
    write load / lock contention).
    """
    db = SessionLocal()
    exclude_ids = exclude_ids or set()
    try:
        now = ist_now().replace(tzinfo=None)
        rows = (
            db.query(AiModelConfig, AiModelUsage)
            .outerjoin(
                AiModelUsage,
                AiModelUsage.ai_model_config_id == AiModelConfig.ai_model_config_id,
            )
            .filter(
                AiModelConfig.admin_id == admin_id,
                AiModelConfig.is_active == True,
            )
            .order_by(
                AiModelConfig.prioprity_queue.asc().nullslast(),
                AiModelConfig.created_at.asc(),
            )
            .all()
        )
        if not rows:
            # Check if there are *any* configs (even inactive) to give a better error message
            any_configs = (
                db.query(AiModelConfig)
                .filter(AiModelConfig.admin_id == admin_id)
                .first()
            )
            if any_configs:
                logger.warning(
                    "[select_available_model] Model configs exist but NONE are active (is_active=False) "
                    "for admin_id=%s — call the toggle-model API to activate a configuration.",
                    admin_id,
                )
            else:
                logger.warning(
                    "[select_available_model] No model configuration found at all for admin_id=%s",
                    admin_id,
                )
            return None

        chosen_config = None
        chosen_usage = None
        dirty = False
        for config, usage in rows:
            if config.ai_model_config_id in exclude_ids:
                continue
            needed = config.max_tokens or 0
            if _is_model_available(usage, now, needed):
                chosen_config = config
                chosen_usage = usage
                break

            if usage and not usage.is_rate_limited:
                usage.is_rate_limited = True
                usage.retry_after = (usage.minute_window_start or now) + timedelta(minutes=1)
                dirty = True
            logger.warning(
                "[select_available_model] Config unavailable | config_id=%s | priority=%s",
                config.ai_model_config_id, config.prioprity_queue,
            )

        if chosen_config is None:
            if dirty:
                db.commit()
            logger.warning(
                "[select_available_model] No available active model configuration for admin_id=%s",
                admin_id,
            )
            return None

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
