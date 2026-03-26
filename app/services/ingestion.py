import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus, IngestionJob, JobStatus
from app.services.chunker import split_into_chunks
from app.services.embedding import embedding_service
from app.services.parser import parse_document
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)


def run_ingestion_job(job_id: str) -> None:
    db: Session = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return

        document = db.query(Document).filter(Document.id == job.document_id).first()
        if not document:
            job.status = JobStatus.failed
            job.error_message = "Document not found"
            db.add(job)
            db.commit()
            return

        job.status = JobStatus.running
        job.started_at = datetime.utcnow()
        document.status = DocumentStatus.parsing
        db.add_all([job, document])
        db.commit()

        file_path = Path(document.file_path)
        parsed_chunks, page_count = parse_document(file_path)
        document.page_count = page_count
        document.status = DocumentStatus.parsed
        db.add(document)
        db.commit()

        document.status = DocumentStatus.chunking
        db.add(document)
        db.commit()

        chunks = split_into_chunks(parsed_chunks)
        document.status = DocumentStatus.chunked
        db.add(document)
        db.commit()

        document.status = DocumentStatus.embedding
        db.add(document)
        db.commit()

        texts = [c.text for c in chunks]
        vectors = embedding_service.embed_texts(texts)

        # Remove old chunks on reindex.
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        db.commit()

        metadata: list[dict] = []
        for chunk in chunks:
            chunk_row = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.text,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                token_count=chunk.token_count,
            )
            db.add(chunk_row)
            db.flush()
            metadata.append(
                {
                    "chunk_id": chunk_row.id,
                    "document_id": document.id,
                    "owner_type": document.owner_type.value,
                    "owner_id": document.owner_id,
                    "document_title": document.title,
                    "original_filename": document.original_filename,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "chunk_index": chunk.chunk_index,
                    "source_type": document.source_type.value,
                    "status": DocumentStatus.indexed.value,
                    "text": chunk.text,
                }
            )

        db.commit()
        vector_store.upsert(vectors=vectors, metadata=metadata)

        document.status = DocumentStatus.indexed
        job.status = JobStatus.success
        job.finished_at = datetime.utcnow()
        db.add_all([document, job])
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.exception("Ingestion failed for job=%s", job_id)
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = JobStatus.failed
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            db.add(job)
        document = db.query(Document).filter(Document.id == job.document_id).first() if job else None
        if document:
            document.status = DocumentStatus.failed
            db.add(document)
        db.commit()
    finally:
        db.close()
