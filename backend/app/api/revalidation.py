"""Revalidation job queue, prioritization, and export API."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import require_viewer, require_analyst
from backend.app.models.entities import RevalidationTask, UserSession
from backend.app.models.schemas import (
    RevalidationTaskCreate,
    RevalidationTaskUpdate,
    RevalidationTaskResponse,
    BatchRevalidationScheduleRequest
)
from backend.app.services.scheduler_service import (
    schedule_revalidation_task,
    schedule_batch_revalidations,
    update_task_status,
    export_tasks_csv
)
from backend.app.services.audit_service import log_action

router = APIRouter(prefix="/api/revalidation", tags=["revalidation"])


@router.get("/tasks", response_model=List[RevalidationTaskResponse])
def list_revalidation_tasks(
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: UserSession = Depends(require_viewer),
    db: Session = Depends(get_db)
) -> List[RevalidationTask]:
    query = db.query(RevalidationTask)
    if status_filter:
        query = query.filter(RevalidationTask.status == status_filter)
    if priority_filter:
        query = query.filter(RevalidationTask.priority_level == priority_filter)
    return query.order_by(RevalidationTask.priority_score.desc()).offset(offset).limit(limit).all()


@router.post("/tasks", response_model=RevalidationTaskResponse, status_code=status.HTTP_201_CREATED)
def create_revalidation_task(
    payload: RevalidationTaskCreate,
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> RevalidationTask:
    try:
        task = schedule_revalidation_task(
            db=db, answer_id=payload.answer_id, reason=payload.reason,
            priority_level_override=payload.priority_level, notes=payload.notes or ""
        )
        log_action(db=db, user_id=session.user_id, action="revalidation.create_task", resource_type="revalidation_task", resource_id=task.id, details={})
        return task
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/batch", response_model=Dict[str, Any])
def batch_schedule_tasks(
    payload: BatchRevalidationScheduleRequest,
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    result = schedule_batch_revalidations(
        db=db, min_impact_threshold=payload.min_impact_threshold, override_existing=payload.override_existing_pending
    )
    log_action(db=db, user_id=session.user_id, action="revalidation.batch_schedule", resource_type="revalidation_queue", resource_id="batch", details=result)
    return result


@router.patch("/tasks/{task_id}", response_model=RevalidationTaskResponse)
def modify_task_status(
    task_id: str,
    payload: RevalidationTaskUpdate,
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> RevalidationTask:
    try:
        task = update_task_status(
            db=db, task_id=task_id, new_status=payload.status, user_id=session.user_id, notes=payload.notes
        )
        log_action(db=db, user_id=session.user_id, action="revalidation.update_status", resource_type="revalidation_task", resource_id=task.id, details={})
        return task
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/export")
def export_tasks(
    session: UserSession = Depends(require_viewer),
    db: Session = Depends(get_db)
) -> Response:
    csv_data = export_tasks_csv(db)
    return Response(
        content=csv_data, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=revalidation_tasks.csv"}
    )
