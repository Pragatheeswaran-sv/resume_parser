from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from db.connection import Base
import datetime


class FetchedMails(Base):
    __tablename__ = "fetched_mails"

    id = Column(Integer, primary_key=True)
    mailbox = Column(String)
    last_uid = Column(Integer)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True)
    message_id = Column(String)
    uid = Column(Integer)
    subject = Column(String)
    sender = Column(String)
    processed = Column(Boolean, default=False)


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id"))
    file_name = Column(String)
    file_path = Column(String)
    is_resume = Column(Boolean, default=False)

    email = relationship("Email")