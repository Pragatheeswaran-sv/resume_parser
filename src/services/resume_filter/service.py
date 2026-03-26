import os
import re
import json
import logging
from uuid import UUID
import datetime as dt
import ollama
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from db.connection import SessionLocal
from src.resume_filter.models import Resume
from sqlalchemy import select, and_, cast, String, text
from sqlalchemy.orm import joinedload
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
            logger.info(f'NAV----> the info extracted {info}')
            vector = embedding_model.embed_query(raw_text)
            logger.info(f'NAV----> the email {info.get("email")}...')
            # Check for existing candidate by email/phone to avoid duplicates
            existing_candidate = None
            if info.get("email"):
                existing_candidate = db.query(Candidate).filter(
                    Candidate.email_address == info.get("email")
                ).first()
            if not existing_candidate and info.get("phone_number"):
                existing_candidate = db.query(Candidate).filter(
                    Candidate.phone_number == info.get("phone_number")
                ).first()

            if existing_candidate:
                candidate = existing_candidate
                logger.info(f'Using existing candidate: {candidate.candidate_id}')
            else:
                candidate = Candidate(
                    name=info.get("name", ""),
                    email_address=info.get("email", ""),
                    phone_number=info.get("phone_number", ""),
                    location=info.get("location", ""),
                    total_experience=normalize_experience(info.get("total_experience")),
                    created_by="resume_parser"
                )
                db.add(candidate)
                db.flush()
            
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

    results = []

    for att in attachments:
        file_path = f"attachments/{att.file_name}"
        if file_path.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        elif file_path.endswith(".docx"):
            text = extract_text_from_docx(file_path)
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
                "attachment_id": att.attachment_id
            })

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
    """Search resumes based on dynamic filters using relationships."""
    
    db = SessionLocal()
    try:
        query = select(Resume).options(
            joinedload(Resume.canditate)
        )
        conditions = []
        
        name = filters.get("name")
        if name:
            conditions.append(Candidate.name.ilike(f"%{name}%"))
        
        exp_min = filters.get("experience_min")
        if exp_min is not None:
            conditions.append(Candidate.total_experience >= exp_min)
        
        exp_max = filters.get("experience_max")
        if exp_max is not None:
            conditions.append(Candidate.total_experience <= exp_max)
        
        skills = filters.get("skills")
        if skills:
            for skill in skills:
                logger.info("NAV----> searching for skill: %s", skill)
                skill_obj = db.query(Skill).filter(
                    Skill.skill.ilike(f"%{skill}%")
                ).all()
                if skill_obj:
                    skill_ids = [s.skill_id for s in skill_obj]
                    conditions.append(
                        Resume.candidate_id.in_(
                            db.query(CandidateSkills.candidate_id).filter(
                                CandidateSkills.skill_id.in_(skill_ids)
                            )
                        )
                    )
        
        companies = filters.get("companies")
        if companies:
            for comp in companies:
                company_obj = db.query(Company).filter(
                    Company.company_name.ilike(f"%{comp}%")
                ).all()
                if company_obj:
                    company_ids = [c.company_id for c in company_obj]
                    conditions.append(
                        Resume.candidate_id.in_(
                            db.query(WorkExperience.candidate_id).filter(
                                WorkExperience.company_id.in_(company_ids)
                            )
                        )
                    )
        
        education = filters.get("education")
        if education:
            for edu in education:
                education_obj = db.query(Education).filter(
                    Education.education.ilike(f"%{edu}%")
                ).all()
                if education_obj:
                    education_ids = [e.education_id for e in education_obj]
                    conditions.append(
                        Resume.candidate_id.in_(
                            db.query(CandidateEducation.candidate_id).filter(
                                CandidateEducation.education_id.in_(education_ids)
                            )
                        )
                    )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        results = db.execute(query).unique().scalars().all()
        return results
    finally:
        db.close()

def get_query_embedding(query: str):
    embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    return embedding_model.embed_query(query)

def semantic_search_resumes(query: str, top_k: int = 5):
    """Perform semantic search on resumes using vector embeddings."""

    db = SessionLocal()
    try:
        query_embedding = get_query_embedding(query)
        # Use PostgreSQL vector similarity search via vector operator <=>
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

        return results
    finally:
        db.close()

def get_master_data():
    """Fetch active data from master tables: Roles, Education, Skills."""
    
    db = SessionLocal()
    try:
        roles = db.query(Role).filter(Role.is_active == True).all()
        educations = db.query(Education).filter(Education.is_active == True).all()
        skills = db.query(Skill).filter(Skill.is_active == True).all()
        
        return {
            "roles": [{"id": str(r.role_id), "name": r.role} for r in roles],
            "education": [{"id": str(e.education_id), "name": e.education} for e in educations],
            "skills": [{"id": str(s.skill_id), "name": s.skill} for s in skills]
        }
    finally:
        db.close()