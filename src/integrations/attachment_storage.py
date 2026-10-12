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
    """Service class for attachment storage operations."""

    def _backend(self) -> str:
        return os.getenv("ATTACHMENT_STORAGE", "local").strip().lower()

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
        """Upload a final attachment file and return its database filename.

        ``ATTACHMENT_STORAGE=local`` keeps the existing local development flow.
        With ``supabase``, this uploads to a private S3-compatible Supabase bucket.
        """
        path = Path(file_path)
        stored_name = Path(file_name or path.name).name
        backend = self._backend()
        if backend == "local":
            return stored_name
        if backend != "supabase":
            raise AttachmentStorageError("ATTACHMENT_STORAGE must be 'local' or 'supabase'")
        if not path.is_file():
            raise AttachmentStorageError(f"Attachment file does not exist: {path}")
        bucket = os.getenv("SUPABASE_S3_BUCKET")
        if not bucket:
            raise AttachmentStorageError("Supabase storage is enabled but SUPABASE_S3_BUCKET is missing")

        try:
            self._s3_client().upload_file(
                str(path), bucket, self._object_key(stored_name),
                ExtraArgs={"ContentType": mimetypes.guess_type(stored_name)[0] or "application/octet-stream"},
            )
        except Exception as exc:
            logger.exception("Unable to upload attachment %s to Supabase", stored_name)
            raise AttachmentStorageError("Unable to upload attachment to Supabase") from exc
        return stored_name

    def create_attachment_download_url(self, file_name: str, expires_in: int = 3600) -> str:
        """Create a short-lived URL for a private Supabase attachment object."""
        if self._backend() != "supabase":
            raise AttachmentStorageError("Supabase storage is not enabled")
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
        """Read an attachment from local storage or the configured Supabase bucket."""
        name = Path(file_name).name
        local_path = Path(local_dir or os.getenv("ATTACHMENT_DIR", "attachments")) / name
        if local_path.is_file():
            return local_path.read_bytes()
        backend = self._backend()
        if backend == "local":
            raise FileNotFoundError(f"{name} not found")
        if backend != "supabase":
            raise AttachmentStorageError("ATTACHMENT_STORAGE must be 'local' or 'supabase'")
        bucket = os.getenv("SUPABASE_S3_BUCKET")
        if not bucket:
            raise AttachmentStorageError("Supabase storage is enabled but SUPABASE_S3_BUCKET is missing")
        try:
            return self._s3_client().get_object(Bucket=bucket, Key=self._object_key(name))["Body"].read()
        except Exception as exc:
            logger.exception("Unable to fetch attachment %s to Supabase", name)
            raise FileNotFoundError(f"{name} not found in attachment storage") from exc

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
