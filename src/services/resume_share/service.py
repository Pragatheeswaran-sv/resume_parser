import logging
import os
from typing import List, Optional

from sqlalchemy.orm import Session

from db.connection import SessionLocal
from src.candidate.models import (
	Candidate,
	CandidateEducation,
	CandidateSkills,
	Education,
	Skill,
	WorkExperience,
	Company,
	Role,
)
from src.resume_filter.models import Resume
from src.email_reader.models import Attachment
from src.resume_share.models import EmailNotification, EmailProviderConfig, EmailTemplate
from src.services.resume_share.email_sender import send_email

logger = logging.getLogger(__name__)

ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR", "attachments")


class ResumeShareError(Exception):
	def __init__(self, message: str, status_code: int = 400):
		self.message = message
		self.status_code = status_code
		super().__init__(self.message)


def _fetch_candidate_details(db: Session, candidate_id: str) -> dict:
	"""Return a dict of candidate fields; only populated values are included."""
	candidate = db.query(Candidate).filter_by(candidate_id=candidate_id).first()
	if not candidate:
		raise ResumeShareError("Candidate not found", status_code=404)

	details = {}
	if candidate.name:
		details["name"] = candidate.name
	if candidate.email_address:
		details["email"] = candidate.email_address
	if candidate.phone_number:
		details["phone"] = candidate.phone_number
	if candidate.location:
		details["location"] = candidate.location
	if candidate.total_experience is not None:
		details["total_experience"] = f"{candidate.total_experience} Years"

	educations = (
		db.query(Education.education, CandidateEducation.institution)
		.join(CandidateEducation, Education.education_id == CandidateEducation.education_id)
		.filter(CandidateEducation.candidate_id == candidate_id)
		.all()
	)
	if educations:
		edu_parts = []
		for edu in educations:
			part = edu.education
			if edu.institution:
				part += f" ({edu.institution})"
			edu_parts.append(part)
		details["education"] = ", ".join(edu_parts)

	skills = (
		db.query(Skill.skill)
		.join(CandidateSkills, Skill.skill_id == CandidateSkills.skill_id)
		.filter(CandidateSkills.candidate_id == candidate_id)
		.all()
	)
	if skills:
		details["skills"] = ", ".join(s.skill for s in skills)

	work_exps = (
		db.query(Role.role, Company.company_name, WorkExperience.start_date, WorkExperience.end_date)
		.join(WorkExperience, Role.role_id == WorkExperience.role_id)
		.join(Company, Company.company_id == WorkExperience.company_id)
		.filter(WorkExperience.candidate_id == candidate_id)
		.order_by(WorkExperience.start_date.desc())
		.all()
	)
	if work_exps:
		exp_parts = []
		for we in work_exps:
			end = we.end_date.strftime("%b %Y") if we.end_date else "Present"
			start = we.start_date.strftime("%b %Y") if we.start_date else ""
			exp_parts.append(f"{we.role} at {we.company_name} ({start} - {end})")
		details["work_experience"] = "; ".join(exp_parts)
		details["current_company"] = work_exps[0].company_name
		details["job_role"] = work_exps[0].role

	return details


def _fetch_resume_and_attachment(db: Session, resume_id: str, candidate_id: str) -> tuple:
	"""Return (file_path, file_name, candidate_role) for the given resume."""
	resume = db.query(Resume).filter_by(resume_id=resume_id).first()
	if not resume:
		raise ResumeShareError("Resume not found", status_code=404)

	if str(resume.candidate_id) != str(candidate_id):
		raise ResumeShareError("Resume does not belong to the specified candidate", status_code=400)

	if not resume.attachment_id:
		raise ResumeShareError("Resume has no attached file", status_code=404)

	attachment = db.query(Attachment).filter_by(attachment_id=resume.attachment_id).first()
	if not attachment:
		raise ResumeShareError("Attachment record not found", status_code=404)

	file_path = os.path.join(ATTACHMENT_DIR, attachment.file_name)
	if not os.path.exists(file_path):
		raise ResumeShareError(f"Attachment file not found on disk: {attachment.file_name}", status_code=404)

	return file_path, attachment.file_name, resume.candidate_role


def _render_template(template_body: str, candidate_details: dict) -> str:
	"""Render the email template, omitting any field whose value is empty/None."""
	field_labels = {
		"name": "Name",
		"email": "Email",
		"phone": "Phone Number",
		"job_role": "Job Role",
		"location": "Location",
		"total_experience": "Total Experience",
		"education": "Education",
		"skills": "Skills",
		"work_experience": "Work Experience",
		"current_company": "Current Company",
		"notice_period": "Notice Period",
		"current_ctc": "Current CTC",
		"expected_ctc": "Expected CTC",
	}

	rendered_fields = []
	for key, label in field_labels.items():
		value = candidate_details.get(key)
		if value:
			rendered_fields.append(f"<b>{label}:</b> {value}")

	fields_html = "<br>".join(rendered_fields)

	result = template_body
	result = result.replace("{{candidate_fields}}", fields_html)

	for key, label in field_labels.items():
		placeholder = "{{" + key + "}}"
		value = candidate_details.get(key)
		if value:
			result = result.replace(placeholder, f"<b>{label}:</b> {value}")
		else:
			lines = result.split("\n")
			lines = [line for line in lines if placeholder not in line]
			result = "\n".join(lines)

	return result


def share_resume_via_email(
	candidate_id: str,
	resume_id: str,
	to_address: str,
	share_log_id,
	cc_address: Optional[List[str]] = None,
	
) -> dict:
	"""Orchestrate fetching data, rendering template, and sending email."""
	db = SessionLocal()
	try:
		logger.info("Share resume request received — candidate=%s, resume=%s, to=%s",
					 candidate_id, resume_id, to_address)

		provider_config = db.query(EmailProviderConfig).filter_by(active=True).first()
		if not provider_config:
			raise ResumeShareError("No active email provider configuration found", status_code=400)
		logger.info("Email provider selected: %s", provider_config.provider_name)

		candidate_details = _fetch_candidate_details(db, candidate_id)
		logger.info("Candidate fetched: %s", candidate_details.get("name", candidate_id))

		file_path, file_name, candidate_role = _fetch_resume_and_attachment(db, resume_id, candidate_id)
		if candidate_role and "job_role" not in candidate_details:
			candidate_details["job_role"] = candidate_role
		logger.info("Resume attachment resolved: %s", file_name)

		template = db.query(EmailTemplate).filter_by(template_name="Resume Template", is_active=True).first()
		if not template:
			raise ResumeShareError("Email template 'Resume Template' not found", status_code=404)
		logger.info("Template loaded: %s", template.template_name)

		email_body = _render_template(template.body, candidate_details)

		candidate_name = candidate_details.get("name", "Candidate")
		subject = template.subject or f"Resume - {candidate_name}"
		subject = subject.replace("{{name}}", candidate_name)

		ext = os.path.splitext(file_name)[1] or ".pdf"
		friendly_filename = candidate_name.strip().replace(" ", "_") + "_Resume" + ext

		db = SessionLocal()
		email_notification = db.query(EmailNotification).filter(EmailNotification.email_share_id == share_log_id).first()
		if email_notification != None :
			print('--Data')
			email_notification.subject = subject
			email_notification.mail_body = email_body
			db.add(email_notification)
			db.commit()
			db.refresh(email_notification)

		config_dict = {
			"provider_name": provider_config.provider_name,
			"from_email": provider_config.from_email,
			"host": provider_config.host,
			"port": provider_config.port,
			"username": provider_config.username,
			"password": provider_config.password,
			"tls_enabled": provider_config.tls_enabled,
		}

		result = send_email(
			config=config_dict,
			to_address=to_address,
			cc_address=cc_address,
			subject=subject,
			html_body=email_body,
			attachment_path=file_path,
			attachment_filename=friendly_filename,
		)

		if not result["success"]:
			logger.error("Email send failed: %s", result["error"])
			raise ResumeShareError(f"Email send failed: {result['error']}", status_code=500)

		logger.info("Email sent successfully: %s", result)
		logger.info("Email sent successfully — message_id=%s", result["message_id"])
		return {
			"success": True,
			"message": "Email sent successfully",
			"email_id": result["message_id"],
		}

	finally:
		db.close()
