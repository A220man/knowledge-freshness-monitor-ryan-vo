"""Transactional audit logging service."""
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.models.entities import AuditLog


def log_action(
    db: Session,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: Dict[str, Any]
) -> AuditLog:
    """Records an audit log entry for a mutation."""
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=json.dumps(details),
        created_at=datetime.now(timezone.utc)
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def get_audit_logs(
    db: Session,
    limit: int = 50,
    offset: int = 0
) -> List[AuditLog]:
    """Retrieves paginated audit trail logs ordered by most recent."""
    return (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
