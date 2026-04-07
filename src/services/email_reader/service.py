import imaplib
import email
from email.utils import parseaddr
from src.email_reader.models import EmailVersion, EmailLogs, Attachment
from db.connection import SessionLocal
import os
import uuid
import logging
from dotenv import load_dotenv
from src.services.background_task.tasks import resume_track
from pypdf import PdfReader
from docx import Document
import ollama
import json

load_dotenv()
logger = logging.getLogger(__name__)

def process_email(snapshot):
    """Process a single email snapshot containing email_id and attachments."""

    email_id = snapshot["email_id"]
    attachments = snapshot["attachments"]
    logger.info(f"Processing email {email_id}")
    for file in attachments:
        logger.info(f"Processing attachment {file}")
    logger.info("Done")

attachment_dir = os.getenv("ATTACHMENT_DIR","attachments")
IMAP_SERVER = os.getenv("IMAP_SERVER","imap.gmail.com")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT","")
PASSWORD = os.getenv("PASSWORD","")

def save_attachment(part, uid):
    """Save email attachment to attachment directory using a UUID derived from the IMAP UID."""

    if not os.path.exists(attachment_dir):
        os.makedirs(attachment_dir)

    original_name = part.get_filename()
    if original_name:
        _, ext = os.path.splitext(original_name)
    else:
        ext = f".{part.get_content_subtype() or 'bin'}"

    derived_name = f"{uuid.uuid5(uuid.NAMESPACE_URL, str(uid))}{ext}"

    counter = 0
    unique_name = derived_name
    base, ext = os.path.splitext(derived_name)
    while os.path.exists(os.path.join(attachment_dir, unique_name)):
        counter += 1
        unique_name = f"{base}_{counter}{ext}"

    path = os.path.join(attachment_dir, unique_name)
    with open(path, "wb") as f:
        f.write(part.get_payload(decode=True))

    return unique_name, path

def is_resume(text: str) -> bool:
    logger.info("NAV----> process started")
    # prompt = """
    #     You are a document classifier.

    #     Your task:
    #     Determine if the given document text belongs to a RESUME / CV.

    #     Return ONLY JSON.

    #     Format:
    #     {
    #     "is_resume": true
    #     }

    #     Rules:
    #     - Resume usually contains skills, experience, education, projects, etc.
    #     - If it is invoice, bill, report, offer letter, or random text → return false
    #     """
    prompt = """
        You are a strict classifier.

        Return ONLY JSON:
        {"is_resume": true} or {"is_resume": false}

        Rules:
        - Return TRUE only if this is clearly a complete resume/CV
        - A resume MUST contain at least 2 of these sections:
        Skills, Experience, Education, Projects

        - Return FALSE if:
        - It is incomplete
        - It is random text
        - It is invoice, email, report, or any other document
        - It looks like partial resume content

        - If unsure → return FALSE
        """

    try:
        logger.info('nav----> the is resume block started ')
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": "You only return JSON"},
                {"role": "user", "content": prompt + "\n\nDocument:\n" + text[:2000]}
            ]
        )

        content = response["message"]["content"].strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        data = json.loads(content[start:end])
        logger.info(f"NAV----> the resume content data {data} ")

        return data.get("is_resume", False)

    except Exception as e:
        print("Resume detection failed:", e)
        return False
    
def extract_attachment_text(path):
    """Extract text from PDF or DOCX attachment."""

    if path.endswith(".pdf"):
        text = ""
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    if path.endswith(".docx"):
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)

    return ""

def  fetch_emails() -> dict:
    """
    Fetch new emails from IMAP inbox and process them.

    - Tracks last processed UID to avoid duplicates
    - Stores email metadata in database
    - Saves and analyzes attachments (resume detection)
    - Triggers Celery task for further processing

    Returns:
        dict: Status message and last processed UID
    """

    db = SessionLocal()
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, PASSWORD)
    mail.select("INBOX")
    state = db.query(EmailVersion).first()
    if not state:
        status, data = mail.uid("search", None, "ALL")
        uids = data[0].split()
        if not uids:
            return {"message": "Mailbox empty"}

        latest_uid = int(uids[-1])
        state = EmailVersion(
            mailbox="INBOX",
            last_uid=latest_uid
        )
        db.add(state)
        db.commit()

        return {"message": f"Initialized last_uid = {latest_uid}"}
    last_uid = state.last_uid
    status, data = mail.uid("search", None, "ALL")
    all_uids = data[0].split()
    new_uids = [int(uid) for uid in all_uids if int(uid) > last_uid]
    if not new_uids:
        return {"message": "No new emails"}

    max_uid = last_uid
    for uid in new_uids:
        existing = db.query(EmailLogs).filter(EmailLogs.uid == uid).first()
        if existing:
            continue
        result, msg_data = mail.uid("fetch", str(uid), "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        message_id = msg.get("Message-ID")
        subject = msg.get("Subject")
        sender_header = msg.get("From")
        sender_address = parseaddr(sender_header or "")[1] or sender_header

        email_obj = EmailLogs(
            message_id=message_id,
            uid=uid,
            subject=subject,
            sender=sender_address
        )
        db.add(email_obj)
        db.commit()
        db.refresh(email_obj)
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                filename, path = save_attachment(part, message_id)
                text = extract_attachment_text(path)
                if not text.strip():
                    logger.info("Empty document:", filename)
                    continue
                resume_flag = is_resume(text)
                logger.info(f"NAV----> the resume flag {resume_flag} for the file {filename}")
                attachment = Attachment(
                    email_id=email_obj.email_id,
                    file_name=filename,
                    is_resume = resume_flag
                )
                db.add(attachment)
                db.commit()
        max_uid = max(max_uid, uid)
        logger.info(f"Processed email: {subject}")
        # celery_task = resume_track(email_obj.email_id)
        logger.info("NAV----> the celery work started")
        celery_task = resume_track.delay(str(email_obj.email_id))
        logger.info(f"NAV----> celery task completed")
        logger.info(f"NAV----> celery task completed {celery_task.id}")

    state.last_uid = max_uid
    db.commit()
    
    return {
        "message": "Emails processed",
        "last_uid": max_uid,
    }