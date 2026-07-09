import logging
import datetime
import base64
from datetime import timezone
from zoneinfo import ZoneInfo
import re
from tomlkit import value
import ollama
import json

from src.services.admin.service import active_model
from src.email_reader.models import Attachment
from src.resume_filter.models import Resume
from src.services.resume_filter.service import extract_docx_text, extract_text_from_pdf
from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import UUID, String, func, cast, inspect
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.admin.models import Admin, AiModel, AiModelConfig, AiModelversion, Users, ExtractionConfig, ist_now
from fastapi import status
from openai import OpenAI
from anthropic import Anthropic
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from src.utils.helper import decrypt_data, record_model_usage, select_available_model

load_dotenv()
logger = logging.getLogger(__name__)

db = SessionLocal()

def encode_file_to_base64(file_path):
    with open(file_path, "rb") as file_obj:
        return base64.b64encode(file_obj.read()).decode("utf-8")

def alter_resume(payload, resume_id):
    try:
        if not payload or not resume_id:
            raise ValueError("Payload and resume_id are required.")

        job_description = (
            payload.get("job_description")
            or payload.get("jobDescription")
            or payload.get("jd")
            or []
        )

        resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
        if resume is None:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Resume not found."}
        attachment_id = resume.attachment_id

        att = db.query(Attachment).filter(Attachment.attachment_id == attachment_id).first()

        file_path = f"attachments/{att.file_name}"

        if file_path.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        elif file_path.endswith(".docx"):
            text = extract_docx_text(file_path)

        clean_jd = ", ".join(job_description) if isinstance(job_description, list) else clean_text(job_description)
        if not clean_jd:
            raise ValueError("job_description or jobDescription is required.")
        
        combined_text = clean_jd.strip()
        data = tailor_resume(text, combined_text)

        output_ext = ".pdf" if file_path.lower().endswith(".pdf") else ".docx"
        output_path = f"attachments/tailored_{att.file_name.rsplit('.', 1)[0]}{output_ext}"
        if output_ext == ".pdf":
            make_resume = generate_resume_pdf(data, output_path)
        else:
            make_resume = generate_resume_docx(data, output_path)
        if not isinstance(make_resume, str):
            return make_resume

        return {
            "message": "resume tailored successfully",
            "file_name": att.file_name.rsplit(".", 1)[0] + output_ext,
            "file_type": "pdf" if output_ext == ".pdf" else "docx",
            "mime_type": (
                "application/pdf"
                if output_ext == ".pdf"
                else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            "content": encode_file_to_base64(make_resume),
            # "tailored_resume": data.get("tailored_resume", data),
        }
    
    except Exception as e:
        logger.error(f"Error in alter_resume: {str(e)}")
        return {"status" : status.HTTP_500_INTERNAL_SERVER_ERROR, "message": str(e)}
    finally:
        db.close()


def parse_llm_json(content):
    cleaned = (
        content.strip()
        .replace("```json", "")
        .replace("```", "")
        .replace("\ufeff", "")
        .replace("fastapi_api |", "")
        .replace("postgres_db |", "")
    )

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No valid JSON object found")

    json_str = cleaned[start:end + 1]

    try:
        return json.loads(json_str)

    except json.JSONDecodeError as e:

        repaired = re.sub(
            r",(\s*[}\]])",
            r"\1",
            json_str
        )

        try:
            return json.loads(repaired)

        except json.JSONDecodeError as e2:
            raise ValueError(
                f"Invalid JSON. "
                f"Line={e2.lineno}, "
                f"Column={e2.colno}, "
                f"Error={e2.msg}"
            )

def create_json_completion(client, model, messages):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_object"
            }
        )
    except Exception as e:
        error_text = str(e)

        if (
            "json_validate_failed" in error_text
            or "Failed to validate JSON" in error_text
        ):
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
        else:
            raise

    return response

def tailor_resume(resume_text, jd_info):

    
    # prompt = """
    #     You are an Expert Resume Tailoring Engine.
    #     Return exactly one valid JSON object only.

    #     Use RESUME_TEXT and JD_INFO to create a tailored resume.

    #     Rules:
    #     1. Use RESUME_TEXT as the source for candidate basics: name, email, phone, location, total experience, company names, durations, education, certifications, links, existing work history, and project details.
    #     2. Use JD_INFO as the source for target role title, JD skills, and JD responsibility themes.
    #     3. Do not create fake companies, fake dates, fake education, fake certifications, or fake employment history.
    #     4. Keep company names and durations exactly from RESUME_TEXT. Never change them.
    #     5. Set tailored_resume.role from the role/title in JD_INFO.
    #     6. Set each work_experience.role from the JD role/title so the experience matches the target role, but keep the same company, duration, and project/work history from RESUME_TEXT.
    #     7. Keep existing resume skills only when they are relevant or related to the JD. Remove unrelated skills.
    #     8. Extract JD skills strictly from JD_INFO. Add only skills, technologies, tools, platforms, programming languages, frameworks, libraries, databases, cloud services, methodologies, certifications, and domain concepts that are explicitly mentioned in JD_INFO. Do not infer, assume, generalize, expand abbreviations into new skills, or create related skills that are not stated in JD_INFO. Do not generate generic soft skills, responsibilities, job duties, or implied competencies unless they are explicitly listed as skills or qualifications in JD_INFO. Categorize extracted skills appropriately into: languages, frameworks, libraries, databases, cloud, devops, tools, ai_ml, concepts, and others.
    #     8A. Skill Extraction Accuracy Rule: Skills must be extracted verbatim or as direct normalized forms of terms explicitly present in JD_INFO. Do not convert responsibilities into new skills. For example, "create dashboards" does not automatically become "Dashboard Development", "collaborate with stakeholders" does not become "Stakeholder Management", and "identify trends" does not become "Trend Analysis" unless those exact skills are explicitly mentioned in JD_INFO.
    #     9. Avoid duplicate skills.
    #     10. Rewrite work experience responsibilities based on RESUME_TEXT and JD_INFO together.
    #     11. Use every existing work_experience/project block from RESUME_TEXT as the base. Do not ignore any block.
    #     12. Preserve the original project/work meaning, company, duration, domain context, and core functionality, then enhance the responsibilities with JD-related work.
    #     13. Modify existing responsibilities so they naturally reflect the JD responsibilities, technologies, tools, and outcomes. Do not replace the project with an unrelated domain.
    #     14. Add JD-related skills inside responsibility sentences as realistic work, not keyword stuffing.
    #     15. Keep each enhanced responsibility believable for the original resume project/work history.
    #     16. If a responsibility is not strongly related to the JD, keep it and lightly improve the wording.
    #     17. Analyze headings such as Work Experience, Experience Details, Professional Experience, Employment History, Projects, Project Details, Client Projects, or Key Projects.
    #     18. Do not keep work experience and projects as separate sections in the output.
    #     19. If RESUME_TEXT is project-based, treat each separate project/client/product block as one work_experience entry.
    #     20. Do not combine multiple project blocks into one work_experience entry.
    #     21. For headings like Project Details, Client Projects, or Key Projects, every project title under that heading must become its own work_experience item.
    #     22. The number of work_experience entries must match the number of distinct work/project blocks found in RESUME_TEXT.
    #     23. If no company is explicitly available for a block, keep company as "" and use project_name to identify the entry.
    #     24. Return tailored_resume.projects as an empty array.
    #     25. Generate a completely new professional summary based primarily on the target role defined in JD_INFO. The summary must contain at least 3 complete sentences (preferably 4–6 lines) and should position the candidate as a strong fit for the target role, not necessarily the role stated in the original summary. Analyze the target role, required skills, preferred skills, technologies, responsibilities, and domain from JD_INFO, then identify the candidate's most relevant experience, projects, skills, achievements, and transferable strengths from RESUME_TEXT. If the existing summary focuses on a different profession, career objective, or role than JD_INFO, discard it entirely and generate a new summary from scratch. Use RESUME_TEXT only as evidence of the candidate's background and experience, not as the source of summary wording or role positioning. Highlight transferable skills, relevant technologies, business impact, problem-solving abilities, domain knowledge, and accomplishments that support the target role. The summary must be ATS-friendly, natural, recruiter-focused, and aligned with the JD. Do not copy or lightly modify the original summary. Reflect the candidate's actual seniority and experience level, avoid keyword stuffing, and never invent experience, achievements, certifications, or skills that are not supported by RESUME_TEXT.
    #     26. Preserve every useful resume section from RESUME_TEXT. If content does not fit summary, skills, work_experience, education, or certifications, add it to achievements, languages, interests, or additional_sections.
    #     27. Return valid JSON only. No markdown, no explanation, no null values.
    #     28. Do not include comments, labels, prefixes, code fences, or trailing commas.
    #     29. The top-level object must contain exactly: jd_analysis, skill_gap_analysis, tailored_resume.
    #     30. If a value is unknown, use "" for strings, 0 for total_experience, and [] for arrays.
    #     31. JD_INFO below is the source of truth for the job description. Do not ignore it.
    #     32. Summary Reconstruction Rule:
    #         The profile summary must NOT be copied blindly from RESUME_TEXT. Evaluate whether the existing summary aligns with the target role, required skills, responsibilities, seniority level, and domain in JD_INFO.

    #         - If the existing summary is relevant, enhance and optimize it for the target role.
    #         - If the existing summary is partially relevant, rewrite it substantially.
    #         - If the existing summary is unrelated to the target role, completely replace it.

    #         The final summary must:
    #         - Be generated specifically for the role in JD_INFO.
    #         - Be ATS-friendly and professionally written.
    #         - Use only factual information available in RESUME_TEXT.
    #         - Highlight the candidate's most relevant experience, skills, technologies, projects, domains, and achievements for the target role.
    #         - Prioritize JD-required and preferred skills when they can be reasonably supported by the candidate's background.
    #         - Reflect the candidate's actual seniority and total experience.
    #         - Sound natural and credible, not keyword-stuffed.
    #         - Never mention skills, achievements, certifications, domains, responsibilities, or experience that are not supported by RESUME_TEXT.
    #         - Never reuse an unrelated objective, career goal, or summary from RESUME_TEXT.
    #         - The summary should make the candidate appear as a strong and realistic fit for the target role while remaining fully truthful to the source resume.

    #     Return this JSON structure:
    #     {
    #     "jd_analysis": {
    #     "target_role": "",
    #     "overall_experience_required": "",
    #     "technical_skills": {
    #         "languages": [],
    #         "frameworks": [],
    #         "libraries": [],
    #         "databases": [],
    #         "cloud": [],
    #         "devops": [],
    #         "tools": [],
    #         "ai_ml": [],
    #         "concepts": [],
    #         "others": []
    #         },
    #     "responsibilities": [],
    #     "domain_knowledge": [],
    #     "certifications": []
    #     },

    #     "skill_gap_analysis": {
    #     "existing_skills": [],
    #     "missing_skills": []
    #     },

    #     "tailored_resume": {
    #         "name": "",
    #         "total_experience": 0,
    #         "email": "",
    #         "phone_number": "",
    #         "location": "",
    #         "role": "",
    #         "summary": "",

    #         "technical_skills": {
    #             "languages": [],
    #             "frameworks": [],
    #             "libraries": [],
    #             "databases": [],
    #             "cloud": [],
    #             "devops": [],
    #             "tools": [],
    #             "ai_ml": [],
    #             "concepts": [],
    #             "others": []
    #         },

    #         "education": [
    #             {
    #             "degree": "",
    #             "field": "",
    #             "institution": "",
    #             "cgpa": "",
    #             "duration": ""
    #             }
    #         ],

    #         "work_experience": [
    #             {
    #             "role": "",
    #             "company": "",
    #             "project_name": "",
    #             "location": "",
    #             "duration": "",
    #             "responsibilities": []
    #             }
    #         ],

    #         "projects": [],

    #         "certifications": [
    #             {
    #             "name": "",
    #             "organization": "",
    #             "year": "",
    #             "details": ""
    #             }
    #         ],

    #         "achievements": [],

    #         "languages": [],

    #         "interests": [],

            

    #         "links": {
    #             "linkedin": "",
    #             "github": "",
    #             "portfolio": ""
    #         }
    #     }
    #     }

    #     """


# before final 

#     prompt = """
# You are a Resume Tailoring Engine. Return one valid JSON object. No markdown.

# GOAL: Transform the resume to match JD_INFO. NOT a copy task.
# FAIL if output keeps original summary, original job titles, or original responsibility wording.

# INPUTS:
# - RESUME_TEXT → identity, companies, dates, project/company names only
# - JD_INFO → target role, skills, responsibility themes (NOT candidate experience years)

# ====================================================================
# 1. PRESERVE EXACTLY
# ====================================================================
# name, email, phone_number, location, education, certifications, links, achievements, languages, interests
# Per kept work entry: company, duration, project_name, location — exact from RESUME_TEXT

# ====================================================================
# 2. MUST GENERATE NEW (never reuse original text)
# ====================================================================
# | Field              | Rule |
# |--------------------|------|
# | summary            | Write 100% NEW from JD — ignore original summary completely |
# | work_experience.role | NEW JD-domain titles — never original titles |
# | responsibilities   | Write 100% NEW from JD themes — never copy original bullets |
# | technical_skills   | JD skills first; add resume skills only if JD-relevant |

# ====================================================================
# 3. SUMMARY (always new, JD-driven)
# ====================================================================
# - Do NOT read, copy, or paraphrase the original Professional Summary from RESUME_TEXT. Write 100% NEW summary — never copy original Professional Summary
# - Write 3–5 fresh sentences for the JD target role
# - Sentence 1: JD role + total_experience (calculated from resume dates, section 4)
# - Include JD skills and JD responsibility themes
# - If career pivot (QA→Data Analyst etc.): zero mention of old profession
# - Use RESUME_TEXT only for years of experience and general domain facts — not for summary wording

# ====================================================================
# 4. EXPERIENCE, TRIM & ROLES
# ====================================================================
# total_experience:
# - Calculate from RESUME_TEXT date ranges (kept entries) — NEVER from JD "1-3 years required"
# - jd_analysis.overall_experience_required = JD text for analysis only

# Trim (only if candidate years >> JD max):
# - Remove OLDEST entries first; always keep most recent
# - Recalculate total_experience from kept dates

# work_experience order: MOST RECENT FIRST (index 0 = latest job)
# Role titles (NEW — never from RESUME_TEXT):
# - Index 0 (latest): JD role + seniority (Senior if 5+ years)
# - Middle: mid-level (e.g. "Data Analyst")
# - Oldest kept: junior (e.g. "Junior Data Analyst")

# FINAL: tailored_resume.role = work_experience[0].role (exact copy)

# ====================================================================
# 5. RESPONSIBILITIES (new, JD-driven)
# ====================================================================
# For EVERY work_experience entry generate 4–5 NEW bullets.

# Rules:
# - Source = JD_INFO responsibility themes + JD skills — NOT original resume bullets
# - Do NOT copy or paraphrase original responsibility text from RESUME_TEXT
# - Do NOT copy JD_INFO sentences verbatim
# - Anchor each bullet to the entry's company/project_name from RESUME_TEXT for context
# - Match seniority of that entry's role title
# - Each bullet: exactly 10–15 words (count before output; reject if under 10 or over 15)
# - Format: [Verb] + [JD-aligned task] + [JD skill/tool] + [company/project context]
# - Spread different JD themes across bullets — no repetition

# Word count examples:
#   OK (12w): "Built Tableau dashboards for Accenture banking clients tracking loan approval metrics weekly."
#   OK (14w): "Extracted and cleaned PostgreSQL datasets using SQL to support automated reporting for insurance claim analysis."
#   BAD (8w):  "Analyzed datasets and created dashboards for stakeholders."  ← too short
#   BAD (20w): "Analyzed large complex datasets using SQL and Tableau to identify trends patterns and anomalies for business teams."  ← too long

# Career pivot: write bullets as JD-role work at that company — no old-role terms (no Selenium/testing for Data Analyst JD).

# ====================================================================
# 6. SKILLS
# ====================================================================
# 1. Add every skill explicitly in JD_INFO
# 2. Add resume skills ONLY if JD-relevant
# 3. Remove all old-profession skills (Selenium, Cypress etc. unless JD is QA)
# 4. Categorize: languages, frameworks, libraries, databases, cloud, devops, tools, ai_ml, concepts, others

# ====================================================================
# 7. STRUCTURE & OUTPUT
# ====================================================================
# - All work/project blocks from RESUME_TEXT unless trimmed (section 4)
# - projects = []
# - Valid JSON; keys: jd_analysis, skill_gap_analysis, tailored_resume

# {
#   "jd_analysis": {
#     "target_role": "",
#     "overall_experience_required": "",
#     "technical_skills": {"languages":[],"frameworks":[],"libraries":[],"databases":[],"cloud":[],"devops":[],"tools":[],"ai_ml":[],"concepts":[],"others":[]},
#     "responsibilities": [],
#     "domain_knowledge": [],
#     "certifications": []
#   },
#   "skill_gap_analysis": {"existing_skills":[],"missing_skills":[]},
#   "tailored_resume": {
#     "name":"","total_experience":0,"email":"","phone_number":"","location":"","role":"","summary":"",
#     "technical_skills":{"languages":[],"frameworks":[],"libraries":[],"databases":[],"cloud":[],"devops":[],"tools":[],"ai_ml":[],"concepts":[],"others":[]},
#     "education":[{"degree":"","field":"","institution":"","cgpa":"","duration":""}],
#     "work_experience":[{"role":"","company":"","project_name":"","location":"","duration":"","responsibilities":[]}],
#     "projects":[],
#     "certifications":[{"name":"","organization":"","year":"","details":""}],
#     "achievements":[],"languages":[],"interests":[],
#     "links":{"linkedin":"","github":"","portfolio":""}
#   }
# }
# """


#     prompt = """
# You are a Resume Tailoring Engine. Return one valid JSON object. No markdown.

# CRITICAL:
# - jd_analysis.target_role MUST come from JD_INFO — never from RESUME_TEXT or from examples below.
# - All generated content (role, summary, skills, bullets) MUST match JD_INFO for THIS request.
# - Never default to any fixed role or skill set. Every request is different — read JD_INFO first.

# ====================================================================
# 1. PRESERVE EXACTLY (from RESUME_TEXT — do not change)
# ====================================================================
# - name, email, phone_number, location
# - education, certifications, links, achievements, languages, interests (if present)
# - Per work entry: company, duration, project_name, location — copy exact

# ====================================================================
# 2. GENERATE NEW (from JD_INFO — never copy from resume)
# ====================================================================
# | Field | Rule |
# |-------|------|
# | jd_analysis.target_role | Extract exact role/title from JD_INFO |
# | tailored_resume.role | Copy work_experience[0].role after step 4 |
# | summary | 100% new — never copy original summary |
# | total_experience | Calculate from kept entry dates (step 4) — never copy resume header text |
# | technical_skills | Build from scratch from JD_INFO (step 6) |
# | work_experience.role | New titles in JD role domain — never original titles |
# | work_experience.responsibilities | New bullets — analyze original then reframe (step 7) |

# ====================================================================
# 3. RESUME STRUCTURE
# ====================================================================
# Employment-based: each job = one work_experience entry (keep company + duration exact)
# Project-based: each project block = one work_experience entry (keep project_name exact)
# - Do not merge entries
# - Order: most recent first (index 0 = latest)
# - projects = []

# ====================================================================
# 4. EXPERIENCE & ROLES
# ====================================================================
# target_role: read from JD_INFO (e.g. whatever role the JD states — engineer, analyst, manager, etc.)

# total_experience:
# - Calculate years from date ranges of KEPT entries in RESUME_TEXT
# - NEVER copy "X+ years" from original summary without calculating
# - NEVER use JD requirement text (e.g. "3-5 years required") as candidate total_experience
# - jd_analysis.overall_experience_required = JD requirement for analysis only

# Trimming (only if candidate years > JD maximum):
# - Remove OLDEST entries first; always keep most recent
# - Recalculate total_experience from kept entry dates only

# Role titles (new — based on jd_analysis.target_role):
# - Index 0 (latest): target role (+ Senior prefix if total_experience >= 5)
# - Middle entries: mid-level variant of target role domain
# - Oldest kept: junior/associate variant of target role domain
# - NEVER keep original job titles from RESUME_TEXT

# FINAL: tailored_resume.role = work_experience[0].role (character-for-character match)

# ====================================================================
# 5. SUMMARY
# ====================================================================
# - Write 3-5 new sentences for jd_analysis.target_role
# - Line 1: target role + total_experience (integer from step 4)
# - Highlight skills and themes from JD_INFO
# - If JD role differs from original resume profession: discard old profession wording entirely
# - Never copy or paraphrase original summary

# ====================================================================
# 6. SKILLS
# ====================================================================
# START with empty categories. Do NOT copy RESUME_TEXT skills section as-is.

# STEP 1: Add every skill/tool explicitly mentioned in JD_INFO
# STEP 2: From resume, add ONLY skills that support jd_analysis.target_role
# STEP 3: Remove ALL skills from old profession not needed for JD role
#   Rule: if skill is not in JD_INFO and not required for target role → exclude it
# STEP 4: Categorize into: languages, frameworks, libraries, databases, cloud, devops, tools, ai_ml, concepts, others
# Empty unused categories as []

# ====================================================================
# 7. RESPONSIBILITIES — JD ROLE ONLY (strict)
# ====================================================================
# Write responsibilities AS IF the candidate worked in jd_analysis.target_role on each project.
# Bullets describe JD-role work — never the candidate's original profession from RESUME_TEXT.

# Per entry: 4-5 bullets | 10-15 words each | all new text

# --- PER ENTRY (do independently for every work_experience row) ---

# 1. READ original entry in RESUME_TEXT:
#    project_name/company, synopsis, original bullets
#    → extract FACTS only: domain, product purpose, data/workflows, outcomes, metrics

# 2. READ JD_INFO:
#    target_role, responsibility themes, required skills/tools

# 3. WRITE bullets using this rule:
#    "What would a [target_role] have done on this project?"
#    - Facts from step 1 = project anchor (domain, product, company/project name)
#    - Wording from step 2 = JD role, JD skills, JD duty themes
#    - Every bullet must sound like target_role work — not the old profession

# 4. REJECT bullet if it:
#    - copies original resume bullet (same meaning or same key phrases)
#    - uses tools/terms from old profession not in JD_INFO
#    - could apply to any project with zero context
#    - copies a JD sentence verbatim
#    - matches the same pattern as another entry (template swap)

# --- JD-ROLE LANGUAGE (dynamic — derive from JD_INFO, not examples) ---
# Use verbs and nouns that match jd_analysis.target_role and JD responsibilities.
# Use skills/tools from JD_INFO in bullets — never default to a fixed skill list.
# If original resume was a different profession: rewrite ALL duties in target_role vocabulary.
# Changing job title without rewriting bullet profession = FAILED output.

# --- UNIQUENESS (mandatory) ---
# Each entry gets different bullets because each project had different facts in step 1.
# Do not repeat the same bullet structure across entries.
# Do not repeat the same opening verb in one entry.
# Spread JD responsibility themes across bullets — vary focus per bullet.

# --- VALIDATION (run before output) ---
# For each entry ask:
#   [ ] Would a hiring manager believe this is [target_role] work?
#   [ ] Are all 4-5 bullets 10-15 words?
#   [ ] Is any bullet copied from original resume? → rewrite
#   [ ] Is any bullet identical in pattern to another entry? → rewrite
#   [ ] Do bullets mention this entry's project/domain facts?

# --- Compact synthesis pattern (adapt to actual JD + project) ---
# "[JD-role verb] [JD duty] using [JD skill] for [project/company] [project-specific context]."
# Each bullet must use a different JD theme and different project fact — never clone across entries.

# ====================================================================
# 8. OUTPUT
# ====================================================================
# Valid JSON only. No nulls. Keys: jd_analysis, skill_gap_analysis, tailored_resume.

# {
#   "jd_analysis": {
#     "target_role": "",
#     "overall_experience_required": "",
#     "technical_skills": {"languages":[],"frameworks":[],"libraries":[],"databases":[],"cloud":[],"devops":[],"tools":[],"ai_ml":[],"concepts":[],"others":[]},
#     "responsibilities": [],
#     "domain_knowledge": [],
#     "certifications": []
#   },
#   "skill_gap_analysis": {"existing_skills":[],"missing_skills":[]},
#   "tailored_resume": {
#     "name":"","total_experience":0,"email":"","phone_number":"","location":"","role":"","summary":"",
#     "technical_skills":{"languages":[],"frameworks":[],"libraries":[],"databases":[],"cloud":[],"devops":[],"tools":[],"ai_ml":[],"concepts":[],"others":[]},
#     "education":[{"degree":"","field":"","institution":"","cgpa":"","duration":""}],
#     "work_experience":[{"role":"","company":"","project_name":"","location":"","duration":"","responsibilities":[]}],
#     "projects":[],
#     "certifications":[{"name":"","organization":"","year":"","details":""}],
#     "achievements":[],"languages":[],"interests":[],
#     "links":{"linkedin":"","github":"","portfolio":""}
#   }
# }
# """


    prompt = """
You are a Resume Tailoring Engine. Return one valid JSON object. No markdown.

CRITICAL:
- Read JD_INFO first. Extract jd_analysis.target_role, skills, and responsibility themes from JD_INFO only.
- Never assume a fixed role (not Data Analyst, not Java Developer, not QA). Every request is different.
- RESUME_TEXT provides project facts. JD_INFO defines how to rewrite them.

====================================================================
1. PRESERVE EXACTLY (from RESUME_TEXT)
====================================================================
name, email, phone_number, location, education, certifications, links, achievements, languages, interests
Per work entry: company, duration, project_name, location — exact copy

====================================================================
2. GENERATE NEW (from JD_INFO)
====================================================================
summary, technical_skills, work_experience.role, work_experience.responsibilities, tailored_resume.role, total_experience
Never copy original summary or original responsibility bullets verbatim.

====================================================================
3. STRUCTURE
====================================================================
- Employment resume: one work_experience entry per job
- Project resume: one work_experience entry per project block (keep project_name exact)
- Order: most recent first (index 0 = latest)
- projects = []

====================================================================
4. ROLES & EXPERIENCE
====================================================================
jd_analysis.target_role = exact role/title from JD_INFO

Role titles (derive from target_role — any JD role):
- Index 0 (latest): target_role (+ Senior if total_experience >= 5)
- Middle: mid-level variant of same role domain
- Oldest: junior/associate variant of same role domain
- Never keep original titles from RESUME_TEXT

total_experience: calculate from kept entry dates — never copy resume header text
FINAL: tailored_resume.role = work_experience[0].role

====================================================================
5. SUMMARY
====================================================================
3-5 new sentences for jd_analysis.target_role from JD_INFO.
Include JD skills/themes. Never copy original summary.
If JD role ≠ original profession: remove all old-profession terms.

====================================================================
6. SKILLS
====================================================================
Add ONLY skills explicitly in JD_INFO. Do not copy resume skills section.
Include a resume skill only if the same term appears in JD_INFO.
All other resume skills must be excluded.

====================================================================
7. RESPONSIBILITIES — GENERAL JD-BASED SYNTHESIS
====================================================================
This section is dynamic. Derive everything from JD_INFO + each project's original facts.

GOAL: For each work entry, write bullets as if the candidate worked as
jd_analysis.target_role on that project — using JD duties and JD skills.

Per entry: 4-5 bullets | 10-15 words each | 100% new text

--- STEP 1: EXTRACT from JD_INFO (once per request) ---
- target_role
- List responsibility themes from JD (parse Key Responsibilities / duties in JD_INFO)
- List skills/tools from JD (parse Qualifications & Skills in JD_INFO)
Store in jd_analysis.responsibilities and use these as the duty vocabulary for ALL entries.

--- STEP 2: EXTRACT from RESUME_TEXT (per entry) ---
For THIS work_experience entry only, read synopsis + original bullets.
Extract FACTS only (not wording):
  - business domain, product purpose, users, workflows
  - data/systems involved, integrations, deliverables, metrics/outcomes
Do NOT copy original bullet sentences.

--- STEP 3: SYNTHESIZE new bullets (per entry) ---
Ask: "What would a [target_role] have contributed on [this project]?"
For each bullet:
  - Pick one JD responsibility theme from Step 1
  - Pick one JD skill/tool from Step 1 where it fits naturally
  - Anchor to one project fact from Step 2 (domain, product, company/project_name)
  - Write in past-tense resume style for target_role

Rules:
- Bullets must sound like target_role work — not the candidate's original profession
- Use JD skills/tools in sentences — do not invent a fixed skill list
- Vary JD themes across bullets within the entry
- Each entry must differ from other entries (different project facts = different bullets)
- Mention project_name or company in 1-2 bullets only

--- FORBIDDEN ---
✗ Copying original resume bullets (same meaning or key phrases)
✗ Copying JD sentences verbatim
✗ Same bullet template across entries with only name swapped
✗ Using tools/terms from old profession that are NOT in JD_INFO
✗ Changing job title but keeping original profession wording in bullets
✗ Generic bullets with no project/domain context

--- VALIDATION (per entry before output) ---
[ ] 4-5 bullets, each 10-15 words
[ ] Every bullet reflects target_role + a JD theme from Step 1
[ ] Every bullet anchored to this entry's project facts from Step 2
[ ] No bullet matches original resume text
[ ] No two entries share the same bullet pattern

--- GENERAL PATTERN (adapt role/skills/themes from JD_INFO) ---
"[Past-tense verb] [JD duty theme] using [JD skill] for [project/company] [project-specific fact]."

====================================================================
8. OUTPUT — use exact JSON keys
====================================================================
{
  "jd_analysis": {
    "target_role": "",
    "overall_experience_required": "",
    "technical_skills": {"languages":[],"frameworks":[],"libraries":[],"databases":[],"cloud":[],"devops":[],"tools":[],"ai_ml":[],"concepts":[],"others":[]},
    "responsibilities": [],
    "domain_knowledge": [],
    "certifications": []
  },
  "skill_gap_analysis": {"existing_skills":[],"missing_skills":[]},
  "tailored_resume": {
    "name":"","total_experience":0,"email":"","phone_number":"","location":"","role":"","summary":"",
    "technical_skills":{"languages":[],"frameworks":[],"libraries":[],"databases":[],"cloud":[],"devops":[],"tools":[],"ai_ml":[],"concepts":[],"others":[]},
    "education":[{"degree":"","field":"","institution":"","cgpa":"","duration":""}],
    "work_experience":[{"role":"","company":"","project_name":"","location":"","duration":"","responsibilities":[]}],
    "projects":[],
    "certifications":[{"name":"","organization":"","year":"","details":""}],
    "achievements":[],"languages":[],"interests":[],
    "links":{"linkedin":"","github":"","portfolio":""}
  }
}
"""

    full_content = f"""
RESUME_TEXT:
{resume_text[:12000]}

JD_INFO:
{str(jd_info)[:8000]}
"""

    admin = db.query(Admin).filter(Admin.is_active == True).first()

    model_info = select_available_model(admin.admin_id)

    if not model_info:
        return Exception("No active AI model configured")
    
    model_config_id = model_info.get("model_config_id")
    model = model_info.get("model_name", "ollama").lower()
    version = model_info.get("version_name", "llama3").lower()
    base_url = model_info.get("base_url")
    api_key = model_info.get("apikey")
    api_key = decrypt_data(api_key)

    system_message = (
        "Resume tailoring engine. Return one JSON object using the exact JSON schema. "
        "Target role, skills, and responsibility themes come from JD_INFO only — no fixed role. "
        "Preserve only: name, email, phone, location, company, duration, project_name. "
        "For each work entry: extract project facts from resume, then write 4-5 NEW bullets "
        "(10-15 words) as jd_analysis.target_role duties using JD themes and JD skills. "
        "Never copy original bullets. Never keep old-profession wording. "
        "Each entry must have unique bullets. tailored_resume.role = work_experience[0].role."
    )

    message = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt + "\n\n" + full_content}
            ]

    if model == "openai":
        if not api_key or api_key == None:
            raise Exception("OpenAI API key not found")

        client = OpenAI(
            api_key=api_key,
            base_url = base_url)

    elif model == "claude":
        if not api_key or api_key == None:
            raise Exception("Claude API key not found")

        client = Anthropic(api_key=api_key)

        response = client.messages.create(
            model=version,
            max_tokens=2000,
            system=system_message,
            messages=[
                {"role": "user", "content": prompt + "\n\n" + full_content}
            ]
        )
        content = response.content[0].text.strip()
        logger.info(f" the response from Claude {response}")
    else:
        client = ollama
        response = client.chat(
            model = version,
            messages = message,
            format="json",
            options={
                "temperature": 0
    }
        )
        logger.info(f" the response from Ollama {response}")
        content = response["message"]["content"].strip()


    if model == "openai":
        response = create_json_completion(
            client=client,
            model=version,
            messages=message
        )
        content = response.choices[0].message.content.strip()
        token_used = response.usage.total_tokens
    
        usage = record_model_usage(model_config_id, token_used, admin.name)
        logger.info(f'{usage}, token used for the prompt: {token_used}')

    try:
        data = parse_llm_json(content)
        print(f"is_resume classification result: {data}")
    except Exception as e:
        print(f"Invalid JSON returned by model: {content}")
        raise ValueError("Model returned invalid JSON") from e
    
    return data

def clean_text(value):

    if value is None:
        return ""

    if isinstance(value, dict):
        return ""

    if isinstance(value, list):
        return ", ".join(map(str, value))

    return (
        str(value)
        .replace("\x00", "")
        .replace("fastapi_api |", "")
        .replace("postgres_db |", "")
        .strip()
    )

def add_heading(doc, text):

    heading = doc.add_heading(level=1)
    run = heading.add_run(text)
    run.bold = True
    run.font.size = Pt(14)

    return heading

def generate_resume_docx(data, output_path):
    try:
        doc = Document()

        section = doc.sections[0]

        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.7)
        section.right_margin = Inches(0.7)

        resume = data.get("tailored_resume", data)

        def safe_get(*keys, default=""):
            for key in keys:
                value = resume.get(key)
                if value not in [None, "", [], {}]:
                    return value
            return default

        name = clean_text(safe_get("name"))
        role = clean_text(safe_get("role"))
        phone = clean_text(safe_get("phone_number", "phoneNumber"))
        email = clean_text(safe_get("email"))
        location = clean_text(safe_get("location"))

        title = doc.add_paragraph()
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        run = title.add_run(name)
        run.bold = True
        run.font.size = Pt(20)

        if role:
            role_para = doc.add_paragraph()
            role_para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

            run = role_para.add_run(role)
            run.italic = True
            run.font.size = Pt(12)

        contact_items = [item for item in [phone, email, location] if item]
        if contact_items:
            contact = doc.add_paragraph()
            contact.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            contact.add_run(" | ".join(contact_items))

        summary = clean_text(safe_get("summary"))

        if summary:
            add_heading(doc, "Professional Summary")
            para = doc.add_paragraph(summary)
            para.style.font.size = Pt(11)

        technical_skills = safe_get("technical_skills", "technicalSkills", default={})

        if isinstance(technical_skills, dict) and any(technical_skills.values()):
            add_heading(doc, "Technical Skills")
            for category, skills in technical_skills.items():
                if not skills:
                    continue

                category_name = category.replace("_", " ").title()
                if isinstance(skills, list):
                    skills_text = ", ".join(
                        clean_text(skill)
                        for skill in skills
                        if skill
                    )
                else:
                    skills_text = clean_text(skills)

                doc.add_paragraph(
                    f"{category_name}: {skills_text}",
                    style="List Bullet"
                )

        work_experience = safe_get("work_experience", "workExperience", default=[])

        if isinstance(work_experience, list) and work_experience:
            valid_experience = []
            for exp in work_experience:
                if not isinstance(exp, dict):
                    continue

                job_title = clean_text(exp.get("role") or exp.get("jobTitle"))
                company = clean_text(exp.get("company"))
                project_name = clean_text(exp.get("project_name") or exp.get("projectName"))
                duration = clean_text(
                    exp.get("duration")
                    or " - ".join(
                        part for part in [
                            clean_text(exp.get("startDate")),
                            clean_text(exp.get("endDate"))
                        ] if part
                    )
                )
                responsibilities = exp.get("responsibilities")
                description = clean_text(exp.get("description"))

                if not any([job_title, company, project_name, duration, responsibilities, description]):
                    continue

                valid_experience.append({
                    "job_title": job_title,
                    "company": company,
                    "project_name": project_name,
                    "duration": duration,
                    "responsibilities": responsibilities,
                    "description": description,
                })

            if valid_experience:
                add_heading(doc, "Work Experience")

            for exp in valid_experience:
                job_title = exp["job_title"]
                company = exp["company"]
                project_name = exp["project_name"]
                duration = exp["duration"]
                responsibilities = exp["responsibilities"]
                description = exp["description"]

                title_para = doc.add_paragraph()
                heading_parts = [part for part in [job_title, company] if part]
                run = title_para.add_run(" | ".join(heading_parts))
                run.bold = True
                run.font.size = Pt(12)

                if project_name:
                    project_para = doc.add_paragraph()
                    run = project_para.add_run(project_name)
                    run.italic = True
                    run.font.size = Pt(10)

                if duration:
                    date_para = doc.add_paragraph()
                    run = date_para.add_run(duration)
                    run.italic = True
                    run.font.size = Pt(10)

                if isinstance(responsibilities, list):
                    for bullet in responsibilities:
                        bullet = clean_text(bullet)
                        if not bullet:
                            continue
                        para = doc.add_paragraph(bullet, style="List Bullet")
                        para.style.font.size = Pt(11)
                elif responsibilities:
                    para = doc.add_paragraph(clean_text(responsibilities))
                    para.style.font.size = Pt(11)
                elif description:
                    bullets = [bullet.strip() for bullet in description.split(".") if bullet.strip()]
                    for bullet in bullets:
                        para = doc.add_paragraph(bullet, style="List Bullet")
                        para.style.font.size = Pt(11)

        projects = safe_get("projects", default=[])

        if isinstance(projects, list) and projects:
            valid_projects = []
            for project in projects:
                if not isinstance(project, dict):
                    continue

                project_name = clean_text(project.get("name"))
                description = clean_text(project.get("description"))
                technologies = project.get("technologies",[])

                technologies_text = clean_text(technologies) if technologies else ""
                if not any([project_name, description, technologies_text]):
                    continue

                valid_projects.append({
                    "project_name": project_name,
                    "description": description,
                    "technologies_text": technologies_text
                })

            if valid_projects:
                add_heading(doc, "Projects")

            for project in valid_projects:
                project_name = project["project_name"]
                description = project["description"]
                technologies_text = project["technologies_text"]

                title_para = doc.add_paragraph()

                run = title_para.add_run(project_name)
                run.bold = True
                run.font.size = Pt(12)

                if description:
                    para = doc.add_paragraph(description)
                    para.style.font.size = Pt(11)

                if technologies_text:
                    tech_para = doc.add_paragraph()

                    run = tech_para.add_run(f"Technologies: {technologies_text}")
                    run.bold = True

        education = safe_get("education", default=[])

        if isinstance(education, list) and education:
            valid_education = []
            for edu in education:
                if not isinstance(edu, dict):
                    continue

                degree = clean_text(edu.get("degree"))
                field = clean_text(edu.get("field"))
                institution = clean_text(edu.get("institution"))
                percentage = clean_text(edu.get("cgpa") or edu.get("percentageCGPA"))
                duration = clean_text(
                    edu.get("duration")
                    or " - ".join(
                        part for part in [
                            clean_text(edu.get("startDate")),
                            clean_text(edu.get("endDate"))
                        ] if part
                    )
                )

                if not any([degree, field, institution, percentage, duration]):
                    continue

                valid_education.append({
                    "degree": degree,
                    "field": field,
                    "institution": institution,
                    "percentage": percentage,
                    "duration": duration
                })

            if valid_education:
                add_heading(doc, "Education")

            for edu in valid_education:
                degree = edu["degree"]
                field = edu["field"]
                institution = edu["institution"]
                percentage = edu["percentage"]
                duration = edu["duration"]

                para = doc.add_paragraph()
                title_text = " ".join(part for part in [degree, field] if part)
                run = para.add_run(title_text)
                run.bold = True
                run.font.size = Pt(12)

                edu_lines = []
                if institution:
                    edu_lines.append(institution)
                if duration:
                    edu_lines.append(duration)
                if percentage:
                    edu_lines.append(f"Percentage/CGPA: {percentage}")

                if edu_lines:
                    para.add_run("\n" + "\n".join(edu_lines))

        certifications = safe_get("certifications", default=[])
        if isinstance(certifications, list) and certifications:
            valid_certifications = []
            for cert in certifications:
                if not isinstance(cert, dict):
                    continue

                name = clean_text(cert.get("name"))
                organization = clean_text(cert.get("organization"))
                year = clean_text(cert.get("year"))
                details = clean_text(cert.get("details"))

                if any([name, organization, year, details]):
                    valid_certifications.append({
                        "name": name,
                        "organization": organization,
                        "year": year,
                        "details": details,
                    })

            if valid_certifications:
                add_heading(doc, "Certifications")

            for cert in valid_certifications:
                para = doc.add_paragraph(style="List Bullet")
                title_bits = [bit for bit in [cert["name"], cert["organization"], cert["year"]] if bit]
                run = para.add_run(" - ".join(title_bits))
                run.bold = True
                if cert["details"]:
                    para.add_run(f"\n{cert['details']}")

        achievements = safe_get("achievements", default=[])
        if isinstance(achievements, list) and achievements:
            cleaned_achievements = [clean_text(item) for item in achievements if clean_text(item)]
            if cleaned_achievements:
                add_heading(doc, "Achievements")
                for item in cleaned_achievements:
                    para = doc.add_paragraph(item, style="List Bullet")
                    para.style.font.size = Pt(11)

        languages = safe_get("languages", default=[])
        if isinstance(languages, list):
            languages_text = ", ".join(clean_text(item) for item in languages if clean_text(item))
            if languages_text:
                add_heading(doc, "Languages")
                para = doc.add_paragraph(languages_text)
                para.style.font.size = Pt(11)

        interests = safe_get("interests", default=[])
        if isinstance(interests, list):
            interests_text = ", ".join(clean_text(item) for item in interests if clean_text(item))
            if interests_text:
                add_heading(doc, "Interests")
                para = doc.add_paragraph(interests_text)
                para.style.font.size = Pt(11)

        links = safe_get("links", default={})
        if isinstance(links, dict):
            link_items = []
            for label in ["linkedin", "github", "portfolio"]:
                value = clean_text(links.get(label))
                if value:
                    link_items.append(f"{label.title()}: {value}")
            if link_items:
                add_heading(doc, "Links")
                for item in link_items:
                    para = doc.add_paragraph(item)
                    para.style.font.size = Pt(11)

        doc.save(output_path)

        return output_path
    except Exception as e:
        logger.error(f"Error in generate_resume_docx: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": str(e)}

def generate_resume_pdf(data, output_path):
    try:
        styles = getSampleStyleSheet()
        story = []

        resume = data.get("tailored_resume", data)

        def safe_get(*keys, default=""):
            for key in keys:
                value = resume.get(key)
                if value not in [None, "", [], {}]:
                    return value
            return default

        name = clean_text(safe_get("name"))
        role = clean_text(safe_get("role"))
        email = clean_text(safe_get("email"))
        phone = clean_text(safe_get("phone_number", "phoneNumber"))
        location = clean_text(safe_get("location"))
        summary = clean_text(safe_get("summary"))

        center_style = ParagraphStyle(
            "CenterStyle",
            parent=styles["Normal"],
            alignment=TA_CENTER
        )

        if name:
            story.append(Paragraph(f"<b>{name}</b>", styles["Title"]))

        if role:
            story.append(Paragraph(role, center_style))

        contact_info = [
            item for item in [phone, email, location]
            if item
        ]

        if contact_info:
            story.append(
                Paragraph(
                    " | ".join(contact_info),
                    center_style
                )
            )

        story.append(Spacer(1, 10))

        if summary:
            story.append(
                Paragraph(
                    "<b>Professional Summary</b>",
                    styles["Heading2"]
                )
            )
            story.append(
                Paragraph(summary, styles["Normal"])
            )
            story.append(Spacer(1, 8))

        technical_skills = safe_get(
            "technical_skills",
            "technicalSkills",
            default={}
        )

        if isinstance(technical_skills, dict):

            has_skill = any(
                value
                for value in technical_skills.values()
            )

            if has_skill:

                story.append(
                    Paragraph(
                        "<b>Technical Skills</b>",
                        styles["Heading2"]
                    )
                )

                for category, skills in technical_skills.items():

                    if not skills:
                        continue

                    if isinstance(skills, list):
                        skills_text = ", ".join(
                            clean_text(skill)
                            for skill in skills
                            if skill
                        )
                    else:
                        skills_text = clean_text(skills)

                    category_name = (
                        category
                        .replace("_", " ")
                        .title()
                    )

                    story.append(
                        Paragraph(
                            f"<b>{category_name}:</b> {skills_text}",
                            styles["Normal"]
                        )
                    )

                story.append(Spacer(1, 8))

        work_experience = safe_get(
            "work_experience",
            "workExperience",
            default=[]
        )

        if isinstance(work_experience, list) and work_experience:

            story.append(
                Paragraph(
                    "<b>Work Experience</b>",
                    styles["Heading2"]
                )
            )

            for exp in work_experience:

                if not isinstance(exp, dict):
                    continue

                title = clean_text(
                    exp.get("role") or exp.get("jobTitle")
                )

                company = clean_text(
                    exp.get("company")
                )

                duration = clean_text(
                    exp.get("duration")
                )

                heading = " | ".join(
                    item for item in [title, company]
                    if item
                )

                if heading:
                    story.append(
                        Paragraph(
                            f"<b>{heading}</b>",
                            styles["Normal"]
                        )
                    )

                if duration:
                    story.append(
                        Paragraph(
                            duration,
                            styles["Italic"]
                        )
                    )

                responsibilities = exp.get(
                    "responsibilities",
                    []
                )

                if isinstance(responsibilities, list):

                    bullets = []

                    for responsibility in responsibilities:

                        responsibility = clean_text(
                            responsibility
                        )

                        if responsibility:
                            bullets.append(
                                ListItem(
                                    Paragraph(
                                        responsibility,
                                        styles["Normal"]
                                    )
                                )
                            )

                    if bullets:
                        story.append(
                            ListFlowable(
                                bullets,
                                bulletType="bullet"
                            )
                        )

                elif responsibilities:
                    story.append(
                        Paragraph(
                            clean_text(responsibilities),
                            styles["Normal"]
                        )
                    )

                story.append(Spacer(1, 6))

        projects = safe_get(
            "projects",
            default=[]
        )

        if isinstance(projects, list) and projects:

            valid_projects = False

            for p in projects:
                if isinstance(p, dict) and any(p.values()):
                    valid_projects = True
                    break

            if valid_projects:

                story.append(
                    Paragraph(
                        "<b>Projects</b>",
                        styles["Heading2"]
                    )
                )

                for project in projects:

                    if not isinstance(project, dict):
                        continue

                    project_name = clean_text(
                        project.get("name")
                    )

                    description = clean_text(
                        project.get("description")
                    )

                    technologies = project.get(
                        "technologies",
                        []
                    )

                    if project_name:
                        story.append(
                            Paragraph(
                                f"<b>{project_name}</b>",
                                styles["Normal"]
                            )
                        )

                    if description:
                        story.append(
                            Paragraph(
                                description,
                                styles["Normal"]
                            )
                        )

                    if technologies:

                        if isinstance(
                            technologies,
                            list
                        ):
                            technologies = ", ".join(
                                technologies
                            )

                        story.append(
                            Paragraph(
                                f"<b>Technologies:</b> {technologies}",
                                styles["Normal"]
                            )
                        )

                    story.append(
                        Spacer(1, 6)
                    )

        education = safe_get(
            "education",
            default=[]
        )

        if isinstance(education, list) and education:

            story.append(
                Paragraph(
                    "<b>Education</b>",
                    styles["Heading2"]
                )
            )

            for edu in education:

                if not isinstance(edu, dict):
                    continue

                degree = clean_text(
                    edu.get("degree")
                )

                field = clean_text(
                    edu.get("field")
                )

                institution = clean_text(
                    edu.get("institution")
                )

                duration = clean_text(
                    edu.get("duration")
                )

                cgpa = clean_text(
                    edu.get("cgpa")
                    or edu.get("percentageCGPA")
                )

                title = " ".join(
                    item for item in [degree, field]
                    if item
                )

                if title:
                    story.append(
                        Paragraph(
                            f"<b>{title}</b>",
                            styles["Normal"]
                        )
                    )

                details = []

                if institution:
                    details.append(institution)

                if duration:
                    details.append(duration)

                if cgpa:
                    details.append(
                        f"CGPA/Percentage: {cgpa}"
                    )

                if details:
                    story.append(
                        Paragraph(
                            "<br/>".join(details),
                            styles["Normal"]
                        )
                    )

                story.append(
                    Spacer(1, 6)
                )

        certifications = safe_get(
            "certifications",
            default=[]
        )

        if isinstance(certifications, list) and certifications:

            valid_certs = [
                c for c in certifications
                if isinstance(c, dict)
                and any(c.values())
            ]

            if valid_certs:

                story.append(
                    Paragraph(
                        "<b>Certifications</b>",
                        styles["Heading2"]
                    )
                )

                for cert in valid_certs:

                    cert_name = clean_text(
                        cert.get("name")
                    )

                    org = clean_text(
                        cert.get("organization")
                    )

                    year = clean_text(
                        cert.get("year")
                    )

                    line = " - ".join(
                        x for x in [
                            cert_name,
                            org,
                            year
                        ]
                        if x
                    )

                    if line:
                        story.append(
                            Paragraph(
                                line,
                                styles["Normal"]
                            )
                        )

                story.append(
                    Spacer(1, 8)
                )

        pdf = SimpleDocTemplate(
            output_path,
            pagesize=A4
        )

        pdf.build(story)

        return output_path

    except Exception as e:
        logger.exception(
            "Error generating PDF"
        )

        return {
            "status": 500,
            "message": str(e)
        }
