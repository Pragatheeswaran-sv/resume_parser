import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import make_msgid
from typing import List, Optional

logger = logging.getLogger(__name__)


def _send_smtp(
    config: dict,
    to_address: str,
    cc_address: Optional[List[str]],
    subject: str,
    html_body: str,
    attachment_path: Optional[str],
    attachment_filename: Optional[str],
) -> dict:
    """Send email via SMTP and return {"success": bool, "message_id": str, "error": str}."""
    msg = MIMEMultipart()
    msg["From"] = config["from_email"]
    msg["To"] = to_address
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=config["from_email"].split("@")[-1])

    if cc_address:
        msg["Cc"] = ", ".join(cc_address)

    msg.attach(MIMEText(html_body, "html"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = attachment_filename or os.path.basename(attachment_path)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)

    recipients = [to_address]
    if cc_address:
        recipients.extend(cc_address)
    try:
        server = smtplib.SMTP(config["host"], config["port"])
        if config.get("tls_enabled", True):
            server.starttls()

        server.login(config["username"], config["password"])
    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "message_id": None,
            "error": "Invalid Gmail credentials or App Password required",
        }
    except smtplib.SMTPConnectError:
        return {
            "success": False,
            "message_id": None,
            "error": "SMTP server connection failed",
        }
    except Exception as e:
        return {"success": False, "message_id": None, "error": str(e)}

    try:
        server.sendmail(config["from_email"], recipients, msg.as_string())
    except Exception as e:
        return {"success": False, "message_id": None, "error": str(e)}
    finally:
        server.quit()

    message_id = msg.get("Message-ID", "")
    logger.info("SMTP email sent successfully to %s", to_address)
    return {"success": True, "message_id": message_id, "error": None}


def send_email(
    config: dict,
    to_address: str,
    cc_address: Optional[List[str]],
    subject: str,
    html_body: str,
    attachment_path: Optional[str] = None,
    attachment_filename: Optional[str] = None,
) -> dict:
    """Route to the correct provider based on config["provider_name"].

    Returns dict with keys: success (bool), message_id (str|None), error (str|None).
    """
    provider = config["provider_name"].lower()

    if provider == "smtp":
        return _send_smtp(
            config,
            to_address,
            cc_address,
            subject,
            html_body,
            attachment_path,
            attachment_filename,
        )
    elif provider == "outlook":
        return {
            "success": False,
            "message_id": None,
            "error": "Outlook provider is not yet implemented. Please use SMTP.",
        }
    elif provider == "sendgrid":
        return {
            "success": False,
            "message_id": None,
            "error": "SendGrid provider is not yet implemented. Please use SMTP.",
        }
    else:
        return {
            "success": False,
            "message_id": None,
            "error": f"Unsupported email provider: {config['provider_name']}",
        }
