import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

from app.core.config import get_settings
from app.models.user import UserRole

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".csv", ".xlsx"}


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_allowed_file(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type: {suffix}")
    return suffix


def max_bytes_for_role(role: UserRole) -> int:
    settings = get_settings()
    max_mb = settings.max_upload_mb_admin if role == UserRole.admin else settings.max_upload_mb_user
    return max_mb * 1024 * 1024


def ensure_upload_size(upload: UploadFile, role: UserRole) -> None:
    max_bytes = max_bytes_for_role(role)
    # FastAPI's UploadFile does not always expose size upfront.
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    if size > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File exceeds max size: {size} bytes")


def ensure_pdf_page_limit(file_path: Path, role: UserRole) -> int:
    settings = get_settings()
    reader = PdfReader(str(file_path))
    page_count = len(reader.pages)
    limit = settings.max_pdf_pages_admin if role == UserRole.admin else settings.max_pdf_pages_user
    if page_count > limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PDF page limit exceeded: {page_count} > {limit}",
        )
    return page_count
