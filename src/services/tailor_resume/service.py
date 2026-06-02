import logging
import datetime
from datetime import timezone
from zoneinfo import ZoneInfo
import re
from tomlkit import value
import ollama
import json

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

load_dotenv()
logger = logging.getLogger(__name__)

db = SessionLocal()

def alter_resume(payload, resume_id):
    try:
        if not payload or not resume_id:
            raise ValueError("Payload and resume_id are required.")

        skills = payload.get("skills") or []
        work_experience = payload.get("work_experience") or []
        profile_summary = payload.get("profile_summary") or ""

        resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
        attachment_id = resume.attachment_id
        
        if resume is None:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Resume not found."} 
        
        att = db.query(Attachment).filter(Attachment.attachment_id == attachment_id).first()
        file_path = f"attachments/{att.file_name}"

        if file_path.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        elif file_path.endswith(".docx"):
            text = extract_docx_text(file_path)

        jd_skills = ", ".join(skills) if isinstance(skills, list) else clean_text(skills)
        clean_skills = 'skills: ' + jd_skills if jd_skills.strip() != "" else ""
        item = []
        for key, value in work_experience[0].items():
            txt = f"{key}: {value}"
            item.append(txt)
        jd_work_exp = " ".join(item)
        
        clean_jd_work_exp = 'work_experience: ' + jd_work_exp if jd_work_exp.strip() != "" else ""
        clean_profile_summary = 'profile_summary: ' + profile_summary if profile_summary.strip() != "" else ""

        combined_text = f"{clean_skills}\n {clean_jd_work_exp}\n {clean_profile_summary}".strip()
        data = tailor_resume(text, combined_text)



        output_ext = ".pdf" if file_path.lower().endswith(".pdf") else ".docx"
        output_path = f"attachments/tailored_{att.file_name.rsplit('.', 1)[0]}{output_ext}"
        if output_ext == ".pdf":
            make_resume = generate_resume_pdf(data, output_path)
        else:
            make_resume = generate_resume_docx(data, output_path)
        return f"resume tailored successfully saved at {make_resume}"
    
    except Exception as e:
        logger.error(f"Error in alter_resume: {str(e)}")
        return {"status" : status.HTTP_500_INTERNAL_SERVER_ERROR, "message": str(e)}
    finally:
        db.close()


def tailor_resume(resume_text, jd_text):
    try:
        prompt = f"""
            You are an ATS resume parser and optimizer.

            Analyze the resume text and return structured resume data.

            Instructions:

            - Extract resume information accurately
            - Clean duplicated OCR text
            - Ignore logs, advertisements, URLs, and broken OCR words
            - Preserve important resume content
            - Merge additional information naturally
            - Improve ATS keywords professionally
            - Keep resume realistic
            - Categorize technical skills into languages, frameworks, libraries, databases, tools, cloud, devops, and others
            - Correct obvious spelling mistakes and standardize skill names (e.g., Gjango → Django, psql → PostgreSQL)
            - Do not duplicate a skill across multiple categories
            - If a skill cannot be confidently categorized, place it in "others"

            Return ONLY valid JSON.

            JSON Rules:
            - No markdown
            - No comments
            - No trailing commas
            - Use empty string for missing values
            - Arrays must always be arrays
            - Output must be a valid JSON object

            Return this structure exactly:

            {{
                "name": "",
                "role": "",
                "phoneNumber": "",
                "email": "",
                "location": "",
                "summary": "",
                "technicalSkills": {{
                        "languages": [],
                        "frameworks": [],
                        "libraries": [],
                        "databases": [],
                        "tools": [],
                        "cloud": [],
                        "devops": [],
                        "others": []
                    }},
                "workExperience": [
                    {{
                        "jobTitle": "",
                        "company": "",
                        "startDate": "",
                        "endDate": "",
                        "description": ""
                    }}
                ],
                "projects": [
                    {{
                        "name": "",
                        "description": "",
                        "technologies": []
                    }}
                ],
                "education": [
                    {{
                        "degree": "",
                        "institution": "",
                        "percentageCGPA": "",
                        "startDate": "",
                        "endDate": ""
                    }}
                ],
                "certifications": [
                    {{
                        "name": "",
                        "organization": "",
                        "details": ""
                    }}
                ],
                "links": {{
                    "linkedin": "",
                    "github": "",
                    "portfolio": ""
                }}
            }}

            ADDITIONAL INFORMATION:
            {jd_text}

            RESUME TEXT:
            {resume_text[:10000]}
            """
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
                messages = message,
                format="json",
                options={
                    "temperature": 0
        }
            )
            logger.info(f" the response from Ollama {response}")
            content = response["message"]["content"].strip()

        def _extract_largest_json_object(raw: str) -> str:
            start_positions = [i for i, ch in enumerate(raw) if ch == "{"]
            candidates = []
            for start in start_positions:
                depth = 0
                in_string = False
                escaped = False
                for idx in range(start, len(raw)):
                    ch = raw[idx]
                    if in_string:
                        if escaped:
                            escaped = False
                        elif ch == "\\":
                            escaped = True
                        elif ch == '"':
                            in_string = False
                        continue

                    if ch == '"':
                        in_string = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            candidates.append(raw[start:idx + 1])
                            break

            if not candidates:
                return ""
            return max(candidates, key=len)

        try:
            cleaned = content.strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

            json_str = _extract_largest_json_object(cleaned)
            if not json_str:
                raise ValueError("No valid JSON object found in model response")

            json_str = re.sub(r",\s*}", "}", json_str)
            json_str = re.sub(r",\s*]", "]", json_str)

            data = json.loads(json_str)
            if not isinstance(data, dict):
                raise ValueError("Model JSON root must be an object")

            logger.info(f"is_resume classification result: {data}")
        except Exception as e:
            logger.error(f"Invalid JSON returned by model: {content}")
            raise ValueError("Model returned invalid JSON") from e
        
        return data
    except Exception as e:
        logger.error(f"Error in tailor_resume: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": str(e)}
    finally:
        db.close()

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

        name = clean_text(data.get("name"))
        role = clean_text(data.get("role"))
        phone = clean_text(data.get("phoneNumber"))
        email = clean_text(data.get("email"))
        location = clean_text(data.get("location"))

        title = doc.add_paragraph()

        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        run = title.add_run(name)

        run.bold = True
        run.font.size = Pt(20)

        if role:

            role_para = doc.add_paragraph()

            role_para.alignment = (
                WD_PARAGRAPH_ALIGNMENT.CENTER
            )

            run = role_para.add_run(role)

            run.italic = True
            run.font.size = Pt(12)

        contact = doc.add_paragraph()

        contact.alignment = (WD_PARAGRAPH_ALIGNMENT.CENTER)

        contact.add_run(f"{phone} | {email} | {location}")

        summary = clean_text(data.get("summary"))

        if summary:
            add_heading(doc, "Professional Summary")
            para = doc.add_paragraph(summary)
            para.style.font.size = Pt(11)

        technical_skills = data.get("technicalSkills", {})

        if (isinstance(technical_skills, dict) and technical_skills):
            add_heading(doc, "Technical Skills")
            for category, skills in technical_skills.items():
                if not skills:
                    continue

                category_name = category.replace("_", " ").title()

                skills_text = ", ".join(
                    clean_text(skill)
                    for skill in skills
                    if skill
                )

                doc.add_paragraph(
                    f"{category_name}: {skills_text}",
                    style="List Bullet"
                )

        work_experience = data.get("workExperience", [])

        if (isinstance(work_experience, list) and work_experience):
            valid_experience = []
            for exp in work_experience:
                if not isinstance(exp, dict):
                    continue

                job_title = clean_text(exp.get("jobTitle"))
                company = clean_text(exp.get("company"))
                start_date = clean_text(exp.get("startDate"))
                end_date = clean_text(exp.get("endDate"))
                description = clean_text(exp.get("description"))

                if not any([job_title, company, start_date, end_date, description]):
                    continue

                valid_experience.append({
                    "job_title": job_title,
                    "company": company,
                    "start_date": start_date,
                    "end_date": end_date,
                    "description": description
                })

            if valid_experience:
                add_heading(doc, "Work Experience")

            for exp in valid_experience:
                job_title = exp["job_title"]
                company = exp["company"]
                start_date = exp["start_date"]
                end_date = exp["end_date"]
                description = exp["description"]

                title_para = doc.add_paragraph()
                run = title_para.add_run(f"{job_title} | {company}")
                run.bold = True
                run.font.size = Pt(12)

                # DATES
                if start_date or end_date:
                    date_para = doc.add_paragraph()
                    run = date_para.add_run(f"{start_date} - {end_date}")

                    run.italic = True
                    run.font.size = Pt(10)

                # DESCRIPTION
                if description:

                    bullets = [
                        bullet.strip()
                        for bullet in description.split(".")
                        if bullet.strip()
                    ]

                    for bullet in bullets:
                        para = doc.add_paragraph(bullet, style="List Bullet")
                        para.style.font.size = Pt(11)

        projects = data.get("projects", [])

        if (isinstance(projects, list) and projects):
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

        education = data.get("education", [])

        if (isinstance(education, list) and education):
            valid_education = []
            for edu in education:
                if not isinstance(edu, dict):
                    continue

                degree = clean_text(edu.get("degree"))
                institution = clean_text(edu.get("institution"))
                percentage = clean_text(edu.get("percentageCGPA"))
                start_date = clean_text(edu.get("startDate"))
                end_date = clean_text(edu.get("endDate"))

                if not any([degree, institution, percentage, start_date, end_date]):
                    continue

                valid_education.append({
                    "degree": degree,
                    "institution": institution,
                    "percentage": percentage,
                    "start_date": start_date,
                    "end_date": end_date
                })

            if valid_education:
                add_heading(doc, "Education")

            for edu in valid_education:
                degree = edu["degree"]
                institution = edu["institution"]
                percentage = edu["percentage"]
                start_date = edu["start_date"]
                end_date = edu["end_date"]

                para = doc.add_paragraph()
                run = para.add_run(degree)
                run.bold = True
                run.font.size = Pt(12)

                edu_text = (f"\n{institution} "f"\n{start_date} - {end_date}")

                if percentage:
                    edu_text += (f"\nPercentage/CGPA: {percentage}")
                para.add_run(edu_text)

        doc.save(output_path)

        return output_path
    except Exception as e:
        logger.error(f"Error in generate_resume_docx: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": str(e)}

def generate_resume_pdf(data, output_path):
    try:
        styles = getSampleStyleSheet()
        story = []

        name = clean_text(data.get("name"))
        role = clean_text(data.get("role"))
        phone = clean_text(data.get("phoneNumber"))
        email = clean_text(data.get("email"))
        location = clean_text(data.get("location"))
        summary = clean_text(data.get("summary"))

        center_style = ParagraphStyle(
            "CenterStyle",
            parent=styles["Normal"],
            alignment=TA_CENTER
        )

        if name:
            story.append(Paragraph(f"<b>{name}</b>", styles["Title"]))
        if role:
            story.append(Paragraph(role, styles["Italic"]))
        contact_text = " | ".join([v for v in [phone, email, location] if v])
        if contact_text:
            story.append(Paragraph(contact_text, center_style))

        story.append(Spacer(1, 8))

        if summary:
            story.append(Paragraph("<b>Professional Summary</b>", styles["Heading2"]))
            story.append(Paragraph(summary, styles["Normal"]))
            story.append(Spacer(1, 8))

        technical_skills = data.get("technicalSkills", {})

        if (isinstance(technical_skills, dict) and technical_skills):
            story.append(Paragraph("<b>Technical Skills</b>", styles["Heading2"]))

            for category, skills in technical_skills.items():
                if not skills:
                    continue

                category_name = (category.replace("_", " ").title())
                skills_text = ", ".join(map(clean_text, skills))
                story.append(Paragraph(f"<b>{category_name} :</b> {skills_text}", styles["Normal"]))

            story.append(Spacer(1, 8))

        work_experience = data.get("workExperience", [])
        if isinstance(work_experience, list) and work_experience:
            valid_experience = []
            for exp in work_experience:
                if not isinstance(exp, dict):
                    continue
                row = {
                    "jobTitle": clean_text(exp.get("jobTitle")),
                    "company": clean_text(exp.get("company")),
                    "startDate": clean_text(exp.get("startDate")),
                    "endDate": clean_text(exp.get("endDate")),
                    "description": clean_text(exp.get("description")),
                }
                if any(row.values()):
                    valid_experience.append(row)
            if valid_experience:
                story.append(Paragraph("<b>Work Experience</b>", styles["Heading2"]))
                for exp in valid_experience:
                    story.append(Paragraph(f"<b>{exp['jobTitle']} | {exp['company']}</b>", styles["Normal"]))
                    if exp["startDate"] or exp["endDate"]:
                        story.append(Paragraph(f"{exp['startDate']} - {exp['endDate']}", styles["Italic"]))
                    if exp["description"]:
                        bullets = [b.strip() for b in exp["description"].split(".") if b.strip()]
                        if bullets:
                            story.append(ListFlowable(
                                [ListItem(Paragraph(b, styles["Normal"])) for b in bullets],
                                bulletType="bullet"
                            ))
                    story.append(Spacer(1, 6))

        projects = data.get("projects", [])
        if isinstance(projects, list) and projects:
            valid_projects = []
            for proj in projects:
                if not isinstance(proj, dict):
                    continue

                name = clean_text(proj.get("name"))
                desc = clean_text(proj.get("description"))
                technologies = proj.get("technologies", [])
                technologies_text = clean_text(technologies) if technologies else ""
                if any([name, desc, technologies_text]):
                    valid_projects.append((name, desc, technologies_text))
                    
            if valid_projects:
                story.append(Paragraph("<b>Projects</b>", styles["Heading2"]))
                for name, desc, technologies_text in valid_projects:
                    if name:
                        story.append(Paragraph(f"<b>{name}</b>", styles["Normal"]))
                    if desc:
                        story.append(Paragraph(desc, styles["Normal"]))
                    if technologies_text:
                        story.append(Paragraph(f"<b>Technologies:</b> {technologies_text}", styles["Normal"]))
                    story.append(Spacer(1, 6))

        education = data.get("education", [])
        if isinstance(education, list) and education:
            valid_education = []
            for edu in education:
                if not isinstance(edu, dict):
                    continue
                degree = clean_text(edu.get("degree"))
                institution = clean_text(edu.get("institution"))
                percentage = clean_text(edu.get("percentageCGPA"))
                start_date = clean_text(edu.get("startDate"))
                end_date = clean_text(edu.get("endDate"))
                if any([degree, institution, percentage, start_date, end_date]):
                    valid_education.append((degree, institution, percentage, start_date, end_date))
            if valid_education:
                story.append(Paragraph("<b>Education</b>", styles["Heading2"]))
                for degree, institution, percentage, start_date, end_date in valid_education:
                    if degree:
                        story.append(Paragraph(f"<b>{degree}</b>", styles["Normal"]))
                    date_line = f"{start_date} - {end_date}".strip(" -")
                    lines = [line for line in [institution, date_line] if line]
                    if percentage:
                        lines.append(f"Percentage/CGPA: {percentage}")
                    if lines:
                        story.append(Paragraph("<br/>".join(lines), styles["Normal"]))
                    story.append(Spacer(1, 6))

        pdf = SimpleDocTemplate(output_path, pagesize=A4)
        pdf.build(story)
        return output_path
    except Exception as e:
        logger.error(f"Error in generate_resume_pdf: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": str(e)}