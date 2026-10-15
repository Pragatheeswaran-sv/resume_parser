"""Persistent attachment storage backed by Supabase's S3-compatible API."""
from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class AttachmentStorageError(RuntimeError):
    """Raised when the configured attachment backend cannot store or fetch a file."""


class AttachmentStorageService:
    """Service class for attachment storage operations.

    Supports hybrid storage:
    - Files are always preserved in the local storage directory.
    - If Supabase S3 credentials exist in .env, files are also uploaded/synced to Supabase.
    - If Supabase credentials are not present, operates smoothly with local storage.
    """

    def has_supabase_credentials(self) -> bool:
        """Check whether all required Supabase S3 credentials exist in .env."""
        endpoint = os.getenv("SUPABASE_S3_ENDPOINT")
        access_key = os.getenv("SUPABASE_S3_ACCESS_KEY")
        secret_key = os.getenv("SUPABASE_S3_SECRET_KEY")
        bucket = os.getenv("SUPABASE_S3_BUCKET")
        return bool(
            endpoint and endpoint.strip()
            and access_key and access_key.strip()
            and secret_key and secret_key.strip()
            and bucket and bucket.strip()
        )

    def _backend(self) -> str:
        explicit = os.getenv("ATTACHMENT_STORAGE", "").strip().lower()
        if explicit in {"supabase", "local"}:
            return explicit
        return "supabase" if self.has_supabase_credentials() else "local"

    def _object_key(self, file_name: str) -> str:
        name = Path(file_name).name
        if not name or name in {".", ".."}:
            raise AttachmentStorageError("Attachment filename is invalid")
        prefix = os.getenv("SUPABASE_S3_PREFIX", "resumes").strip("/")
        return f"{prefix}/{name}" if prefix else name

    def _s3_client(self):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover
            raise AttachmentStorageError("boto3 must be installed for Supabase storage") from exc

        endpoint = os.getenv("SUPABASE_S3_ENDPOINT")
        access_key = os.getenv("SUPABASE_S3_ACCESS_KEY")
        secret_key = os.getenv("SUPABASE_S3_SECRET_KEY")
        missing = [name for name, value in {
            "SUPABASE_S3_ENDPOINT": endpoint,
            "SUPABASE_S3_ACCESS_KEY": access_key,
            "SUPABASE_S3_SECRET_KEY": secret_key,
        }.items() if not value]
        if missing:
            raise AttachmentStorageError(f"Supabase storage is enabled but missing: {', '.join(missing)}")
        return boto3.client(
            "s3", endpoint_url=endpoint, aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=os.getenv("SUPABASE_S3_REGION", "us-east-1"),
            config=Config(s3={"addressing_style": "path"}),
        )

    def upload_attachment(self, file_path: str, file_name: str | None = None) -> str:
        """Store attachment file locally and upload to Supabase if credentials exist."""
        path = Path(file_path)
        stored_name = Path(file_name or path.name).name

        if not path.is_file():
            raise AttachmentStorageError(f"Attachment file does not exist: {path}")

        # If Supabase credentials exist in .env, upload a copy to Supabase
        if self.has_supabase_credentials():
            bucket = os.getenv("SUPABASE_S3_BUCKET")
            try:
                self._s3_client().upload_file(
                    str(path), bucket, self._object_key(stored_name),
                    ExtraArgs={"ContentType": mimetypes.guess_type(stored_name)[0] or "application/octet-stream"},
                )
                logger.info("Uploaded attachment %s to Supabase S3 bucket %s", stored_name, bucket)
            except Exception as exc:
                logger.exception("Unable to upload attachment %s to Supabase; retaining local copy: %s", stored_name, exc)
        else:
            logger.info("Supabase credentials not configured in .env; stored %s in local directory", stored_name)

        return stored_name

    def create_attachment_download_url(self, file_name: str, expires_in: int = 3600) -> str:
        """Create a short-lived URL for a private Supabase attachment object."""
        if not self.has_supabase_credentials():
            raise AttachmentStorageError("Supabase credentials are not configured in .env")
        bucket = os.getenv("SUPABASE_S3_BUCKET")
        if not bucket:
            raise AttachmentStorageError("Supabase storage is enabled but SUPABASE_S3_BUCKET is missing")
        # AWS Signature V4 presigned URLs have a maximum validity of seven days.
        expires_in = max(60, min(expires_in, 604800))
        try:
            return self._s3_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": self._object_key(file_name)},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            logger.exception("Unable to create a download URL for %s", file_name)
            raise AttachmentStorageError("Unable to create attachment download URL") from exc

    def read_attachment(self, file_name: str, local_dir: str | None = None) -> bytes:
        """Read an attachment from local storage first, fallback to Supabase if missing."""
        name = Path(file_name).name
        local_path = Path(local_dir or os.getenv("ATTACHMENT_DIR", "attachments")) / name
        if local_path.is_file():
            return local_path.read_bytes()

        # Fallback to Supabase if local file is missing and credentials are set
        if self.has_supabase_credentials():
            bucket = os.getenv("SUPABASE_S3_BUCKET")
            try:
                data = self._s3_client().get_object(Bucket=bucket, Key=self._object_key(name))["Body"].read()
                # Cache to local disk for future fast access
                try:
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(data)
                except Exception:
                    pass
                return data
            except Exception as exc:
                logger.exception("Unable to fetch attachment %s from Supabase", name)
                raise FileNotFoundError(f"{name} not found in attachment storage") from exc

        raise FileNotFoundError(f"{name} not found in local directory and Supabase is not configured")

    def stage_attachment(self, file_name: str, local_dir: str | None = None) -> str:
        """Return a local path, downloading a remote attachment only when needed."""
        directory = Path(local_dir or os.getenv("ATTACHMENT_DIR", "attachments"))
        path = directory / Path(file_name).name
        if not path.is_file():
            directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.read_attachment(file_name, str(directory)))
        return str(path)


AttachmentStorage = AttachmentStorageService
attachment_storage_service = AttachmentStorageService()

# Backward-compatible function references
upload_attachment = attachment_storage_service.upload_attachment
create_attachment_download_url = attachment_storage_service.create_attachment_download_url
read_attachment = attachment_storage_service.read_attachment
stage_attachment = attachment_storage_service.stage_attachment
