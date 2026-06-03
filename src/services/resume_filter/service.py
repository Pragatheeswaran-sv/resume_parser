import os
import re
import json
import logging
from uuid import UUID
import datetime as dt
import zipfile
from lxml import etree
import pandas as pd
from alembic.util import status
from fastapi import HTTPException
import ollama
from dotenv import load_dotenv
from email.utils import parseaddr
from pypdf import PdfReader
from docx import Document
from db.connection import SessionLocal
from src.resume_filter.models import Resume
from sqlalchemy import JSON, Float, Integer, select, and_, cast, String, text, func, or_
from sqlalchemy.orm import aliased, joinedload
from src.email_reader.models import EmailLogs, Attachment
from src.candidate.models import (
    Candidate, CandidateSkills, CandidateEducation, 
    WorkExperience, Skill, Education, Company, Role
)
from src.services.admin.service import get_model
from src.admin.models import Admin, AiModel, AiModelConfig, AiModelversion

from openai import OpenAI
from anthropic import Anthropic

from src.utils.helper import calculate_match_score, clean_mobile_number, compress_file
BASE_DIR = "/app"  
EXPORT_PATH = os.path.join(BASE_DIR, "export_files")

load_dotenv()
logger = logging.getLogger(__name__)

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

    for r in resumes:
        try:
            info = r["info"]            
            attachment_id = r.get("attachment_id")
            sender_email = parse_email_address(r.get("sender_email", ""))
            logger.info(f' the info extracted {info}')

            info_email = (info.get("email") or "").strip().lower()
            extracted_role = info.get("role", "").strip()
            if not info_email and sender_email:
                logger.info(f' using sender email fallback: {sender_email}')
                info_email = sender_email

            email_address = info_email or sender_email or ""
            phone_number = (info.get("phone_number") or "").strip()
            phone_number = clean_mobile_number(phone_number)

            candidate = None
            if email_address:
                candidate = db.query(Candidate).filter(
                    func.lower(Candidate.email_address) == email_address.lower()
                ).first()

            if not candidate and phone_number:
                candidate = db.query(Candidate).filter(
                    Candidate.phone_number == phone_number
                ).first()

            if candidate:
                logger.info(" candidate already exists, reusing candidate_id")

                # Keep existing candidate fresh with any missing contact values.
                if not candidate.email_address and email_address:
                    candidate.email_address = email_address
                    candidate.email_from_sender = bool(sender_email and not info_email)
                if not candidate.phone_number and phone_number:
                    candidate.phone_number = phone_number
                db.add(candidate)
            else:
                candidate = Candidate(
                    name=info.get("name", ""),
                    email_address=email_address,
                    email_from_sender=bool(sender_email and not info_email),
                    phone_number=phone_number,
                    location=info.get("location", ""),
                    total_experience=normalize_experience(info.get("total_experience")),
                    created_by="resume_parser"
                )
                db.add(candidate)
                db.flush()
                logger.info(" candidate added to db")
            
            # Add skills
            skills_list = info.get("skills", [])
            logger.info(f' the skills {skills_list}...')
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
                            logger.info("new skills added to db")
                        is_skill = db.query(CandidateSkills).filter(CandidateSkills.candidate_id == candidate.candidate_id ,CandidateSkills.skill_id == skill.skill_id).first()
                        
                        if not is_skill:
                            candidate_skill = CandidateSkills(
                                candidate_id=candidate.candidate_id,
                                skill_id=skill.skill_id,
                                created_by="resume_parser"
                            )
                            db.add(candidate_skill)
                            logger.info("candidate skills added to db")
                        else:
                            logger.info('candidate skill already exists')
            # Add education from new structure (objects with qualification, institution, percentage, passout_year)
            education_list = info.get("education", [])
            logger.info(f' the education {education_list}...')
            if education_list:
                for edu_item in education_list:
                    if isinstance(edu_item, dict):
                        qualification = edu_item.get("qualification", "").strip()
                        institution = edu_item.get("institution", "").strip()
                        percentage = edu_item.get("percentage", "") 
                        try:
                            value = float(percentage.replace("%", "").strip())

                            # If value looks like CGPA (commonly <= 10), convert to percentage
                            if value <= 10:
                                percentage = str(round(value * 9.5, 2))
                            else:
                                percentage = str(value)

                        except ValueError:
                            percentage = ""
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
                                logger.info("new education added to db")
                            
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
                            is_education = db.query(CandidateEducation).filter(CandidateEducation.candidate_id == candidate.candidate_id, CandidateEducation.education_id == education_type.education_id).first()
                            if not is_education:
                                candidate_edu = CandidateEducation(
                                    candidate_id=candidate.candidate_id,
                                    education_id=education_type.education_id,
                                    institution=institution if institution else None,
                                    percentage=percentage_val,
                                    year_of_passed=year_passed,
                                    created_by="resume_parser"
                                )
                                db.add(candidate_edu)
                                logger.info("candidate education added to db")
                            else:
                                logger.info("candidate education already exists")
            
            # Add work experience from new structure (objects with company_name, role, start_date, end_date)
            work_experience_list = info.get("work_experience", [])
            logger.info(f' the work experience {work_experience_list}...')
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
                                logger.info(" new company added to db")
                            
                            # Get or create role
                            role_obj = db.query(Role).filter(
                                Role.role.ilike(role_name)
                            ).first()
                            
                            if not role_obj:
                                role_obj = Role(
                                    role=role_name,
                                    created_by="resume_parser"
                                )
                                db.add(role_obj)
                                db.flush()
                                logger.info(" new role added to db")
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
                            
                            is_work_exp = db.query(WorkExperience).filter(WorkExperience.candidate_id == candidate.candidate_id, WorkExperience.company_id == company.company_id, WorkExperience.role_id == role_obj.role_id).first()
                            if not is_work_exp:
                            # Create work experience record
                                work_exp = WorkExperience(
                                    candidate_id=candidate.candidate_id,
                                    company_id=company.company_id,
                                    role_id=role_obj.role_id,
                                    start_date=start_dt,
                                    end_date=end_dt,
                                    created_by="resume_parser"
                                )
                                db.add(work_exp)
                                logger.info("candidate experience added to db")
                            else:
                                logger.info("candidate experience already exists")
                                      
            is_resume_record = db.query(Resume).filter(
                Resume.candidate_id == candidate.candidate_id,
                Resume.candidate_role == extracted_role
            ).first()

            if is_resume_record:
                logger.info('Resume of candidate already exists')
            else:
                resume_record = Resume(
                    candidate_id=candidate.candidate_id,
                    attachment_id=attachment_id,
                    candidate_role=extracted_role,
                    created_by="resume_parser"
                )
                db.add(resume_record)
                db.flush()

                logger.info(f'Successfully saved resume for {candidate.name}')
            
        except Exception as e:
            logger.error(f"Error saving resume: {e}")
            db.rollback()
            continue

    try:
        db.commit()
    finally:
        db.close()

def extract_text_from_pdf(path):
    text = ""
    try:
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() or ""
        logger.info(f"Extracted text from PDF: {text}")  # Print first 200 chars for verification
    except Exception as e:
        logger.info(f"[ERROR] PDF read failed: {path} -> {e}")
    return text

def extract_docx_text(path):
    """
    Extract text from:
    - paragraphs
    - tables
    - textboxes
    - colored sections
    - shapes XML
    """

    full_text = []

    doc = Document(path)

    # Paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()

        if text:
            full_text.append(text)

    # Tables
    for table in doc.tables:
        for row in table.rows:
            row_text = []

            for cell in row.cells:
                cell_text = cell.text.strip()

                if cell_text:
                    row_text.append(cell_text)

            if row_text:
                full_text.append(" | ".join(row_text))

    
    with zipfile.ZipFile(path) as z:
        xml_content = z.read("word/document.xml")

    tree = etree.XML(xml_content)

    namespaces = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    }

    xml_texts = tree.xpath("//w:t/text()", namespaces=namespaces)

    for text in xml_texts:
        cleaned = text.strip()

        if cleaned and cleaned not in full_text:
            full_text.append(cleaned)

    # Remove duplicates while preserving order
    unique_text = list(dict.fromkeys(full_text))
    logger.info(f"Extracted text from DOCX: {' '.join(unique_text)}...")
    return "\n".join(unique_text)
    # return preprocess_resume_text("\n".join(unique_text))

def extract_text_from_docx(path):
    text = ""
    try:
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)
        logger.info(f"Extracted text from DOCX: {text}")  # Print first 100 chars for verification
    except Exception as e:
        logger.info(f"[ERROR] DOCX read failed: {path} -> {e}")
    return text

def is_resume(text: str) -> bool:
    """Classify whether a document is a resume/CV using the local LLM."""

    prompt = """ 
        You are a strict classifier.

        Return ONLY JSON:
        {"is_resume": true} or {"is_resume": false}

        Rules:
        - Return TRUE only if this is clearly a complete resume/CV
        - A resume MUST contain at least 2 of these sections:
        Skills, Experience, Education, Projects

        - Return FALSE if:
        - It is random text
        - It is invoice, email, report, or any other document
        - It looks like partial resume content

        - If unsure → return FALSE
        """

    try:
        db = SessionLocal()
        admin = db.query(Admin).filter(Admin.is_active == True).first()

        if not admin:   
            logger.warning("No admin found, defaulting to ollama with latest model")
            raise Exception("No admin found")
        
        admin_id = admin.admin_id

        model_info =( db.query(
            func.json_build_object(
                'model_name', AiModel.model_name,
                'model_version_name', AiModelversion.version_name,
                'apikey', AiModelConfig.apikey,
                'max_tokens', AiModelConfig.max_tokens,
                'temperature', AiModelConfig.temparature,
                'is_active', AiModelConfig.is_active
            )
        )
        .select_from(AiModelConfig).
        join(AiModel, AiModel.ai_model_id == AiModelConfig.ai_model_id).
        join(AiModelversion, AiModelversion.ai_model_version_id == AiModelConfig.ai_model_version_id).
        filter(AiModelConfig.is_active == True).
        first()
        )

        if not model_info:
            model_info = {}
        else:
            model_info = model_info[0]

        model = model_info.get("model_name", "ollama").lower()
        version = model_info.get("model_version_name", "llama3").lower()
        api_key = model_info.get("apikey") or None

        message = [
                    {"role": "system", "content": "You only return JSON"},
                    {"role": "user", "content": prompt + "\n\nDocument:\n" + text[:12000]}
                ]
        
        if model == "openai":
            if not api_key or api_key == None:
                raise Exception("OpenAI API key not found")

            client = OpenAI(api_key=api_key)

            response = client.chat.completions.create(
                model = version,
                messages = message
            )
            content = response.choices[0].message.content.strip()
            logger.info(f" the response from OpenAi {response}")
        elif model == "claude":
            if not api_key or api_key == None:
                raise Exception("Claude API key not found")

            client = Anthropic(api_key=api_key)

            response = client.messages.create(
                model=version,
                max_tokens=1000,
                system="You only return JSON",
                messages=[
                    {"role": "user", "content": prompt + "\n\nDocument:\n" + text[:12000]}
                ]
            )
            content = response.content[0].text.strip()
            logger.info(f" the response from Claude {response}")
        else:
            client = ollama
            response = client.chat(
                model = version,
                messages = message
            )
            logger.info(f" the response from Ollama {response}")
            content = response["message"]["content"].strip()

        try:
            start = content.find("{")
            end = content.rfind("}") + 1

            if start == -1 or end == 0:
                raise ValueError("No valid JSON object found in model response")

            json_str = content[start:end]
            data = json.loads(json_str)
            logger.info(f"is_resume classification result: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON returned by model: {content}")
            raise ValueError("Model returned invalid JSON") from e
        resume_state = data.get("is_resume", False)
        return resume_state

    except Exception as e:
        logger.error("Resume detection failed: %s", e)
        return False
    finally:
        db.close()

def extract_basic_info(resume_text):
    """Use local Ollama LLM to extract structured info from resume text."""
    logger.info('This process started=>>>>')
    logger.info("This extract_basic_info executed -----> ")
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
            "role": "",
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

        5. SKILLS EXTRACTION (STRICT): If a skill entry contains separators like ":", "-", "–", "—", or "|", discard everything before the first separator and extract only the content after it, then split by "," and return each item as an individual skill (e.g., "Cloud: AWS, GCP", "Cloud - AWS, GCP" → ["AWS","GCP"]); if no separator is present, extract skills normally as individual keywords; always return a flat list with no prefixes, no grouping, no sentences, and no duplicates. 
        Do NOT return full sentences.

        6. DATE NORMALIZATION (VERY IMPORTANT): Convert all dates to format YYYY-MM (e.g., 2016-06) OR YYYY (e.g., 2016); examples: "June 2016" -> "2016-06", "Feb 2017" -> "2017-02", "2018" -> "2018"; if only month/year given -> convert to YYYY-MM; if invalid text like "Year 11" -> return "".

        7. passout_year must be ONLY a YEAR (YYYY).
        - If not a valid year -> return ""

        8. EDUCATION PERCENTAGE EXTRACTION (STRICT):

        Extract percentage/CGPA/GPA only if explicitly mentioned near the education entry.

        Examples:
        - "85%" -> "85"
        - "CGPA 8.2" -> "77.9" (CGPA × 9.5)
        - "GPA 3.8/4" -> "95" ((GPA / 4) × 100)

        Return ONLY the final percentage value as string.

        Do NOT guess, mix values between education entries, or extract unrelated numbers.
        If no valid value exists, return "".

        9. work_experience dates must ALWAYS follow YYYY-MM or YYYY.
        - If end_date is "present" -> return "Present"

        10. DO NOT include words like:
        - "June", "Feb", "Year 11", "Currently"
        Only return normalized values.

        11. Do NOT guess missing data except for top-level role inference from skills.

        12. Ensure output is valid JSON (parsable).

        13. Infer top-level "role" ONLY from technical skills; do not use summary, titles, company, projects, responsibilities, certifications, education, or any other content. Keep it short and professional; if unclear, return "".

        14. Example mappings: Python/FastAPI/Django -> Python Developer, React/JS/HTML/CSS -> Frontend Developer, Node/Express/MongoDB -> Backend Developer, React+Node -> Full Stack Developer, Java/Spring -> Java Developer, Selenium/Testing -> QA Engineer, AWS/Docker/K8s/Jenkins -> DevOps Engineer, ML/NLP/TensorFlow -> Machine Learning Engineer, Power BI/Tableau/SQL -> Data Analyst, Python/Pandas/ETL -> Data Engineer, Kotlin/Java -> Android Developer, Swift/iOS -> iOS Developer, PHP/Laravel -> PHP Developer, C#/.NET -> .NET Developer.

        15. work_experience.role must be extracted only if explicitly mentioned; otherwise return "".

        IMPORTANT:
        - Top-level "role" must be based ONLY on skills.
        - Do NOT use any other information for top-level role inference.
        - No extra text
        - No trailing commas
        - Strict JSON only
        """
    try:
        db = SessionLocal()
        admin = db.query(Admin).filter(Admin.is_active == True).first()

        if not admin:   
            logger.warning("No admin found, defaulting to ollama with latest model")
            raise Exception("No admin found")
        
        admin_id = admin.admin_id
        model_info = get_model(page = 1, page_size = 100, sort_by = None, sort_order = None, filter_column = None, filter_value = None, admin_id = admin_id)

        model_info =( db.query(
            func.json_build_object(
                'model_name', AiModel.model_name,
                'model_version_name', AiModelversion.version_name,
                'apikey', AiModelConfig.apikey,
                'max_tokens', AiModelConfig.max_tokens,
                'temperature', AiModelConfig.temparature,
                'is_active', AiModelConfig.is_active
            )
        )
        .select_from(AiModelConfig).
        join(AiModel, AiModel.ai_model_id == AiModelConfig.ai_model_id).
        join(AiModelversion, AiModelversion.ai_model_version_id == AiModelConfig.ai_model_version_id).
        filter(AiModelConfig.is_active == True).
        first()
        )

        if not model_info:
            model_info = {}
        else:
            model_info = model_info[0]

        model = model_info.get("model_name", "llama3").lower()
        version = model_info.get("model_version_name", "latest").lower()
        api_key = model_info.get("apikey") or None
        
        message = [
                    {"role": "system", "content": "You only return JSON"},
                    {"role": "user", "content": prompt + "\n\nDocument:\n" + resume_text[:12000]}
                ]

        if model == "openai":
            if not api_key or api_key == None:
                raise Exception("OpenAI API key not found")

            client = OpenAI(api_key=api_key)

            response = client.chat.completions.create(
                model = version,
                messages = message
            )
            content = response.choices[0].message.content.strip()
            logger.info(f" the response from OpenAi {response}")
        elif model == "claude":
            if not api_key or api_key == None:
                raise Exception("Claude API key not found")

            client = Anthropic(api_key=api_key)

            response = client.messages.create(
                model=version,
                max_tokens=1000,
                system="You only return JSON",
                messages=[
                    {"role": "user", "content": prompt + "\n\nDocument:\n" + resume_text[:12000]}
                ]
            )
            content = response.content[0].text.strip()
            logger.info(f" the response from Claude {response}")
        else:
            client = ollama
            response = client.chat(
                model = version,
                messages = message
            )
            logger.info(f" the response from Ollama {response}")
            content = response["message"]["content"].strip()

        try:
            start = content.find("{")
            end = content.rfind("}") + 1

            if start == -1 or end == 0:
                raise ValueError("No valid JSON object found in model response")

            json_str = content[start:end]
            data = json.loads(json_str)
            logger.info(f"is_resume classification result: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON returned by model: {content}")
            raise ValueError("Model returned invalid JSON") from e
       
        return data
    
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

def clean_json_response(content):
    """
    Extract valid JSON from LLM response
    """
    if isinstance(content, dict):
        return content

    match = re.search(r"\{.*\}", content, re.DOTALL)

    if not match:
        raise ValueError("No valid JSON found in response")

    json_text = match.group(0)

    return json.loads(json_text)

def process_resumes(email_id: UUID) -> dict:
    """
    Classify and process resume attachments for a given email.

    Steps:
        1. Fetch all attachments for the email.
        2. Extract text and classify each attachment as resume or not (LLM).
        3. For confirmed resumes, extract structured info (name, skills, etc.).
        4. Store resume and candidate data in PostgreSQL.
    """

    logger.info("process_resumes called for email_id=%s", email_id)
    db = SessionLocal()
    try:
        email_obj = db.query(EmailLogs).filter(
            EmailLogs.email_id == email_id
        ).first()

        if not email_obj:
            return {"message": "Email not found"}

        all_attachments = db.query(Attachment).filter(
            Attachment.email_id == email_obj.email_id
        ).all()
        logger.info("Fetched %d attachments for classification", len(all_attachments))

        results = []
        file_path = ""
        attachment_ids = []
        for att in all_attachments:
            file_path = f"attachments/{att.file_name}"
            attachment_ids.append(att.attachment_id)
            if file_path.endswith(".pdf"):
                text = extract_text_from_pdf(file_path)
            elif file_path.endswith(".docx"):
                # text = extract_text_from_docx(file_path)
                text = extract_docx_text(file_path)
            else:
                continue

            if not text.strip():
                logger.info("Empty document, skipping: %s", att.file_name)
                continue

            resume_flag = is_resume(text)
            att.is_resume = resume_flag
            db.commit()
            logger.info("Classified %s — is_resume=%s", att.file_name, resume_flag)

            if resume_flag == False:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"{file_path} removed successfully")
                else:
                    logger.info(f"{file_path} does not exist")
                
            if not resume_flag:
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
            logger.info("Extracted info for %s", att.file_name)

        if results:
            logger.info("Saving %d resume(s) to DB", len(results))
            save_resumes_to_db(results)

        file_compress = compress_file(file_path)
        for att_id in attachment_ids:
            attachment = db.query(Attachment).filter(Attachment.attachment_id == att_id).first()
            attachment.file_name = file_compress
            db.commit()
            db.refresh(attachment)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"{file_path} removed successfully")
        logger.info(f'{file_compress}')
        
        return {
            "message_id": str(email_id),
            "processed_files": len(results)
        }
    finally:
        db.close()

def search_resumes(filters: dict, export: bool = False) -> list:
    import time as _time
    start_time = _time.time()
    logger.info("[search_resumes] Called with filters: %s", filters)
    if not filters or not isinstance(filters, dict):
        logger.warning("[search_resumes] Received empty or invalid filters dict")
        return [{"total_record": 0}]

    db = SessionLocal()
    try:
        filter_count = 0

        def _safe_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def _safe_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

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
                ).label("education"),
                func.max(CandidateEducation.year_of_passed).label("max_year_of_passed"),
                func.max(CandidateEducation.percentage).label("max_percentage"),
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

                func.count(WorkExperience.experience_id).label(
                    "work_exp_count"
                ),

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

        name_list = filters.get("name")
        if isinstance(name_list, list) and name_list:
            name_conditions = [Candidate.name.ilike(f"%{str(name).strip()}%") for name in name_list if str(name).strip()]
            if name_conditions:
                conditions.append(or_(*name_conditions))
                filter_count += 1
        elif isinstance(name_list, str) and name_list.strip():
            conditions.append(Candidate.name.ilike(f"%{name_list.strip()}%"))
            filter_count += 1

        min_exp = _safe_float(filters.get("min_experience"))
        if min_exp is not None:
            conditions.append(Candidate.total_experience >= min_exp)
            filter_count += 1

        max_exp = _safe_float(filters.get("max_experience"))
        if max_exp is not None:
            conditions.append(Candidate.total_experience <= max_exp)
            filter_count += 1

        skills = filters.get("skills")
        if isinstance(skills, list) and skills:
            conditions.append(
                Candidate.candidate_id.in_(
                    db.query(CandidateSkills.candidate_id).filter(
                        CandidateSkills.skill_id.in_(skills)
                    )
                )
            )
            filter_count += 1

        companies = filters.get("companies")
        if isinstance(companies, list) and companies:
            company_terms = [str(comp).strip() for comp in companies if str(comp).strip()]
            company_ids = []
            if company_terms:
                company_name_filters = [Company.company_name.ilike(f"%{term}%") for term in company_terms]
                company_ids = [
                    row.company_id
                    for row in db.query(Company.company_id).filter(or_(*company_name_filters)).all()
                ]

            if company_ids:
                conditions.append(
                    Candidate.candidate_id.in_(
                        db.query(WorkExperience.candidate_id).filter(
                            WorkExperience.company_id.in_(company_ids)
                        )
                    )
                )
                filter_count += 1

        roles = filters.get("roles")
        if isinstance(roles, list) and roles:
            role_terms = [str(role).strip() for role in roles if str(role).strip()]
            role_ids = []
            if role_terms:
                role_numeric_ids = [rid for rid in (_safe_int(role) for role in role_terms) if rid is not None]
                role_name_filters = [Role.role.ilike(f"%{term}%") for term in role_terms]
                role_filters = list(role_name_filters)
                if role_numeric_ids:
                    role_filters.append(Role.role_id.in_(role_numeric_ids))
                role_ids = [
                    row.role_id
                    for row in db.query(Role.role_id).filter(
                        or_(*role_filters)
                    ).all()
                ]
            
            if role_ids:
                conditions.append(
                    Candidate.candidate_id.in_(
                        db.query(WorkExperience.candidate_id).filter(
                            WorkExperience.role_id.in_(role_ids)
                        )
                    )
                )
                filter_count += 1

        education = filters.get("education")
        if isinstance(education, list) and education:
            conditions.append(
                Candidate.candidate_id.in_(
                    db.query(CandidateEducation.candidate_id).filter(
                        CandidateEducation.education_id.in_(education)
                    )
                )
                )
            filter_count += 1

        year_conditions = []
        passout_start_year = _safe_int(filters.get("passout_start_year"))
        if passout_start_year is not None:
            year_conditions.append(func.max(CandidateEducation.year_of_passed) >= passout_start_year)

        passout_end_year = _safe_int(filters.get("passout_end_year"))
        if passout_end_year is not None:
            year_conditions.append(func.max(CandidateEducation.year_of_passed) <= passout_end_year)

        if year_conditions:
            conditions.append(
                Candidate.candidate_id.in_(
                    db.query(CandidateEducation.candidate_id)
                    .join(Education, Education.education_id == CandidateEducation.education_id)
                    .group_by(CandidateEducation.candidate_id)
                    .having(and_(*year_conditions))
                )
            )
            filter_count += 1

        percentage = _safe_float(filters.get("percentage"))
        if percentage is not None:
            conditions.append(
                Candidate.candidate_id.in_(
                    db.query(CandidateEducation.candidate_id).filter(
                        CandidateEducation.percentage >= percentage
                    )
                )
            )
            filter_count += 1

        logger.info("[search_resumes] Total filter conditions built: %d", len(conditions))

        total_count = (
            db.query(func.count(Candidate.candidate_id))
            .filter(and_(*conditions))
            .scalar()
        ) or 0

        candidate_resumes = (
            db.query(
                Resume.candidate_id.label("candidate_id"),

                func.count(Resume.resume_id).label("resume_count"),

                func.json_agg(
                    func.json_build_object(
                        "resume_id", Resume.resume_id,
                        "candidate_role", Resume.candidate_role,
                        "file_name", Attachment.file_name
                    )
                ).label("resumes")
            )
            .select_from(Resume)
            .join(
                Attachment,
                Resume.attachment_id == Attachment.attachment_id
            )
            .group_by(Resume.candidate_id)
            .subquery()
        )


        # Subquery to get the most recent resume for each candidate
        recent_resume_subq = (
            db.query(
                Resume.candidate_id,
                Resume.resume_id,
                Resume.candidate_role,
                func.row_number().over(
                    partition_by=Resume.candidate_id,
                    order_by=Resume.created_at.desc()
                ).label("rn")
            )
            .subquery()
        )
        query = (
            db.query(
                func.json_build_object(
                    "candidate_id", Candidate.candidate_id,
                    "name", Candidate.name,
                    "email", Candidate.email_address,
                    "phone_number", Candidate.phone_number,
                    "location", Candidate.location,
                    "total_experience", Candidate.total_experience,
                    "resume_id", recent_resume_subq.c.resume_id,
                    "candidate_role", func.coalesce(recent_resume_subq.c.candidate_role, ""),
                    'resume_count', func.coalesce(candidate_resumes.c.resume_count, 0),
                    'resumes', func.coalesce(candidate_resumes.c.resumes, cast('[]', JSON)),
                    "education", func.coalesce(candidate_education.c.education, cast('[]', JSON)),
                    "skills", func.coalesce(candidate_skills.c.skills, cast('[]', JSON)),
                    "work_experience", func.coalesce(candidate_work_exp.c.work_experience, cast('[]', JSON)),
                    "company_count", func.coalesce(candidate_work_exp.c.work_exp_count, 0)
                ).label("candidate_info")
            )
            .select_from(Candidate)
            .outerjoin(candidate_education, Candidate.candidate_id == candidate_education.c.candidate_id)
            .outerjoin(candidate_skills, Candidate.candidate_id == candidate_skills.c.candidate_id)
            .outerjoin(candidate_work_exp, Candidate.candidate_id == candidate_work_exp.c.candidate_id)
            .outerjoin(
                recent_resume_subq,
                and_(
                    Candidate.candidate_id == recent_resume_subq.c.candidate_id,
                    recent_resume_subq.c.rn == 1
                )
            )
            .outerjoin(
                candidate_resumes,
                Candidate.candidate_id == candidate_resumes.c.candidate_id
            )
            .filter(and_(*conditions))
        )

        sort_map = {
            "name": Candidate.name,
            "total_experience": Candidate.total_experience,
            "created_at": Candidate.created_at,
            "location": Candidate.location,
            "email": Candidate.email_address,
            "year_of_passed": cast(candidate_education.c.max_year_of_passed, Integer),
            "percentage": cast(candidate_education.c.max_percentage, Float),
        }

        sort_by = filters.get("sort_by")
        sort_order = (filters.get("sort_order") or "asc").lower()

        if sort_by in sort_map:
            col = sort_map[sort_by]
            query = query.order_by(col.desc() if sort_order == "desc" else col.asc())
        
        if not os.path.exists(EXPORT_PATH):
            logger.info(f"Export directory does not exist, creating: {EXPORT_PATH}")
            os.makedirs(EXPORT_PATH)

        if export:
            export_file = os.path.join(EXPORT_PATH, f"exported_resumes_{str(dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))}.csv")
            logger.info(f"Exporting results to {export_file}")
            all_data = query.all()
            if all_data:
                df = pd.DataFrame([row.candidate_info for row in all_data])
                df.to_csv(export_file, index=False)
                logger.info(f"Export completed successfully: {export_file}")
                result = {"file_path": export_file[4:]} 
                # print('export result-->', result)
                return result
            else:
                logger.info("No data to export")
                return {"file_path": "No data to export"}

        page = _safe_int(filters.get("page", 1)) or 1
        page_size = _safe_int(filters.get("page_size", 20)) or 20
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        query = query.limit(page_size).offset((page - 1) * page_size)

        data = query.all()
        jd_role = filters.get("roles") or []
        jd_role = db.query(Role.role).filter(Role.role_id.in_(jd_role)).first()
        jd_skill = filters.get("skills") or []
        jd_skills = [skill.skill for skill in db.query(Skill.skill).filter(Skill.skill_id.in_(jd_skill)).all()]
        jd_exp = filters.get("max_experience", 0)
        results = []
        for row in data:
            candidate_info = row.candidate_info
            candidate_skills_list = candidate_info.get("skills", [])
            rate_skill = [item.get("skill") for item in candidate_skills_list if item.get("skill")]
            rate_experience = candidate_info.get("total_experience", 0) or 0
            rate_role = candidate_info.get("candidate_role", "") or ""
            
            candidate_rating = calculate_match_score(
                jd_role,
                rate_role,
                jd_skills,
                rate_skill,
                jd_exp,
                rate_experience,
            )
            candidate_info["candidate_rating"] = candidate_rating.get("star_rating")
            results.append(candidate_info)

        results.append({"total_record": total_count})

        logger.info(
            "[search_resumes] Completed in %ss | returned %d candidates",
            round(_time.time() - start_time, 3),
            len(results) - 1
        )

        return results
        

    except Exception as e:
        logger.error("[search_resumes] Unexpected error: %s", str(e), exc_info=True)
        raise
    finally:
        db.close()

# def search_resumes(filters: dict):
#     import time as _time
#     start_time = _time.time()
#     logger.info("[search_resumes] Called with filters: %s", filters)
#     print('filtered=>',filters)
#     if not filters or not isinstance(filters, dict):
#         logger.warning("[search_resumes] Received empty or invalid filters dict")
#         return [{"total_record": 0}]

#     db = SessionLocal()
#     try:
#         candidate_education = (
#             db.query(
#                 CandidateEducation.candidate_id.label("candidate_id"),
#                 func.json_agg(
#                     func.json_build_object(
#                         "education_id", Education.education_id,
#                         "education", Education.education,
#                         "institution", CandidateEducation.institution,
#                         "percentage", CandidateEducation.percentage,
#                         "year_of_passed", CandidateEducation.year_of_passed
#                     )
#                 ).label("education"),
#                 func.max(CandidateEducation.year_of_passed).label("max_year_of_passed"),
#                 func.max(CandidateEducation.percentage).label("max_percentage"),
#             )
#             .select_from(CandidateEducation)
#             .join(Education, CandidateEducation.education_id == Education.education_id)
#             .group_by(CandidateEducation.candidate_id)
#             .subquery()
#         )

#         candidate_skills = (
#             db.query(
#                 CandidateSkills.candidate_id.label("candidate_id"),
#                 func.json_agg(
#                     func.json_build_object(
#                         "skill_id", Skill.skill_id,
#                         "skill", Skill.skill
#                     )
#                 ).label("skills")
#             )
#             .select_from(CandidateSkills)
#             .join(Skill, CandidateSkills.skill_id == Skill.skill_id)
#             .group_by(CandidateSkills.candidate_id)
#             .subquery()
#         )

#         candidate_work_exp = (
#             db.query(
#                 WorkExperience.candidate_id.label("candidate_id"),
#                 func.json_agg(
#                     func.json_build_object(
#                         "role_id", Role.role_id,
#                         "role", Role.role,
#                         "company_name", Company.company_name,
#                         "company_location", Company.company_location,
#                         "start_date", WorkExperience.start_date,
#                         "end_date", WorkExperience.end_date,
#                         "is_present", WorkExperience.is_active
#                     )
#                 ).label("work_experience")
#             )
#             .select_from(WorkExperience)
#             .join(Role, WorkExperience.role_id == Role.role_id)
#             .join(Company, WorkExperience.company_id == Company.company_id)
#             .group_by(WorkExperience.candidate_id)
#             .subquery()
#         )

#         conditions = [Candidate.is_active == True]

#         logger.info("[search_resumes] Total filter conditions built: %d", len(conditions))

#         total_count = (
#             db.query(func.count(Candidate.candidate_id))
#             .filter(and_(*conditions))
#             .scalar()
#         ) or 0

#         query = (
#             db.query(
#                 func.json_build_object(
#                     "candidate_id", Candidate.candidate_id,
#                     "name", Candidate.name,
#                     "email", Candidate.email_address,
#                     "phone_number", Candidate.phone_number,
#                     "location", Candidate.location,
#                     "total_experience", Candidate.total_experience,
#                     "education", func.coalesce(candidate_education.c.education, cast('[]', JSON)),
#                     "skills", func.coalesce(candidate_skills.c.skills, cast('[]', JSON)),
#                     "work_experience", func.coalesce(candidate_work_exp.c.work_experience, cast('[]', JSON))
#                 ).label("candidate_info")
#             )
#             .select_from(Candidate)
#             .outerjoin(candidate_education, Candidate.candidate_id == candidate_education.c.candidate_id)
#             .outerjoin(candidate_skills, Candidate.candidate_id == candidate_skills.c.candidate_id)
#             .outerjoin(candidate_work_exp, Candidate.candidate_id == candidate_work_exp.c.candidate_id)
#             .filter(and_(*conditions))
#         )

        
#         sort_by = filters.get("sort_by")
#         sort_order = (filters.get("sort_order") or "asc").lower()

#         sort_map = {
#             "name": Candidate.name,
#             "total_experience": Candidate.total_experience,
#             "created_at": Candidate.created_at,
#             "location": Candidate.location,
#             "email": Candidate.email_address,
#             "year_of_passed": candidate_education.c.max_year_of_passed,
#             "percentage": candidate_education.c.max_percentage,
#         }

#         if sort_by and sort_by in sort_map:
#             sort_col = sort_map[sort_by]
#             query = query.order_by(
#                 sort_col.desc() if sort_order == "desc" else sort_col.asc()
#             )
#             logger.debug("[search_resumes] Sorting by %s %s", sort_by, sort_order)
#         elif sort_by:
#             logger.warning("[search_resumes] Unknown sort_by field: '%s', ignoring", sort_by)

        
#         page = max(1, int(filters.get("page", 1) or 1))
#         page_size = max(1, min(100, int(filters.get("page_size", 20) or 20)))
#         offset = (page - 1) * page_size

#         query = query.limit(page_size).offset(offset)
#         data = query.all()

#         results = [row.candidate_info for row in data]
#         results.append({"total_record": total_count})
#         return results

#     except Exception as e:
#         logger.error("[search_resumes] Unexpected error: %s", str(e), exc_info=True)
#         raise
#     finally:
#         db.close()

# # def search_resumes(filters: dict):
#     """Search candidates based on dynamic filters using aggregation subqueries."""

#     import time as _time
#     start_time = _time.time()
#     logger.info("[search_resumes] Called with filters: %s", filters)

#     if not filters or not isinstance(filters, dict):
#         logger.warning("[search_resumes] Received empty or invalid filters dict")
#         return [{"total_record": 0}]

#     db = SessionLocal()
#     try:
#         candidate_education = (
#             db.query(
#                 CandidateEducation.candidate_id.label("candidate_id"),
#                 func.json_agg(
#                     func.json_build_object(
#                         "education_id", Education.education_id,
#                         "education", Education.education,
#                         "institution", CandidateEducation.institution,
#                         "percentage", CandidateEducation.percentage,
#                         "year_of_passed", CandidateEducation.year_of_passed
#                     )
#                 ).label("education"),
#                 func.max(Education.year_of_passed).label("max_year_of_passed"),
#                 func.max(Education.percentage).label("max_percentage"),
#             )
#             .select_from(CandidateEducation)
#             .join(Education, CandidateEducation.education_id == Education.education_id)
#             .group_by(CandidateEducation.candidate_id)
#             .subquery()
#         )

#         candidate_skills = (
#             db.query(
#                 CandidateSkills.candidate_id.label("candidate_id"),
#                 func.json_agg(
#                     func.json_build_object(
#                         "skill_id", Skill.skill_id,
#                         "skill", Skill.skill
#                     )
#                 ).label("skills")
#             )
#             .select_from(CandidateSkills)
#             .join(Skill, CandidateSkills.skill_id == Skill.skill_id)
#             .group_by(CandidateSkills.candidate_id)
#             .subquery()
#         )

#         candidate_work_exp = (
#             db.query(
#                 WorkExperience.candidate_id.label("candidate_id"),
#                 func.json_agg(
#                     func.json_build_object(
#                         "role_id", Role.role_id,
#                         "role", Role.role,
#                         "company_name", Company.company_name,
#                         "company_location", Company.company_location,
#                         "start_date", WorkExperience.start_date,
#                         "end_date", WorkExperience.end_date,
#                         "is_present", WorkExperience.is_active
#                     )
#                 ).label("work_experience")
#             )
#             .select_from(WorkExperience)
#             .join(Role, WorkExperience.role_id == Role.role_id)
#             .join(Company, WorkExperience.company_id == Company.company_id)
#             .group_by(WorkExperience.candidate_id)
#             .subquery()
#         )

#         conditions = [Candidate.is_active == True]

#         name_list = filters.get("name")
#         if name_list:
#             name_conditions = []

#             for name in name_list:
#                 name = str(name).strip()
#                 if name:
#                     name_conditions.append(Candidate.name.ilike(f"%{name}%"))

#             if name_conditions:
#                 conditions.append(or_(*name_conditions))

#         exp_min = filters.get("min_experience")
#         if exp_min is not None and exp_min != "":
#             try:
#                 conditions.append(Candidate.total_experience >= float(exp_min))
#             except (ValueError, TypeError):
#                 pass

#         exp_max = filters.get("max_experience")
#         if exp_max is not None and exp_max != "":
#             try:
#                 conditions.append(Candidate.total_experience <= float(exp_max))
#             except (ValueError, TypeError):
#                 pass

#         skills_filter = filters.get("skills")
#         if skills_filter:
#             if not isinstance(skills_filter, list):
#                 logger.warning("[search_resumes] skills must be a list, got %s", type(skills_filter).__name__)
#             else:
#                 valid_skills = [s for s in skills_filter if s and isinstance(s, str)]
#                 if valid_skills:
#                     logger.debug("[search_resumes] Applying skills filter with %d UUIDs", len(valid_skills))
#                     conditions.append(
#                         Candidate.candidate_id.in_(
#                             db.query(CandidateSkills.candidate_id).filter(
#                                 CandidateSkills.skill_id.in_(valid_skills)
#                             )
#                         )
#                     )

#         companies = filters.get("companies")
#         if companies:
#             if not isinstance(companies, list):
#                 logger.warning("[search_resumes] companies must be a list, got %s", type(companies).__name__)
#             else:
#                 company_ids = []
#                 for comp in companies:
#                     comp = str(comp).strip()
#                     if not comp:
#                         continue
#                     matched = db.query(Company).filter(
#                         Company.company_name.ilike(f"%{comp}%")
#                     ).all()
#                     if matched:
#                         company_ids.extend([c.company_id for c in matched])
#                         logger.debug("[search_resumes] Company '%s' matched %d records", comp, len(matched))
#                     else:
#                         logger.debug("[search_resumes] No companies matched name: '%s'", comp)
#                 conditions.append(
#                     Candidate.candidate_id.in_(
#                         db.query(WorkExperience.candidate_id).filter(
#                             WorkExperience.company_id.in_(company_ids)
#                         )
#                     )
#                 )

#         education_vals = filters.get("education")
#         if education_vals:
#             if not isinstance(education_vals, list):
#                 logger.warning("[search_resumes] education must be a list, got %s", type(education_vals).__name__)
#             else:
#                 valid_edu = [e for e in education_vals if e and isinstance(e, str)]
#                 if valid_edu:
#                     logger.debug("[search_resumes] Applying education filter with %d UUIDs", len(valid_edu))
#                     conditions.append(
#                         Candidate.candidate_id.in_(
#                             db.query(CandidateEducation.candidate_id).filter(
#                                 CandidateEducation.education_id.in_(valid_edu)
#                             )
#                         )
#                     )

#         roles = filters.get("roles")
#         if roles:
#             if not isinstance(roles, list):
#                 logger.warning("[search_resumes] roles must be a list, got %s", type(roles).__name__)
#             else:
#                 valid_roles = [r for r in roles if r and isinstance(r, str)]
#                 if valid_roles:
#                     logger.debug("[search_resumes] Applying roles filter with %d UUIDs", len(valid_roles))
#                     conditions.append(
#                         Candidate.candidate_id.in_(
#                             db.query(WorkExperience.candidate_id).filter(
#                                 WorkExperience.role_id.in_(valid_roles)
#                             )
#                         )
#                     )

#         passout_start = filters.get("passout_start_year")
#         passout_end = filters.get("passout_end_year")
#         if passout_start is not None or passout_end is not None:
#             year_conditions = []
#             if passout_start is not None and passout_start != "":
#                 try:
#                     ps_val = int(passout_start)
#                     year_conditions.append(CandidateEducation.year_of_passed >= ps_val)
#                     logger.debug("[search_resumes] Applying passout_start_year: %d", ps_val)
#                 except (ValueError, TypeError):
#                     logger.warning(
#                         "[search_resumes] Invalid passout_start_year: '%s', skipping", passout_start
#                     )
#             if passout_end is not None and passout_end != "":
#                 try:
#                     pe_val = int(passout_end)
#                     year_conditions.append(CandidateEducation.year_of_passed <= pe_val)
#                     logger.debug("[search_resumes] Applying passout_end_year: %d", pe_val)
#                 except (ValueError, TypeError):
#                     logger.warning(
#                         "[search_resumes] Invalid passout_end_year: '%s', skipping", passout_end
#                     )
#             if year_conditions:
#                 conditions.append(
#                     Candidate.candidate_id.in_(
#                         db.query(CandidateEducation.candidate_id).filter(and_(*year_conditions))
#                     )
#                 )

#         percentage = filters.get("percentage")
#         if percentage is not None and percentage != "":
#             try:
#                 pct_val = float(percentage)
#                 logger.debug("[search_resumes] Applying percentage filter: >= %s", pct_val)
#                 conditions.append(
#                     Candidate.candidate_id.in_(
#                         db.query(CandidateEducation.candidate_id).filter(
#                             CandidateEducation.percentage >= pct_val
#                         )
#                     )
#                 )
#             except (ValueError, TypeError):
#                 logger.warning("[search_resumes] Invalid percentage value: '%s', skipping", percentage)

#         logger.info("[search_resumes] Total filter conditions built: %d", len(conditions))

#         total_count = (
#             db.query(func.count(Candidate.candidate_id))
#             .filter(and_(*conditions))
#             .scalar()
#         ) or 0
#         logger.info("[search_resumes] Total matching records: %d", total_count)

#         query = (
#             db.query(
#                 func.json_build_object(
#                     "candidate_id", Candidate.candidate_id,
#                     "name", Candidate.name,
#                     "email", Candidate.email_address,
#                     "phone_number", Candidate.phone_number,
#                     "location", Candidate.location,
#                     "total_experience", Candidate.total_experience,
#                     "education", func.coalesce(candidate_education.c.education, cast('[]', JSON)),
#                     "skills", func.coalesce(candidate_skills.c.skills, cast('[]', JSON)),
#                     "work_experience", func.coalesce(candidate_work_exp.c.work_experience, cast('[]', JSON))
#                 ).label("candidate_info")
#             )
#             .select_from(Candidate)
#             .outerjoin(candidate_education, Candidate.candidate_id == candidate_education.c.candidate_id)
#             .outerjoin(candidate_skills, Candidate.candidate_id == candidate_skills.c.candidate_id)
#             .outerjoin(candidate_work_exp, Candidate.candidate_id == candidate_work_exp.c.candidate_id)
#             .filter(and_(*conditions))
#         )

#         sort_by = filters.get("sort_by")
#         sort_order = (filters.get("sort_order") or "asc").lower()
#         sort_map = {
#             "name": Candidate.name,
#             "total_experience": Candidate.total_experience,
#             "created_at": Candidate.created_at,
#             "location" : Candidate.location,
#             "email_address" : Candidate.email_address,
#             "year_of_passed": candidate_education.max_year_of_passed,
#             "percentage": candidate_education.max_percentage,
#         }

#         if sort_by and sort_by in sort_map:
#             sort_col = sort_map[sort_by]
#             query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
#             logger.debug("[search_resumes] Sorting by %s %s", sort_by, sort_order)
#         elif sort_by:
#             logger.warning("[search_resumes] Unknown sort_by field: '%s', ignoring", sort_by)

#         page = max(1, int(filters.get("page", 1) or 1))
#         page_size = max(1, min(100, int(filters.get("page_size", 20) or 20)))
#         offset = (page - 1) * page_size
#         query = query.limit(page_size).offset(offset)
#         logger.info("[search_resumes] Pagination: page=%d, page_size=%d, offset=%d", page, page_size, offset)

#         data = query.all()
#         logger.info("[search_resumes] Query returned %d candidate records", len(data))

#         results = [row.candidate_info for row in data]
#         results.append({"total_record": total_count})

#         elapsed = round(_time.time() - start_time, 3)
#         logger.info(
#             "[search_resumes] Completed in %ss | returned %d candidates, total_record=%d",
#             elapsed, len(results) - 1, total_count
#         )
#         return results

#     except Exception as e:
#         logger.error("[search_resumes] Unexpected error: %s", str(e), exc_info=True)
#         raise
#     finally:
#         db.close()
#         logger.debug("[search_resumes] Database session closed")

def extract_filters_from_query(query: str) -> dict:
    """Use LLM to convert a natural-language hiring query into a structured filter payload."""

    prompt = """
        You are a hiring-query parser.

        Extract filters from:
        - short queries
        - skills lists
        - role searches
        - full job descriptions

        Return ONLY valid JSON.

        Schema:
        {
        "skills": [],
        "education": [],
        "roles": [],
        "companies": [],
        "min_experience": null,
        "max_experience": null,
        "name": null,
        "passout_start_year": null,
        "passout_end_year": null,
        "percentage": null
        }

        Rules:

        1. Technologies, programming languages, frameworks, libraries, databases, cloud platforms, tools, ETL tools, DevOps tools, AI/ML concepts, and software technologies -> skills.

        Examples:
        Python, SQL, React, FastAPI, AWS, Docker, Snowflake, Databricks, Airflow, Pinecone, FAISS, Chroma, Qdrant, LangGraph, CrewAI.

        2. Extract technologies mentioned after:
        - e.g.
        - like
        - such as
        - including
        and inside brackets ().

        3. Job titles/designations -> roles.

        Examples:
        Python Developer
        Backend Engineer
        Data Engineer
        Software Developer
        DevOps Engineer

        4. If a phrase contains:
        developer, engineer, architect, manager, lead, analyst, consultant, administrator, specialist, tester, designer

        then treat the FULL phrase as ONE role.

        Examples:
        "Python Developer"
        "Java Engineer"
        "Data Engineer"

        Do NOT split:
        "Python Developer"
        into:
        skills=["Python"]
        roles=["Developer"]

        5. Single technologies without designation -> skills.

        Examples:
        Python, React, AWS.

        6. Extract multiple skills separately.

        Example:
        "Python, Java, SQL"
        -> ["Python", "Java", "SQL"]

        7. Experience:
        - "5+ years" -> min_experience=5
        - "3-5 years" -> min_experience=3, max_experience=5
        - "10 years" -> min_experience=10, max_experience=10

        8. Extract only explicitly mentioned education.

        9. CGPA to percentage:
        8.5 CGPA -> 85

        10. Remove duplicates and normalize values.

        11. Extract only explicitly mentioned values.

        12. Omit null or empty fields.

        13. Return ONLY valid JSON.
        No markdown.
        No explanation.
        No extra text.
        """
    try:
        db = SessionLocal()
        admin = db.query(Admin).filter(Admin.is_active == True).first()

        if not admin:
            logger.warning("[extract_filters_from_query] No admin found, defaulting to ollama with latest model")
            raise Exception("No admin found")

        model_info = (db.query(
            func.json_build_object(
                'model_name', AiModel.model_name,
                'model_version_name', AiModelversion.version_name,
                'apikey', AiModelConfig.apikey,
                'max_tokens', AiModelConfig.max_tokens,
                'temperature', AiModelConfig.temparature,
                'is_active', AiModelConfig.is_active
            )
        )
        .select_from(AiModelConfig)
        .join(AiModel, AiModel.ai_model_id == AiModelConfig.ai_model_id)
        .join(AiModelversion, AiModelversion.ai_model_version_id == AiModelConfig.ai_model_version_id)
        .filter(AiModelConfig.is_active == True)
        .first()
        )

        if not model_info:
            model_info = {}
        else:
            model_info = model_info[0]
        
        model = model_info.get("model_name", "ollama").lower()
        version = model_info.get("model_version_name", "llama3").lower()
        api_key = model_info.get("apikey") or None
        
        logger.info("[extract_filters_from_query] Using model: %s, version: %s", model, version)

        message = [
            {"role": "system", "content": "You output only JSON."},
            {"role": "user", "content": prompt + "\n\nQuery:\n" + query[:1000]},
        ]

        if model == "openai":
            if not api_key or api_key == None:
                raise Exception("OpenAI API key not found")

            client = OpenAI(api_key=api_key)

            response = client.chat.completions.create(
                model=version,
                messages=message
            )
            content = response.choices[0].message.content.strip()
        elif model == "claude":
            if not api_key or api_key == None:
                raise Exception("Claude API key not found")

            client = Anthropic(api_key=api_key)

            response = client.messages.create(
                model=version,
                max_tokens=1000,
                system="You output only JSON.",
                messages=[
                    {"role": "user", "content": prompt + "\n\nQuery:\n" + query[:1000]}
                ]
            )
            content = response.content[0].text.strip()
        else:
            response = ollama.chat(
                model=version,
                messages=message
            )
            content = response["message"]["content"].strip()

        logger.info("[extract_filters_from_query] Raw LLM response: %s", content[:500])

        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("[extract_filters_from_query] No JSON object found in LLM output")
            return {}

        parsed = json.loads(content[start:end])
        if not isinstance(parsed, dict):
            return {}

        allowed_keys = {
            "skills", "education", "roles", "companies",
            "min_experience", "max_experience", "name",
            "passout_start_year", "passout_end_year", "percentage",
        }
        return {k: v for k, v in parsed.items() if k in allowed_keys and v is not None}

    except Exception as e:
        logger.error("[extract_filters_from_query] LLM extraction failed: %s", str(e), exc_info=True)
        return {}
    finally:
        db.close()


def resolve_dynamic_filters(dynamic_filters: dict) -> dict:
    """Convert human-readable names in dynamic filters to UUID-based values
    compatible with ``ResumeFilterRequest`` / ``search_resumes``.
    """

    if not dynamic_filters or not isinstance(dynamic_filters, dict):
        return {}

    db = SessionLocal()
    resolved: dict = {}
    try:
        def _match_ids(model, id_attr, name_attr, values: list) -> list[str]:
            ids = []
            for value in values:
                if not value or not isinstance(value, str):
                    continue
                clean_value = value.strip()
                if not clean_value:
                    continue

                matches = db.query(model).filter(name_attr.ilike(clean_value)).all()
                if not matches:
                    matches = db.query(model).filter(name_attr.ilike(f"%{clean_value}%")).all()

                if matches:
                    ids.extend(str(getattr(match, id_attr)) for match in matches)
                else:
                    logger.debug("[resolve_dynamic_filters] No match for '%s'", clean_value)
            return list(dict.fromkeys(ids))

        skill_names = dynamic_filters.get("skills")
        if skill_names and isinstance(skill_names, list):
            skill_ids = _match_ids(Skill, "skill_id", Skill.skill, skill_names)
            if skill_ids:
                resolved["skills"] = skill_ids

        edu_names = dynamic_filters.get("education")
        if edu_names and isinstance(edu_names, list):
            edu_ids = _match_ids(Education, "education_id", Education.education, edu_names)
            if edu_ids:
                resolved["education"] = edu_ids

        role_names = dynamic_filters.get("roles")
        if role_names and isinstance(role_names, list):
            role_ids = _match_ids(Role, "role_id", Role.role, role_names)
            if role_ids:
                resolved["roles"] = list(dict.fromkeys(role_ids))
            

        companies = dynamic_filters.get("companies")
        if companies and isinstance(companies, list):
            resolved["companies"] = [c.strip() for c in companies if isinstance(c, str) and c.strip()]

        for field in ("min_experience", "max_experience"):
            val = dynamic_filters.get(field)
            if val is not None:
                if isinstance(val, str):
                    import re as _re
                    m = _re.search(r"(\d+(?:\.\d+)?)", val)
                    if m:
                        resolved[field] = float(m.group(1))
                else:
                    try:
                        resolved[field] = float(val)
                    except (ValueError, TypeError):
                        pass

        name_val = dynamic_filters.get("name")
        if name_val and isinstance(name_val, str) and name_val.strip():
            resolved["name"] = [name_val.strip()]

        for field in ("passout_start_year", "passout_end_year"):
            val = dynamic_filters.get(field)
            if val is not None:
                if isinstance(val, str):
                    import re as _re2
                    m = _re2.search(r"(\d{4})", val)
                    if m:
                        resolved[field] = int(m.group(1))
                else:
                    try:
                        resolved[field] = int(val)
                    except (ValueError, TypeError):
                        pass

        pct_val = dynamic_filters.get("percentage")
        if pct_val is not None:
            if isinstance(pct_val, str):
                import re as _re3
                m = _re3.search(r"(\d+(?:\.\d+)?)", pct_val)
                if m:
                    resolved["percentage"] = float(m.group(1))
            else:
                try:
                    resolved["percentage"] = float(pct_val)
                except (ValueError, TypeError):
                    pass

        logger.info("[resolve_dynamic_filters] Resolved: %s", resolved)
        return resolved

    except Exception as e:
        logger.error("[resolve_dynamic_filters] Error: %s", str(e), exc_info=True)
        return {}
    finally:
        db.close()


def merge_filters(standard: dict, dynamic: dict) -> dict:
    """Merge standard (UI-driven) filters with resolved dynamic (LLM-driven) filters.

    Merging strategy:
    - List fields (skills, education, roles, companies): union with deduplication.
    - Scalar/range fields: standard wins when present; otherwise use dynamic.
    - Pagination and sorting fields always come from standard only.
    """

    if not dynamic:
        return dict(standard) if standard else {}
    if not standard:
        return dict(dynamic)

    merged = dict(standard)
    list_fields = ("skills", "education", "roles", "companies")
    pagination_fields = {"page", "page_size", "sort_by", "sort_order", "action_type"}

    for key in list_fields:
        std_vals = standard.get(key) or []
        dyn_vals = dynamic.get(key) or []
        if not isinstance(std_vals, list):
            std_vals = []
        if not isinstance(dyn_vals, list):
            dyn_vals = []
        combined = list(dict.fromkeys(std_vals + dyn_vals))
        if combined:
            merged[key] = combined

    scalar_fields = ("min_experience", "max_experience", "name", "percentage",
                     "passout_start_year", "passout_end_year", "file_name")
    for key in scalar_fields:
        if merged.get(key) is None and dynamic.get(key) is not None:
            merged[key] = dynamic[key]

    for key in pagination_fields:
        if key in dynamic and key not in merged:
            pass

    for key in list_fields:
        if key in merged and not merged[key]:
            del merged[key]

    return merged


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


def apply_filters(candidates: list, filters: dict) -> list:
    """
    Apply filters on candidate records returned from DB.
    """
    
    filtered_candidates = []
    filters = filters.get("filters", {})

    for candidate in candidates:
        matched = True

        if filters.get("name"):
            search_names = [
                str(n).lower()
                for n in filters["name"]
            ]

            candidate_name = (
                candidate.get("name") or ""
            ).lower()

            if not any(
                name in candidate_name
                for name in search_names
            ):
                matched = False

        if matched and filters.get("location"):
            location_filter = (
                filters["location"]
            ).lower()

            candidate_location = (
                candidate.get("location") or ""
            ).lower()

            if location_filter not in candidate_location:
                matched = False

        if matched and filters.get("skills"):
            candidate_skill_ids = set()
            for skill in candidate.get("skills", []):
                if not isinstance(skill, dict):
                    continue

                skill_id = skill.get("skill_id")

                if skill_id is not None:
                    candidate_skill_ids.add(skill_id)

            filter_skill_ids = set(filters["skills"])
            if not filter_skill_ids.issubset(
                candidate_skill_ids
            ):
                matched = False

        if matched and filters.get("companies"):
            candidate_companies = set()
            for exp in candidate.get(
                "work_experience", []
            ):
                if isinstance(exp, dict):
                    company_name = exp.get(
                        "company_name", ""
                    )
                elif isinstance(exp, str):
                    company_name = exp
                else:
                    continue

                if company_name:
                    candidate_companies.add(
                        company_name.lower()
                    )

            filter_companies = {
                str(company).lower()
                for company in filters["companies"]
            }
            if not any(
                company in candidate_companies
                for company in filter_companies
            ):
                matched = False

        if matched and filters.get("passout_start_year"):
            start_year = int(
                filters["passout_start_year"]
            )

            education_years = []
            for edu in candidate.get("education", []):
                if not isinstance(edu, dict):
                    continue

                year = edu.get("year_of_passed")
                if year is not None:
                    try:
                        education_years.append(
                            int(year)
                        )
                    except (
                        ValueError,
                        TypeError,
                    ):
                        pass

            if not any(
                year >= start_year
                for year in education_years
            ):
                matched = False

        if matched and filters.get("passout_end_year"):
            end_year = int(
                filters["passout_end_year"]
            )

            education_years = []
            for edu in candidate.get("education", []):
                if not isinstance(edu, dict):
                    continue

                year = edu.get("year_of_passed")
                if year is not None:
                    try:
                        education_years.append(
                            int(year)
                        )
                    except (
                        ValueError,
                        TypeError,
                    ):
                        pass

            if not any(
                year <= end_year
                for year in education_years
            ):
                matched = False

        if matched and filters.get("percentage"):
            required_percentage = float(
                filters["percentage"]
            )

            percentages = []
            for edu in candidate.get("education", []):
                if not isinstance(edu, dict):
                    continue

                percentage = edu.get("percentage")
                if percentage is not None:
                    try:
                        percentages.append(
                            float(percentage)
                        )
                    except (
                        ValueError,
                        TypeError,
                    ):
                        pass

            if not any(
                p >= required_percentage
                for p in percentages
            ):
                matched = False

        if matched and filters.get("experience"):

            filter_experience = {
                int(exp)
                for exp in filters["experience"]
            }
            candidate_experience = candidate.get(
                "total_experience"
            )

            try:
                candidate_experience = int(
                    candidate_experience
                )
            except (ValueError, TypeError):
                matched = False

            if (
                matched
                and candidate_experience
                not in filter_experience
            ):
                matched = False
        if matched:
            filtered_candidates.append(candidate)

    return filtered_candidates
