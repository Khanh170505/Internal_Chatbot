import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.document import Document, IngestionJob
from app.schemas.api import UserOut
from app.services.auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def admin_stats(_: UserOut = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return {
        "documents_total": db.query(func.count(Document.id)).scalar() or 0,
        "jobs_total": db.query(func.count(IngestionJob.id)).scalar() or 0,
        "audit_logs_total": db.query(func.count(AuditLog.id)).scalar() or 0,
    }


@router.get("/audit-logs")
def audit_logs(_: UserOut = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    output = []
    for log in logs:
        output.append(
            {
                "id": log.id,
                "actor_id": log.actor_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "metadata": json.loads(log.metadata_json),
                "created_at": log.created_at.isoformat(),
            }
        )
    return output
