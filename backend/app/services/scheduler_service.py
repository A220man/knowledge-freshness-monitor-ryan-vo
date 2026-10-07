"""Revalidation job scheduling, priority ranking, and queue management."""
import csv
import io
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from backend.app.models.entities import RagAnswer, RevalidationTask, CitationEdge


def calculate_task_priority(answer: RagAnswer) -> Dict[str, Any]:
    primary_compromised = any(
        c.is_primary and (c.revision.status in {"expired", "superseded"} or c.revision.drift_score >= 0.35)
        for c in answer.citations if c.revision
    )
    primary_penalty = 1.0 if primary_compromised else 0.0
    citations_count = len(answer.citations)
    breadth_factor = min(1.0, citations_count / 5.0)

    raw_score = (0.60 * answer.impact_score) + (0.25 * primary_penalty) + (0.15 * breadth_factor)
    score = round(max(0.0, min(1.0, raw_score)), 4)
    level = "high" if (score >= 0.70 or primary_compromised) else ("medium" if score >= 0.40 else "low")
    return {"priority_score": score, "priority_level": level}


def schedule_revalidation_task(
    db: Session,
    answer_id: str,
    reason: str,
    priority_level_override: Optional[str] = None,
    notes: str = ""
) -> RevalidationTask:
    answer = db.query(RagAnswer).filter(RagAnswer.id == answer_id).first()
    if not answer:
        raise ValueError(f"RagAnswer with id {answer_id} not found.")

    p_info = calculate_task_priority(answer)
    task = RevalidationTask(
        answer_id=answer.id, reason=reason, priority_score=p_info["priority_score"],
        priority_level=priority_level_override or p_info["priority_level"],
        status="pending", scheduled_at=datetime.now(timezone.utc), notes=notes
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def schedule_batch_revalidations(
    db: Session,
    min_impact_threshold: float = 0.30,
    override_existing: bool = False
) -> Dict[str, Any]:
    stale_answers = db.query(RagAnswer).filter(RagAnswer.impact_score >= min_impact_threshold).all()
    created_count = 0
    skipped_count = 0

    for ans in stale_answers:
        active_task = db.query(RevalidationTask).filter(
            RevalidationTask.answer_id == ans.id,
            RevalidationTask.status.in_(["pending", "in_progress"])
        ).first()

        if active_task and not override_existing:
            skipped_count += 1
            continue

        p_info = calculate_task_priority(ans)
        task = RevalidationTask(
            answer_id=ans.id,
            reason=f"Automated graph scan detected impact score {ans.impact_score:.2f} ({ans.freshness_status}).",
            priority_score=p_info["priority_score"],
            priority_level=p_info["priority_level"],
            status="pending",
            scheduled_at=datetime.now(timezone.utc),
            notes="Scheduled by automated batch freshness propagation."
        )
        db.add(task)
        created_count += 1

    db.commit()
    return {"evaluated_answers": len(stale_answers), "tasks_scheduled": created_count, "tasks_skipped": skipped_count}


def update_task_status(
    db: Session,
    task_id: str,
    new_status: str,
    user_id: Optional[str] = None,
    notes: Optional[str] = None
) -> RevalidationTask:
    task = db.query(RevalidationTask).filter(RevalidationTask.id == task_id).first()
    if not task:
        raise ValueError(f"RevalidationTask with id {task_id} not found.")

    task.status = new_status
    if notes is not None:
        task.notes = notes
    if new_status in {"completed", "dismissed"}:
        task.completed_at = datetime.now(timezone.utc)
        task.resolved_by = user_id or "system_operator"
        if new_status == "completed" and task.answer:
            task.answer.freshness_status = "fresh"
            task.answer.impact_score = 0.0
            task.answer.last_validated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(task)
    return task


def export_tasks_csv(db: Session) -> str:
    tasks = db.query(RevalidationTask).order_by(RevalidationTask.priority_score.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["task_id", "answer_id", "query_text", "status", "priority_level", "priority_score", "scheduled_at", "completed_at", "resolved_by", "reason"])
    for t in tasks:
        writer.writerow([
            t.id, t.answer_id, t.answer.query_text if t.answer else "", t.status, t.priority_level,
            f"{t.priority_score:.4f}", t.scheduled_at.isoformat() if t.scheduled_at else "",
            t.completed_at.isoformat() if t.completed_at else "", t.resolved_by or "", t.reason
        ])
    return output.getvalue()
