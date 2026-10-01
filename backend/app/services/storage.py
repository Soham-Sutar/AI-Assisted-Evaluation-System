import os
import uuid
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple
from fastapi import HTTPException, status
from app.core.config import settings

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS

ALLOWED_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "application/pdf": ".pdf",
}


def get_base_storage_dir() -> Path:
    """Retrieve and ensure base storage directory exists."""
    base_dir = Path(settings.STORAGE_PATH).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def sanitize_filename(filename: str) -> str:
    """Sanitize user-provided filename by stripping path separators and special chars."""
    clean_name = os.path.basename(filename)
    return "".join(c for c in clean_name if c.isalnum() or c in (".", "_", "-")).strip()


def validate_file_upload(
    filename: str,
    content_type: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
) -> str:
    """
    Validate file extension, mime type, and file size.
    Returns normalized extension (e.g. '.pdf', '.png', '.jpg').
    """
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename",
        )

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if content_type:
        mime_clean = content_type.split(";")[0].strip().lower()
        if mime_clean not in ALLOWED_MIME_TYPES and mime_clean != "application/octet-stream":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported MIME type '{content_type}' for answer sheet upload",
            )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if file_size_bytes is not None and file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_MB}MB",
        )

    return ext


def get_answer_sheet_dirs(answer_sheet_id: str) -> Dict[str, Path]:
    """
    Create and return isolated directory structure for an answer sheet:
    - root: /app/storage/answer_sheets/{id}/
    - original: /app/storage/answer_sheets/{id}/original/
    - processed: /app/storage/answer_sheets/{id}/processed/
    - crops: /app/storage/answer_sheets/{id}/crops/
    """
    base_dir = get_base_storage_dir()
    sheet_root = (base_dir / "answer_sheets" / answer_sheet_id).resolve()
    
    # Path traversal check
    if not str(sheet_root).startswith(str(base_dir)):
        raise ValueError("Invalid answer sheet path detected")

    original_dir = sheet_root / "original"
    processed_dir = sheet_root / "processed"
    crops_dir = sheet_root / "crops"

    original_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    return {
        "root": sheet_root,
        "original": original_dir,
        "processed": processed_dir,
        "crops": crops_dir,
    }


def save_original_file(answer_sheet_id: str, file_bytes: bytes, extension: str) -> str:
    """
    Safely save original uploaded file using server-generated UUID filename.
    Never uses user-controlled filename as the storage path.
    Returns the absolute path as string.
    """
    dirs = get_answer_sheet_dirs(answer_sheet_id)
    safe_filename = f"original_{uuid.uuid4().hex[:12]}{extension}"
    target_path = dirs["original"] / safe_filename

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    return str(target_path.resolve())


def verify_safe_path(file_path: str) -> Path:
    """Ensure a file path stays within the application storage directory."""
    base_dir = get_base_storage_dir()
    target = Path(file_path).resolve()
    if not str(target).startswith(str(base_dir)):
        raise ValueError(f"Access denied: path traversal attempt detected for '{file_path}'")
    return target


def cleanup_answer_sheet(answer_sheet_id: str) -> None:
    """Remove storage directory for an answer sheet."""
    base_dir = get_base_storage_dir()
    sheet_root = (base_dir / "answer_sheets" / answer_sheet_id).resolve()
    if str(sheet_root).startswith(str(base_dir)) and sheet_root.exists():
        shutil.rmtree(sheet_root, ignore_errors=True)
