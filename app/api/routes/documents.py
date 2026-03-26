import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit
from app.core.config import get_settings
from app.db.session import get_db
from app.models.document import Document, DocumentStatus, IngestionJob, JobStatus, JobType, OwnerType, SourceType
from app.models.user import User, UserRole
from app.schemas.api import DocumentOut, ReindexResponse
from app.services.audit import write_audit_log
from app.services.auth import get_current_user, require_admin
from app.services.file_utils import compute_sha256, ensure_allowed_file, ensure_pdf_page_limit, ensure_upload_size
from app.services.ingestion import run_ingestion_job

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _serialize_document(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        owner_type=doc.owner_type.value,
        owner_id=doc.owner_id,
        title=doc.title,
        original_filename=doc.original_filename,
        status=doc.status.value,
        source_type=doc.source_type.value,
        page_count=doc.page_count,
        created_at=doc.created_at.isoformat(),
    )


@router.post("/upload", response_model=ReindexResponse)
def upload_document(
    background_tasks: BackgroundTasks,
    scope: str,
    file: UploadFile = File(...),
    current_user: User = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> ReindexResponse:
    if scope not in {"global", "user"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope must be global or user")

    if scope == "global" and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required for global scope")

    ensure_allowed_file(file.filename)
    ensure_upload_size(file, current_user.role)

    settings = get_settings()
    if scope == "global":
        base_dir = settings.data_dir / "admin_docs"
        owner_type = OwnerType.global_
        owner_id = None
        source_type = SourceType.admin_upload
    else:
        base_dir = settings.data_dir / "user_docs" / current_user.id
        owner_type = OwnerType.user
        owner_id = current_user.id
        source_type = SourceType.user_upload

    base_dir.mkdir(parents=True, exist_ok=True)
    target = base_dir / file.filename

    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    page_count = None
    if Path(file.filename).suffix.lower() == ".pdf":
        page_count = ensure_pdf_page_limit(target, current_user.role)

    checksum = compute_sha256(target)

    document = Document(
        owner_type=owner_type,
        owner_id=owner_id,
        uploaded_by=current_user.id,
        title=Path(file.filename).stem,
        original_filename=file.filename,
        file_path=str(target.resolve()),
        mime_type=file.content_type or "application/octet-stream",
        source_type=source_type,
        checksum=checksum,
        page_count=page_count,
        status=DocumentStatus.uploaded,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    job = IngestionJob(
        document_id=document.id,
        triggered_by=current_user.id,
        job_type=JobType.index,
        status=JobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    write_audit_log(
        db,
        actor_id=current_user.id,
        action="document.upload",
        resource_type="document",
        resource_id=document.id,
        metadata={"scope": scope, "filename": file.filename},
    )

    background_tasks.add_task(run_ingestion_job, job.id)
    return ReindexResponse(document_id=document.id, job_id=job.id, status=job.status.value)


@router.get("", response_model=list[DocumentOut])
def list_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DocumentOut]:
    if current_user.role == UserRole.admin:
        docs = db.query(Document).order_by(Document.created_at.desc()).all()
    else:
        docs = (
            db.query(Document)
            .filter((Document.owner_type == OwnerType.global_) | ((Document.owner_type == OwnerType.user) & (Document.owner_id == current_user.id)))
            .order_by(Document.created_at.desc())
            .all()
        )
    return [_serialize_document(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DocumentOut:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role != UserRole.admin:
        allowed = doc.owner_type == OwnerType.global_ or (doc.owner_type == OwnerType.user and doc.owner_id == current_user.id)
        if not allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
    return _serialize_document(doc)


@router.post("/{document_id}/reindex", response_model=ReindexResponse)
def reindex_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReindexResponse:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.owner_type == OwnerType.global_ and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admin can reindex global docs")
    if doc.owner_type == OwnerType.user and doc.owner_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    doc.status = DocumentStatus.uploaded
    db.add(doc)
    db.commit()

    job = IngestionJob(
        document_id=doc.id,
        triggered_by=current_user.id,
        job_type=JobType.reindex,
        status=JobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    write_audit_log(
        db,
        actor_id=current_user.id,
        action="document.reindex",
        resource_type="document",
        resource_id=doc.id,
        metadata={"job_id": job.id},
    )

    background_tasks.add_task(run_ingestion_job, job.id)
    return ReindexResponse(document_id=doc.id, job_id=job.id, status=job.status.value)


@router.delete("/{document_id}")
def archive_document(document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.owner_type == OwnerType.global_ and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admin can archive global docs")
    if doc.owner_type == OwnerType.user and doc.owner_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    doc.status = DocumentStatus.archived
    db.add(doc)
    db.commit()

    write_audit_log(
        db,
        actor_id=current_user.id,
        action="document.archive",
        resource_type="document",
        resource_id=doc.id,
        metadata={},
    )
    return {"status": "archived", "document_id": doc.id}


@router.get("/{document_id}/status")
def document_status(document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role != UserRole.admin:
        allowed = doc.owner_type == OwnerType.global_ or (doc.owner_type == OwnerType.user and doc.owner_id == current_user.id)
        if not allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
    return {"document_id": doc.id, "status": doc.status.value, "page_count": doc.page_count}
