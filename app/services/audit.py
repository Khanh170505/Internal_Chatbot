import json
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    metadata: dict,
) -> None:
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=json.dumps(metadata, ensure_ascii=True),
    )
    db.add(log)
    db.commit()
