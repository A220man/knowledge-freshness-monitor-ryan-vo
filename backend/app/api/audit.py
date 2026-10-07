"""Audit logging query endpoints for administrators."""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import require_admin
from backend.app.models.entities import UserSession
from backend.app.models.schemas import AuditLogResponse
from backend.app.services.audit_service import get_audit_logs

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=List[AuditLogResponse])
def list_audit_trail(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: UserSession = Depends(require_admin),
    db: Session = Depends(get_db)
) -> List[AuditLogResponse]:
    """Retrieves immutable audit trail entries."""
    logs = get_audit_logs(db, limit=limit, offset=offset)
    return logs
