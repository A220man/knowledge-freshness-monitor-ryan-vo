import csv
import io
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from backend.app.models.entities import RagAnswer, RevalidationTask, CitationEdge


def calculate_task_priority(answer: RagAnswer) -> Dict[str, Any]:
    primary_compromised = any(
        edge.is_primary and edge.revision.status in {"stale", "expired", "superseded"}
        for edge in answer.citations
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
        raise ValueError(f"RagAnswer {answer_id} not found")

    priority = calculate_task_priority(answer)
    priority_level = priority_level_override or priority["priority_level"]

    task = RevalidationTask(
        answer_id=answer_id,
        reason=reason,
        priority_score=priority["priority_score"],
        priority_level=priority_level,
        notes=notes,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def schedule_batch_revalidations(
    db: Session,
    min_impact_threshold: float = 0.25,
    max_tasks: int = 50,
    override_existing: bool = False
) -> Dict[str, Any]:
    stale_answers = db.query(RagAnswer).filter(RagAnswer.impact_score >= min_impact_threshold).all()
    created_count = 0
    skipped_count = 0

    for ans in stale_answers[:max_tasks]:
        existing = db.query(RevalidationTask).filter(
            RevalidationTask.answer_id == ans.id,
            RevalidationTask.status.in_(["pending", "in_progress"])
        ).first()
        if existing:
            skipped_count += 1
            continue

        priority = calculate_task_priority(ans)
        task = RevalidationTask(
            answer_id=ans.id,
            reason=f"Automated batch scheduling: impact score {ans.impact_score}",
            priority_score=priority["priority_score"],
            priority_level=priority["priority_level"],
        )
        db.add(task)
        created_count += 1

    db.commit()
    return {"evaluated_answers": len(stale_answers), "tasks_scheduled": created_count, "tasks_skipped": skipped_count}


def update_task_status(
    db: Session,
    task_id: str,
    new_status: str,
    resolver_notes: str = "",
    user_id: str = ""
) -> RevalidationTask:
    task = db.query(RevalidationTask).filter(RevalidationTask.id == task_id).first()
    if not task:
        raise ValueError(f"RevalidationTask {task_id} not found")

    valid_statuses = {"pending", "in_progress", "completed", "dismissed"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")

    task.status = new_status
    task.resolver_notes = resolver_notes
    if new_status == "completed":
        task.completed_at = datetime.now(timezone.utc)
        # Reset answer freshness on completion
        answer = db.query(RagAnswer).filter(RagAnswer.id == task.answer_id).first()
        if answer:
            answer.freshness_status = "fresh"
            answer.impact_score = 0.0

    db.commit()
    db.refresh(task)
    return task


def _spreadsheet_cell(value):
    """Keep untrusted text literal in spreadsheet exports, without mutating storage."""
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return value


def export_tasks_csv(
    db: Session,
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None
) -> str:
    query = db.query(RevalidationTask)

    if status_filter:
        query = query.filter(RevalidationTask.status == status_filter)
    if priority_filter:
        query = query.filter(RevalidationTask.priority_level == priority_filter)

    tasks = query.order_by(RevalidationTask.priority_score.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["task_id", "answer_id", "query_text", "status", "priority_score", "priority_level", "reason", "scheduled_at", "completed_at", "resolver_notes"])

    for task in tasks:
        # Get query_text from the associated answer
        answer = db.query(RagAnswer).filter(RagAnswer.id == task.answer_id).first()
        query_text = answer.query_text if answer else ""
        writer.writerow([
            _spreadsheet_cell(task.id),
            _spreadsheet_cell(task.answer_id),
            _spreadsheet_cell(query_text),
            _spreadsheet_cell(task.status),
            _spreadsheet_cell(task.priority_score),
            _spreadsheet_cell(task.priority_level),
            _spreadsheet_cell(task.reason),
            _spreadsheet_cell(task.scheduled_at.isoformat() if task.scheduled_at else ""),
            _spreadsheet_cell(task.completed_at.isoformat() if task.completed_at else ""),
            _spreadsheet_cell(task.resolver_notes),
        ])

    return output.getvalue()



"""Automated scheduler for periodic impact analysis and webhook dispatch."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.services.graph_engine import propagate_all_impacts, dispatch_webhook_notifications

logger = logging.getLogger(__name__)


class ImpactAnalysisScheduler:
    """Background scheduler for periodic impact analysis and webhook notifications."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def _run_impact_analysis(self) -> None:
        """Run a single impact analysis cycle and dispatch webhooks."""
        db: Session = SessionLocal()
        try:
            logger.info("Starting scheduled impact analysis")
            result = propagate_all_impacts(db)
            
            webhook_notifications = result.get("webhook_notifications", [])
            if webhook_notifications:
                logger.info(f"Dispatching {len(webhook_notifications)} webhook notifications")
                await dispatch_webhook_notifications(webhook_notifications)
            else:
                logger.debug("No critical_stale transitions detected, no webhooks dispatched")
                
            logger.info(
                "Scheduled impact analysis completed",
                extra={
                    "total_answers_evaluated": result.get("total_answers_evaluated", 0),
                    "impacted_answers_count": result.get("impacted_answers_count", 0),
                    "webhooks_dispatched": len(webhook_notifications),
                }
            )
        except Exception as e:
            logger.exception("Scheduled impact analysis failed", extra={"error": str(e)})
        finally:
            db.close()

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        self._running = True
        logger.info(f"Impact analysis scheduler started with interval {settings.SCHEDULER_INTERVAL_SECONDS}s")
        
        # Run once immediately on startup
        await self._run_impact_analysis()
        
        while self._running:
            try:
                await asyncio.sleep(settings.SCHEDULER_INTERVAL_SECONDS)
                if self._running:  # Check again after sleep
                    await self._run_impact_analysis()
            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.exception("Scheduler loop error", extra={"error": str(e)})
                # Continue running despite errors
                await asyncio.sleep(10)

    def start(self) -> None:
        """Start the scheduler background task."""
        if not settings.SCHEDULER_ENABLED:
            logger.info("Scheduler disabled via configuration")
            return
        if self._task is not None and not self._task.done():
            logger.warning("Scheduler already running")
            return
        self._task = asyncio.create_task(self._scheduler_loop())

    def stop(self) -> None:
        """Stop the scheduler background task."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            logger.info("Scheduler stop requested")


# Module-level instance
impact_scheduler = ImpactAnalysisScheduler()


@asynccontextmanager
async def lifespan_with_scheduler(app):
    """Extended lifespan that includes the scheduler."""
    # Startup
    impact_scheduler.start()
    try:
        yield
    finally:
        # Shutdown
        impact_scheduler.stop()
        if impact_scheduler._task is not None:
            try:
                await impact_scheduler._task
            except asyncio.CancelledError:
                pass
