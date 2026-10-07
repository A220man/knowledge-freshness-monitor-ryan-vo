"""RAG citation dependency mapping and impact analysis API."""
import hashlib
import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import require_viewer, require_analyst
from backend.app.models.entities import RagAnswer, CitationEdge, DocumentRevision, UserSession
from backend.app.models.schemas import (
    RagAnswerCreate,
    RagAnswerResponse,
    ImpactAnalysisResponse,
    AdvisoryReportRequest,
    AdvisoryReportResponse
)
from backend.app.services.graph_engine import (
    calculate_answer_impact,
    propagate_all_impacts,
    extract_citation_graph_data
)
from backend.app.services.llm_advisor import generate_advisory_report
from backend.app.services.audit_service import log_action

router = APIRouter(prefix="/api/citations", tags=["citations"])


@router.get("/answers", response_model=List[RagAnswerResponse])
def list_rag_answers(
    freshness_status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: UserSession = Depends(require_viewer),
    db: Session = Depends(get_db)
) -> List[RagAnswer]:
    query = db.query(RagAnswer)
    if freshness_status:
        query = query.filter(RagAnswer.freshness_status == freshness_status)
    return query.order_by(RagAnswer.impact_score.desc()).offset(offset).limit(limit).all()


@router.post("/answers", response_model=RagAnswerResponse, status_code=status.HTTP_201_CREATED)
def register_rag_answer(
    payload: RagAnswerCreate,
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> RagAnswer:
    q_hash = hashlib.sha256(payload.query_text.strip().lower().encode("utf-8")).hexdigest()
    answer = RagAnswer(
        query_text=payload.query_text, answer_text=payload.answer_text,
        query_hash=q_hash, freshness_status="fresh", impact_score=0.0
    )
    db.add(answer)
    db.flush()

    for cite in payload.citations:
        rev = db.query(DocumentRevision).filter(DocumentRevision.id == cite.revision_id).first()
        if not rev:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision {cite.revision_id} not found.")
        db.add(CitationEdge(
            answer_id=answer.id, revision_id=cite.revision_id, chunk_id=cite.chunk_id,
            citation_excerpt=cite.citation_excerpt, confidence_weight=cite.confidence_weight, is_primary=cite.is_primary
        ))

    db.commit()
    db.refresh(answer)

    eval_res = calculate_answer_impact(answer)
    answer.freshness_status = eval_res["freshness_status"]
    answer.impact_score = eval_res["impact_score"]
    db.commit()
    db.refresh(answer)

    log_action(db=db, user_id=session.user_id, action="citations.register", resource_type="rag_answer", resource_id=answer.id, details={})
    return answer


@router.get("/answers/{answer_id}", response_model=RagAnswerResponse)
def get_rag_answer(
    answer_id: str,
    session: UserSession = Depends(require_viewer),
    db: Session = Depends(get_db)
) -> RagAnswer:
    answer = db.query(RagAnswer).filter(RagAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG answer not found.")
    return answer


@router.post("/impact-analysis", response_model=ImpactAnalysisResponse)
def trigger_impact_analysis(
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> ImpactAnalysisResponse:
    t0 = time.perf_counter()
    res = propagate_all_impacts(db)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    return ImpactAnalysisResponse(
        analyzed_documents=res["analyzed_documents"],
        stale_or_expired_revisions=res["stale_or_expired_revisions"],
        total_answers_evaluated=res["total_answers_evaluated"],
        impacted_answers_count=res["impacted_answers_count"],
        impacted_answers=res["impacted_answers"],
        execution_time_ms=elapsed_ms
    )


@router.get("/graph", response_model=Dict[str, Any])
def get_citation_graph(
    session: UserSession = Depends(require_viewer),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    return extract_citation_graph_data(db)


@router.post("/answers/{answer_id}/advisory", response_model=AdvisoryReportResponse)
async def request_advisory_report(
    answer_id: str,
    payload: Optional[AdvisoryReportRequest] = None,
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> AdvisoryReportResponse:
    override = payload.provider_override if payload else None
    try:
        report = await generate_advisory_report(db=db, answer_id=answer_id, provider_override=override)
        return AdvisoryReportResponse(**report)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
