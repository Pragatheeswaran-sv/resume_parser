import os
import zipfile
import pikepdf
from dotenv import load_dotenv
import logging
import cryptography.fernet as fernet
import re
import phonenumbers

load_dotenv()
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY").encode()
cipher_suite = fernet.Fernet(SECRET_KEY)

def compress_pdf(input_path, output_path):
    try:
        with pikepdf.open(input_path) as pdf:
            pdf.save(
                output_path,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate
            )
        size = os.path.getsize(output_path)
        compressed_file_path = output_path.split('/')
        compressed_file_path = compressed_file_path[-1]
        logger.info(f"PDF compressed: {output_path} with size of {size}", compressed_file_path)
        return compressed_file_path
    except Exception as e:
        return(f"PDF compression failed: {e}")


def compress_docx(input_path, output_path):
    try:
        # DOCX is already a zip → recompress it
        with zipfile.ZipFile(input_path, 'r') as zin:
            with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    buffer = zin.read(item.filename)
                    zout.writestr(item, buffer)
        size = os.path.getsize(output_path)
        compressed_file_path = output_path.split('/')
        compressed_file_path = compressed_file_path[-1]
        logger.info(f"DOCX compressed: {output_path} with size of {size}")
        return compressed_file_path
    except Exception as e:
        return(f"DOCX compression failed: {e}")


def compress_file(input_file):
    if not os.path.exists(input_file):
        return("File does not exist")
        

    file_name, ext = os.path.splitext(input_file)
    ext = ext.lower()

    output_file = f"{file_name}_compressed{ext}"

    if ext == ".pdf":
        return compress_pdf(input_file, output_file)

    elif ext == ".docx":
        return compress_docx(input_file, output_file)

    else:
        return("Unsupported file type. Only PDF and DOCX allowed.")


def encrypt_data(data):
    encrypted_value = cipher_suite.encrypt(data.encode()).decode()
    return encrypted_value

def decrypt_data(encrypted_value):
    if not encrypted_value:
        return None

    try:
        if isinstance(encrypted_value, str):
            encrypted_value = encrypted_value.encode()

        return cipher_suite.decrypt(encrypted_value).decode()

    except fernet.InvalidToken:
        # Not a valid encrypted value (plain text or corrupted)
        return encrypted_value  # return as-is

    except Exception:
        return None

def clean_mobile_number(phone_number):
    try:
        # Remove spaces/dashes/brackets
        cleaned = re.sub(r"[^\d+]", "", phone_number)

        parsed = phonenumbers.parse(cleaned)

        return str(parsed.national_number)

    except Exception:
        return phone_number