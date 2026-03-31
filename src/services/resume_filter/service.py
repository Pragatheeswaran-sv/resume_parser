import os
import re
import json
import logging
from uuid import UUID
import datetime as dt
import ollama
from dotenv import load_dotenv
from email.utils import parseaddr
from pypdf import PdfReader
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from db.connection import SessionLocal
from src.resume_filter.models import Resume
from sqlalchemy import and_, cast, text, func
from sqlalchemy.dialects.postgresql import JSON
from src.email_reader.models import EmailLogs, Attachment
from src.candidate.models import (
	Candidate, CandidateSkills, CandidateEducation, 
	WorkExperience, Skill, Education, Company, Role
)


load_dotenv()
logger = logging.getLogger(__name__)
VECTORDB_PATH = "faiss_index"

def normalize_experience(exp_value) -> int:
    """Ensure experience is always integer for DB"""
    
    if exp_value is None:
        return 0
    if isinstance(exp_value, (int, float)):
        return int(exp_value)
    text = str(exp_value).lower()
    match = re.search(r"\d+(\.\d+)?", text)
    if match:
        return int(float(match.group()))

    return 0

def parse_email_address(sender: str) -> str:
    name, addr = parseaddr(sender or "")
    return addr.strip().lower()


def save_resumes_to_db(resumes):
    """Save extracted resume info to PostgreSQL database with normalized schema."""
    
    db = SessionLocal()
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    for r in resumes:
        try:
            raw_text = r["text"]
            info = r["info"]            
            attachment_id = r.get("attachment_id")
            sender_email = parse_email_address(r.get("sender_email", ""))
            logger.info(f'NAV----> the info extracted {info}')

            info_email = (info.get("email") or "").strip().lower()
            if not info_email and sender_email:
                logger.info(f'NAV----> using sender email fallback: {sender_email}')
                info_email = sender_email
                info["email"] = sender_email

            vector = embedding_model.embed_query(raw_text)

            existing_candidate = None
            if info_email:
                existing_candidate = db.query(Candidate).filter(
                    Candidate.email_address == info_email
                ).first()
            if not existing_candidate and info.get("phone_number"):
                existing_candidate = db.query(Candidate).filter(
                    Candidate.phone_number == info.get("phone_number")
                ).first()

            if existing_candidate:
                candidate = existing_candidate
                if not candidate.email_address and sender_email:
                    candidate.email_address = sender_email
                    candidate.email_from_sender = True
                    db.add(candidate)
                logger.info(f'Using existing candidate: {candidate.candidate_id}')
            else:
                candidate = Candidate(
                    name=info.get("name", ""),
                    email_address=info_email or sender_email or "",
                    email_from_sender=bool(sender_email and not info_email),
                    phone_number=info.get("phone_number", ""),
                    location=info.get("location", ""),
                    total_experience=normalize_experience(info.get("total_experience")),
                    created_by="resume_parser"
                )
                db.add(candidate)
                db.flush()
                logger.info("NAV----> candidate added to db")
            
            # Add skills
            skills_list = info.get("skills", [])
            logger.info(f'NAV----> the skills {skills_list}...')
            if skills_list:
                for skill_name in skills_list:
                    if skill_name and isinstance(skill_name, str):
                        skill_name = skill_name.strip()
                        # Get or create skill
                        skill = db.query(Skill).filter(
                            Skill.skill.ilike(skill_name)
                        ).first()
                        
                        if not skill:
                            skill = Skill(
                                skill=skill_name,
                                created_by="resume_parser"
                            )
                            db.add(skill)
                            db.flush()
                            logger.info("NAV----> new skills added to db")
                        # Check if already linked
                        existing_link = db.query(CandidateSkills).filter(
                            CandidateSkills.candidate_id == candidate.candidate_id,
                            CandidateSkills.skill_id == skill.skill_id
                        ).first()
                        
                        if not existing_link:
                            candidate_skill = CandidateSkills(
                                candidate_id=candidate.candidate_id,
                                skill_id=skill.skill_id,
                                created_by="resume_parser"
                            )
                            db.add(candidate_skill)
                            logger.info("NAV----> candidate skills added to db")
            # Add education from new structure (objects with qualification, institution, percentage, passout_year)
            education_list = info.get("education", [])
            logger.info(f'NAV----> the education {education_list}...')
            if education_list:
                for edu_item in education_list:
                    if isinstance(edu_item, dict):
                        qualification = edu_item.get("qualification", "").strip()
                        institution = edu_item.get("institution", "").strip()
                        percentage = edu_item.get("percentage", "")
                        passout_year = edu_item.get("passout_year", "")
                        
                        if qualification:
                            # Get or create education type
                            education_type = db.query(Education).filter(
                                Education.education.ilike(qualification)
                            ).first()
                            
                            if not education_type:
                                education_type = Education(
                                    education=qualification,
                                    created_by="resume_parser"
                                )
                                db.add(education_type)
                                db.flush()
                                logger.info("NAV----> new education added to db")
                            
                            # Parse passout_year to integer
                            try:
                                year_passed = int(passout_year) if passout_year else None
                            except (ValueError, TypeError):
                                year_passed = None
                            
                            # Parse percentage to float
                            try:
                                percentage_val = float(percentage) if percentage else None
                            except (ValueError, TypeError):
                                percentage_val = None
                            
                            # Check if already linked
                            existing_edu = db.query(CandidateEducation).filter(
                                CandidateEducation.candidate_id == candidate.candidate_id,
                                CandidateEducation.education_id == education_type.education_id
                            ).first()
                            
                            if not existing_edu:
                                candidate_edu = CandidateEducation(
                                    candidate_id=candidate.candidate_id,
                                    education_id=education_type.education_id,
                                    institution=institution if institution else None,
                                    percentage=percentage_val,
                                    year_of_passed=year_passed,
                                    created_by="resume_parser"
                                )
                                db.add(candidate_edu)
                                logger.info("NAV----> candidate education added to db")
            
            # Add work experience from new structure (objects with company_name, role, start_date, end_date)
            work_experience_list = info.get("work_experience", [])
            logger.info(f'NAV----> the work experience {work_experience_list}...')
            if work_experience_list:
                for work_exp_item in work_experience_list:
                    if isinstance(work_exp_item, dict):
                        company_name = work_exp_item.get("company_name", "").strip()
                        role_name = work_exp_item.get("role", "Unknown").strip()
                        start_date = work_exp_item.get("start_date", "")
                        end_date = work_exp_item.get("end_date", "")
                        
                        if company_name:
                            # Get or create company
                            company = db.query(Company).filter(
                                Company.company_name.ilike(company_name)
                            ).first()
                            
                            if not company:
                                company = Company(
                                    company_name=company_name,
                                    company_location="",
                                    created_by="resume_parser"
                                )
                                db.add(company)
                                db.flush()
                                logger.info("NAV----> new company added to db")
                            
                            # Get or create role
                            role = db.query(Role).filter(
                                Role.role.ilike(role_name)
                            ).first()
                            
                            if not role:
                                role = Role(
                                    role=role_name,
                                    created_by="resume_parser"
                                )
                                db.add(role)
                                db.flush()
                                logger.info("NAV----> new role added to db")
                            # Parse dates (YYYY-MM or YYYY format)
                            start_dt = None
                            end_dt = None
                            
                            try:
                                if start_date and start_date != "":
                                    if len(start_date) == 4:  # YYYY
                                        start_dt = dt.date(int(start_date), 1, 1)
                                    elif len(start_date) == 7:  # YYYY-MM
                                        year, month = start_date.split("-")
                                        start_dt = dt.date(int(year), int(month), 1)
                            except (ValueError, TypeError):
                                pass
                            
                            try:
                                if end_date and end_date != "" and end_date.lower() != "present":
                                    if len(end_date) == 4:  # YYYY
                                        end_dt = dt.date(int(end_date), 12, 31)
                                    elif len(end_date) == 7:  # YYYY-MM
                                        year, month = end_date.split("-")
                                        # Get last day of month
                                        if month == "12":
                                            end_dt = dt.date(int(year), 12, 31)
                                        else:
                                            next_month = dt.date(int(year), int(month) + 1, 1)
                                            end_dt = next_month - dt.timedelta(days=1)
                            except (ValueError, TypeError):
                                pass
                            
                            # Create work experience record
                            work_exp = WorkExperience(
                                candidate_id=candidate.candidate_id,
                                company_id=company.company_id,
                                role_id=role.role_id,
                                start_date=start_dt,
                                end_date=end_dt,
                                created_by="resume_parser"
                            )
                            db.add(work_exp)
                            logger.info("NAV----> candidate experience added to db")
            
            # Create Resume record linking to candidate and attachment
            resume_record = Resume(
                embedding=vector,
                candidate_id=candidate.candidate_id,
                attachment_id=attachment_id,
                created_by="resume_parser"
            )
            db.add(resume_record)
            db.flush()
            
            logger.info(f'Successfully saved resume for {info.get("name", "Unknown")}')
            
        except Exception as e:
            logger.error(f"Error saving resume: {e}")
            db.rollback()
            continue
    
    db.commit()
    db.close()

def save_to_faiss(resumes, save_path=VECTORDB_PATH):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    docs = []
    metadatas = []
    for r in resumes:
        # Use JSON string as text to embed
        text_to_embed = json.dumps(r, ensure_ascii=False)
        chunks = splitter.split_text(text_to_embed)
        docs.extend(chunks)
        metadatas.extend([{"file_name": r.get("file_name", "")}] * len(chunks))
    embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectordb = FAISS.from_texts(docs, embedding=embedding, metadatas=metadatas)
    vectordb.save_local(save_path)
    logger.info("[INFO] FAISS index saved")
    return vectordb

def extract_text_from_pdf(path):
    text = ""
    try:
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        logger.info(f"[ERROR] PDF read failed: {path} -> {e}")
    return text

def extract_text_from_docx(path):
    text = ""
    try:
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.info(f"[ERROR] DOCX read failed: {path} -> {e}")
    return text

def extract_basic_info(resume_text):
    """Use local Ollama LLM to extract structured info from resume text."""

    logger.info("This section executed -----> ")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    prompt = """
		You are a highly accurate resume parser.
	
		Extract structured candidate information from the given resume.
	
		Return ONLY valid JSON.
		Do NOT add explanation.
		Do NOT add any text before or after JSON.
	
		STRICT JSON FORMAT:
	
		{
			"name": "",
			"total_experience": 0,
			"email": "",
			"phone_number": "",
			"location": "",
			"skills": [],
			"education": [
				{
					"qualification": "",
					"institution": "",
					"percentage": "",
					"passout_year": ""
				}
			],
			"work_experience": [
				{
					"company_name": "",
					"role": "",
					"start_date": "",
					"end_date": ""
				}
			]
		}
	
		STRICT RULES:
	
		1. ALWAYS return all keys. Do NOT skip any field.
	
		2. If any value is missing:
		- Use "" for strings
		- Use 0 for total_experience
		- Use [] for arrays
	
		3. DO NOT return null.
	
		4. total_experience must be a NUMBER (years).
	
		5. skills must be SHORT keywords (e.g., "Python", "SQL", "Communication").
		Do NOT return full sentences.
	
		6. DATE NORMALIZATION (VERY IMPORTANT):
		- Convert all dates to format:
			YYYY-MM (e.g., 2016-06)
			OR YYYY (e.g., 2016)
		- Examples:
			"June 2016" → "2016-06"
			"Feb 2017" → "2017-02"
			"2018" → "2018"
		- If only month/year given → convert to YYYY-MM
		- If invalid text like "Year 11" → return ""
	
		7. passout_year must be ONLY a YEAR (YYYY).
		- If not a valid year → return ""
	
		8. work_experience dates must ALWAYS follow YYYY-MM or YYYY.
		- If end_date is "present" → return "Present"
	
		9. DO NOT include words like:
		- "June", "Feb", "Year 11", "Currently"
		Only return normalized values.
	
		10. Do NOT guess missing data.
	
		11. Ensure output is valid JSON (parsable).
	
		IMPORTANT:
		- No extra text
		- No trailing commas
		- Strict JSON only
		"""
    try:
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": "You output only JSON."},
                {"role": "user", "content": prompt + "\n\nResume:\n" + resume_text[:4000]}
            ]
        )
        logger.info(f'NAV----> before content')
        content = response["message"]["content"].strip()
        logger.info(f"NAv----> content {content}")
        # clean JSON
        start = content.find("{")
        end = content.rfind("}") + 1
        logger.info(f"NAV---> start {start}")
        logger.info(f"NAV---> end {end}")
        json_str = content[start:end]
        return json.loads(json_str)
    
    except Exception as e:
        logger.info(f"[ERROR] LLM parse failed: {e}")
        return None

# def process_resumes(folder_path:str, message_id: int):
#     start = time.time()
#     base_dir = os.getcwd() 
#     db = SessionLocal()
#     # folder_path =os.path.join(base_dir, "atttachments")
#     folder_path = "Resumes"
#     results = []

#     for file in os.listdir(folder_path):
#         existing = db.query(Resume).filter(Resume.file_name == file).first()

#         if existing:
#             logger.info(f"Skipping already processed file: {file}")
#             continue

#         path = os.path.join(folder_path, file)
#         if file.lower().endswith(".pdf"):
#             text = extract_text_from_pdf(path)
#         elif file.lower().endswith(".docx"):
#             text = extract_text_from_docx(path)
#         else:
#             continue

#         if not text.strip():
#             logger.info(f"[WARN] Empty: {file}")
#             continue

#         logger.info(f"[LLM] Extracting: {file}")
#         info = extract_basic_info(text)
#         if info:
#             info["file_name"] = file
#             # results.append(info)cls
#             results.append({
#                 "info": info,
#                 "text": text
#             })

#     if results:
#         logger.info(f"NACV----> This result section executed {results}")
#         save_to_faiss(results)
#         save_resumes_to_db(results)
#     logger.info(f"\n[TIME] {round(time.time()-start,2)} sec")
#     return os.listdir()

def process_resumes(email_id: UUID) -> dict:
    """
    This function processes resumes from email attachments. It performs the following    steps:
        1. Fetches the email and its attachments using the provided message_id. It looks for attachments marked as resumes in the database.
        2. For each resume attachment, it extracts text content (supports PDF and DOCX formats).
        3. Uses a local Ollama LLM (llama3) to extract structured information such as name, experience, skills, companies, and education.
        4. Generates vector embeddings for the resume text using the HuggingFace model `all-MiniLM-L6-v2`.
        5. Stores the extracted resume data in the PostgreSQL database, linking it to the email.
        6. Saves vector embeddings in a FAISS vector database for semantic search.
    """
    
    logger.info("NAV----> the process resume function called")
    db = SessionLocal()
    email_obj = db.query(EmailLogs).filter(
        EmailLogs.email_id == email_id
    ).first()

    if not email_obj:
        return {"message": "Email not found"}
    attachments = db.query(Attachment).filter(
        Attachment.email_id == email_obj.email_id,
        Attachment.is_resume == True
    ).all()
    logger.info("NAV----> the attachments fetched successfully")
    results = []

    for att in attachments:
        file_path = f"attachments/{att.file_name}"
        if file_path.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
            logger.info(f"NAV----> the text extracted from pdf {text[:100]}...")
        elif file_path.endswith(".docx"):
            text = extract_text_from_docx(file_path)
            logger.info(f"NAV----> the text extracted from docx {text[:100]}...")
        else:
            continue

        if not text.strip():
            continue

        info = extract_basic_info(text)
        if info:
            info["file_name"] = att.file_name
            results.append({
                "info": info,
                "text": text,
                "attachment_id": att.attachment_id,
                "sender_email": parse_email_address(email_obj.sender)
            })
        logger.info("NAV----> the info extracted successfully")
    if results:
        # save_to_faiss(results)
        logger.info(f"NACV----> This result section executed {results}")
        save_resumes_to_db(results)

    db.close()

    return {
        "message_id": str(email_id),
        "processed_files": len(results)
    }

def search_resumes(filters: dict):
    """Search candidates based on dynamic filters using aggregation subqueries."""

    import time as _time
    start_time = _time.time()
    logger.info("[search_resumes] Called with filters: %s", filters)

    if not filters or not isinstance(filters, dict):
        logger.warning("[search_resumes] Received empty or invalid filters dict")
        return [{"total_record": 0}]

    db = SessionLocal()
    try:
        candidate_education = (
            db.query(
                CandidateEducation.candidate_id.label("candidate_id"),
                func.json_agg(
                    func.json_build_object(
                        "education_id", Education.education_id,
                        "education", Education.education,
                        "institution", CandidateEducation.institution,
                        "percentage", CandidateEducation.percentage,
                        "year_of_passed", CandidateEducation.year_of_passed
                    )
                ).label("education")
            )
            .select_from(CandidateEducation)
            .join(Education, CandidateEducation.education_id == Education.education_id)
            .group_by(CandidateEducation.candidate_id)
            .subquery()
        )

        candidate_skills = (
            db.query(
                CandidateSkills.candidate_id.label("candidate_id"),
                func.json_agg(
                    func.json_build_object(
                        "skill_id", Skill.skill_id,
                        "skill", Skill.skill
                    )
                ).label("skills")
            )
            .select_from(CandidateSkills)
            .join(Skill, CandidateSkills.skill_id == Skill.skill_id)
            .group_by(CandidateSkills.candidate_id)
            .subquery()
        )

        candidate_work_exp = (
            db.query(
                WorkExperience.candidate_id.label("candidate_id"),
                func.json_agg(
                    func.json_build_object(
                        "role_id", Role.role_id,
                        "role", Role.role,
                        "company_name", Company.company_name,
                        "company_location", Company.company_location,
                        "start_date", WorkExperience.start_date,
                        "end_date", WorkExperience.end_date,
                        "is_present", WorkExperience.is_active
                    )
                ).label("work_experience")
            )
            .select_from(WorkExperience)
            .join(Role, WorkExperience.role_id == Role.role_id)
            .join(Company, WorkExperience.company_id == Company.company_id)
            .group_by(WorkExperience.candidate_id)
            .subquery()
        )

        conditions = [Candidate.is_active == True]

        name = filters.get("name")
        if name:
            name = str(name).strip()
            if name:
                conditions.append(Candidate.name.ilike(f"%{name}%"))

        exp_min = filters.get("min_experience")
        if exp_min is not None and exp_min != "":
            try:
                conditions.append(Candidate.total_experience >= float(exp_min))
            except (ValueError, TypeError):
                pass

        exp_max = filters.get("max_experience")
        if exp_max is not None and exp_max != "":
            try:
                conditions.append(Candidate.total_experience <= float(exp_max))
            except (ValueError, TypeError):
                pass

        skills_filter = filters.get("skills")
        if skills_filter:
            if not isinstance(skills_filter, list):
                logger.warning("[search_resumes] skills must be a list, got %s", type(skills_filter).__name__)
            else:
                valid_skills = [s for s in skills_filter if s and isinstance(s, str)]
                if valid_skills:
                    logger.debug("[search_resumes] Applying skills filter with %d UUIDs", len(valid_skills))
                    conditions.append(
                        Candidate.candidate_id.in_(
                            db.query(CandidateSkills.candidate_id).filter(
                                CandidateSkills.skill_id.in_(valid_skills)
                            )
                        )
                    )

        companies = filters.get("companies")
        if companies:
            if not isinstance(companies, list):
                logger.warning("[search_resumes] companies must be a list, got %s", type(companies).__name__)
            else:
                company_ids = []
                for comp in companies:
                    comp = str(comp).strip()
                    if not comp:
                        continue
                    matched = db.query(Company).filter(
                        Company.company_name.ilike(f"%{comp}%")
                    ).all()
                    if matched:
                        company_ids.extend([c.company_id for c in matched])
                        logger.debug("[search_resumes] Company '%s' matched %d records", comp, len(matched))
                    else:
                        logger.debug("[search_resumes] No companies matched name: '%s'", comp)
                if company_ids:
                    conditions.append(
                        Candidate.candidate_id.in_(
                            db.query(WorkExperience.candidate_id).filter(
                                WorkExperience.company_id.in_(company_ids)
                            )
                        )
                    )

        education_vals = filters.get("education")
        if education_vals:
            if not isinstance(education_vals, list):
                logger.warning("[search_resumes] education must be a list, got %s", type(education_vals).__name__)
            else:
                valid_edu = [e for e in education_vals if e and isinstance(e, str)]
                if valid_edu:
                    logger.debug("[search_resumes] Applying education filter with %d UUIDs", len(valid_edu))
                    conditions.append(
                        Candidate.candidate_id.in_(
                            db.query(CandidateEducation.candidate_id).filter(
                                CandidateEducation.education_id.in_(valid_edu)
                            )
                        )
                    )

        roles = filters.get("roles")
        if roles:
            if not isinstance(roles, list):
                logger.warning("[search_resumes] roles must be a list, got %s", type(roles).__name__)
            else:
                valid_roles = [r for r in roles if r and isinstance(r, str)]
                if valid_roles:
                    logger.debug("[search_resumes] Applying roles filter with %d UUIDs", len(valid_roles))
                    conditions.append(
                        Candidate.candidate_id.in_(
                            db.query(WorkExperience.candidate_id).filter(
                                WorkExperience.role_id.in_(valid_roles)
                            )
                        )
                    )

        passout_start = filters.get("passout_start_year")
        passout_end = filters.get("passout_end_year")
        if passout_start is not None or passout_end is not None:
            year_conditions = []
            if passout_start is not None and passout_start != "":
                try:
                    ps_val = int(passout_start)
                    year_conditions.append(CandidateEducation.year_of_passed >= ps_val)
                    logger.debug("[search_resumes] Applying passout_start_year: %d", ps_val)
                except (ValueError, TypeError):
                    logger.warning(
                        "[search_resumes] Invalid passout_start_year: '%s', skipping", passout_start
                    )
            if passout_end is not None and passout_end != "":
                try:
                    pe_val = int(passout_end)
                    year_conditions.append(CandidateEducation.year_of_passed <= pe_val)
                    logger.debug("[search_resumes] Applying passout_end_year: %d", pe_val)
                except (ValueError, TypeError):
                    logger.warning(
                        "[search_resumes] Invalid passout_end_year: '%s', skipping", passout_end
                    )
            if year_conditions:
                conditions.append(
                    Candidate.candidate_id.in_(
                        db.query(CandidateEducation.candidate_id).filter(and_(*year_conditions))
                    )
                )

        percentage = filters.get("percentage")
        if percentage is not None and percentage != "":
            try:
                pct_val = float(percentage)
                logger.debug("[search_resumes] Applying percentage filter: >= %s", pct_val)
                conditions.append(
                    Candidate.candidate_id.in_(
                        db.query(CandidateEducation.candidate_id).filter(
                            CandidateEducation.percentage >= pct_val
                        )
                    )
                )
            except (ValueError, TypeError):
                logger.warning("[search_resumes] Invalid percentage value: '%s', skipping", percentage)

        logger.info("[search_resumes] Total filter conditions built: %d", len(conditions))

        total_count = (
            db.query(func.count(Candidate.candidate_id))
            .filter(and_(*conditions))
            .scalar()
        ) or 0
        logger.info("[search_resumes] Total matching records: %d", total_count)

        query = (
            db.query(
                func.json_build_object(
                    "candidate_id", Candidate.candidate_id,
                    "name", Candidate.name,
                    "email", Candidate.email_address,
                    "phone_number", Candidate.phone_number,
                    "location", Candidate.location,
                    "total_experience", Candidate.total_experience,
                    "education", func.coalesce(candidate_education.c.education, cast('[]', JSON)),
                    "skills", func.coalesce(candidate_skills.c.skills, cast('[]', JSON)),
                    "work_experience", func.coalesce(candidate_work_exp.c.work_experience, cast('[]', JSON))
                ).label("candidate_info")
            )
            .select_from(Candidate)
            .outerjoin(candidate_education, Candidate.candidate_id == candidate_education.c.candidate_id)
            .outerjoin(candidate_skills, Candidate.candidate_id == candidate_skills.c.candidate_id)
            .outerjoin(candidate_work_exp, Candidate.candidate_id == candidate_work_exp.c.candidate_id)
            .filter(and_(*conditions))
        )

        sort_by = filters.get("sort_by")
        sort_order = (filters.get("sort_order") or "asc").lower()
        sort_map = {
            "name": Candidate.name,
            "total_experience": Candidate.total_experience,
            "created_at": Candidate.created_at,
        }

        if sort_by and sort_by in sort_map:
            sort_col = sort_map[sort_by]
            query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
            logger.debug("[search_resumes] Sorting by %s %s", sort_by, sort_order)
        elif sort_by:
            logger.warning("[search_resumes] Unknown sort_by field: '%s', ignoring", sort_by)

        page = max(1, int(filters.get("page", 1) or 1))
        page_size = max(1, min(100, int(filters.get("page_size", 20) or 20)))
        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)
        logger.info("[search_resumes] Pagination: page=%d, page_size=%d, offset=%d", page, page_size, offset)

        data = query.all()
        logger.info("[search_resumes] Query returned %d candidate records", len(data))

        results = [row.candidate_info for row in data]
        results.append({"total_record": total_count})

        elapsed = round(_time.time() - start_time, 3)
        logger.info(
            "[search_resumes] Completed in %ss | returned %d candidates, total_record=%d",
            elapsed, len(results) - 1, total_count
        )
        return results

    except Exception as e:
        logger.error("[search_resumes] Unexpected error: %s", str(e), exc_info=True)
        raise
    finally:
        db.close()
        logger.debug("[search_resumes] Database session closed")

def get_query_embedding(query: str):
    logger.debug("[get_query_embedding] Generating embedding for query: '%s'", query[:80])
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    return embedding_model.embed_query(query)

def semantic_search_resumes(query: str, top_k: int = 5):
    """Perform semantic search on resumes using vector embeddings."""

    logger.info("[semantic_search] Called with query='%s', top_k=%d", query[:80], top_k)

    if not query or not isinstance(query, str) or not query.strip():
        logger.warning("[semantic_search] Empty or invalid query received")
        return []

    if not isinstance(top_k, int) or top_k < 1:
        logger.warning("[semantic_search] Invalid top_k=%s, defaulting to 5", top_k)
        top_k = 5

    db = SessionLocal()
    try:
        query_embedding = get_query_embedding(query)
        logger.debug("[semantic_search] Embedding generated, executing vector search")

        sql = text("""
            SELECT 
                r.resume_id,
                c.candidate_id,
                c.name,
                c.email_address,
                c.total_experience,
                r.embedding <=> CAST(:query_embedding AS vector) as similarity_distance
            FROM resumes r
            JOIN candidates c ON r.candidate_id = c.candidate_id
            ORDER BY similarity_distance ASC
            LIMIT :top_k
        """)

        results = db.execute(
            sql, 
            {
                "query_embedding": query_embedding,
                "top_k": top_k
            }
        ).fetchall()

        logger.info("[semantic_search] Returned %d results", len(results))
        return results
    except Exception as e:
        logger.error("[semantic_search] Error during vector search: %s", str(e), exc_info=True)
        raise
    finally:
        db.close()
        logger.debug("[semantic_search] Database session closed")

def get_master_data():
    """Fetch active data from master tables: Roles, Education, Skills."""
    
    logger.info("[get_master_data] Fetching master data")
    db = SessionLocal()
    try:
        roles = db.query(Role).filter(Role.is_active == True).all()
        educations = db.query(Education).filter(Education.is_active == True).all()
        skills = db.query(Skill).filter(Skill.is_active == True).all()
        
        logger.info(
            "[get_master_data] Fetched %d roles, %d educations, %d skills",
            len(roles), len(educations), len(skills)
        )
        return {
            "roles": [{"id": str(r.role_id), "name": r.role} for r in roles],
            "education": [{"id": str(e.education_id), "name": e.education} for e in educations],
            "skills": [{"id": str(s.skill_id), "name": s.skill} for s in skills]
        }
    except Exception as e:
        logger.error("[get_master_data] Error fetching master data: %s", str(e), exc_info=True)
        raise
    finally:
        db.close()