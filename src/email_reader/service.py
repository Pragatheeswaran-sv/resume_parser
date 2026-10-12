"""Email reader service layer.

Provides IMAP email ingestion, attachment parsing and extraction,
metadata storage, and asynchronous resume processing delegation.
"""

from contextlib import contextmanager
import email
from email.utils import parseaddr
import imaplib
import logging
import os
from typing import Any, Dict, Generator, Optional, Tuple
import uuid

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from db.connection import SessionLocal
from src.celery.tasks import resume_track
from src.email_reader.models import Attachment, EmailLogs, EmailVersion

load_dotenv()
logger = logging.getLogger(__name__)

ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR", "attachments")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT", "")
PASSWORD = os.getenv("PASSWORD", "")


# =============================================================================
# 1. Base Service
# =============================================================================

class BaseService:
    """Base service offering transactional DB session management."""

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    @contextmanager
    def get_session(self, session: Optional[Session] = None) -> Generator[Session, None, None]:
        """Provide a transactional database session scope."""
        if session is not None:
            yield session
            return
        if self._db is not None:
            yield self._db
            return
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


# =============================================================================
# 2. Email Reader Service
# =============================================================================

class EmailReaderService(BaseService):
    """Handles IMAP email polling, attachment persistence, and Celery dispatch."""

    def __init__(
        self,
        db: Optional[Session] = None,
        imap_server: Optional[str] = None,
        email_account: Optional[str] = None,
        password: Optional[str] = None,
        attachment_dir: Optional[str] = None,
    ):
        super().__init__(db=db)
        self.imap_server = imap_server or IMAP_SERVER
        self.email_account = email_account or EMAIL_ACCOUNT
        self.password = password or PASSWORD
        self.attachment_dir = attachment_dir or ATTACHMENT_DIR

    def process_email(self, snapshot: Dict[str, Any]) -> None:
        """Process a single email snapshot containing email_id and attachments."""
        email_id = snapshot.get("email_id")
        attachments = snapshot.get("attachments", [])
        logger.info("Processing email %s", email_id)
        for file in attachments:
            logger.info("Processing attachment %s", file)
        logger.info("Done")

    def save_attachment(self, part: Any, uid: Any) -> Tuple[str, str]:
        """Save email attachment to attachment directory using a UUID derived from the IMAP UID."""
        if not os.path.exists(self.attachment_dir):
            os.makedirs(self.attachment_dir, exist_ok=True)

        original_name = part.get_filename()
        if original_name:
            _, ext = os.path.splitext(original_name)
        else:
            ext = f".{part.get_content_subtype() or 'bin'}"

        derived_name = f"{uuid.uuid5(uuid.NAMESPACE_URL, str(uid))}{ext}"

        counter = 0
        unique_name = derived_name
        base, ext = os.path.splitext(derived_name)
        while os.path.exists(os.path.join(self.attachment_dir, unique_name)):
            counter += 1
            unique_name = f"{base}_{counter}{ext}"

        path = os.path.join(self.attachment_dir, unique_name)
        with open(path, "wb") as f:
            f.write(part.get_payload(decode=True))
        size = os.path.getsize(path)
        logger.info("%s saved in attachment with size of %d", path, size)
        return unique_name, path

    def fetch_emails(self, session: Optional[Session] = None) -> Dict[str, Any]:
        """Fetch new emails from IMAP inbox and process them.

        - Tracks last processed UID to avoid duplicates
        - Stores email metadata in database
        - Saves attachments to disk and records them
        - Triggers Celery task for resume processing

        Returns:
            Dict[str, Any]: Status message and last processed UID
        """
        with self.get_session(session) as db:
            mail = None
            try:
                mail = imaplib.IMAP4_SSL(self.imap_server)
                mail.login(self.email_account, self.password)
                mail.select("INBOX")
                state = db.query(EmailVersion).first()
                if not state:
                    status_resp, data = mail.uid("search", None, "ALL")
                    uids = data[0].split()
                    if not uids:
                        return {"message": "Mailbox empty"}

                    latest_uid = int(uids[-1])
                    state = EmailVersion(
                        mailbox="INBOX",
                        last_uid=latest_uid,
                    )
                    db.add(state)
                    db.commit()

                    return {"message": f"Initialized last_uid = {latest_uid}"}

                last_uid = state.last_uid
                status_resp, data = mail.uid("search", None, "ALL")
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
                        sender=sender_address,
                    )
                    db.add(email_obj)
                    db.commit()
                    db.refresh(email_obj)

                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            filename, path = self.save_attachment(part, uid)
                            attachment = Attachment(
                                email_id=email_obj.email_id,
                                file_name=filename,
                            )
                            db.add(attachment)
                            db.commit()

                    max_uid = max(max_uid, uid)
                    logger.info("Processed email: %s", subject)
                    logger.info("the celery work started")
                    celery_task = resume_track.delay(str(email_obj.email_id))
                    logger.info("celery task completed %s", celery_task.id)

                state.last_uid = max_uid
                db.commit()

                return {
                    "message": "Emails processed",
                    "last_uid": max_uid,
                }

            finally:
                if mail:
                    try:
                        mail.logout()
                    except Exception:
                        pass


# Global singleton instance
email_reader_service = EmailReaderService()


# =============================================================================
# 3. Backward-Compatible Function Exports
# =============================================================================

def process_email(snapshot: Dict[str, Any]) -> None:
    return email_reader_service.process_email(snapshot)


def save_attachment(part: Any, uid: Any) -> Tuple[str, str]:
    return email_reader_service.save_attachment(part, uid)


def fetch_emails() -> Dict[str, Any]:
    return email_reader_service.fetch_emails()


__all__ = [
    "BaseService",
    "EmailReaderService",
    "email_reader_service",
    "process_email",
    "save_attachment",
    "fetch_emails",
]