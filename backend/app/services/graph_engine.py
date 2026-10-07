"""Citation dependency graph engine and impact propagation algorithms."""
from datetime import datetime, timezone
from typing import Dict, List, Set, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models.entities import Document, DocumentRevision, DocumentChunk, RagAnswer, CitationEdge


def evaluate_revision_freshness_status(revision: DocumentRevision, now: Optional[datetime] = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    if revision.status == "superseded":
        return "superseded"
    if revision.expiration_timestamp:
        exp_ts = revision.expiration_timestamp
        if exp_ts.tzinfo is None:
            exp_ts = exp_ts.replace(tzinfo=timezone.utc)
        if now >= exp_ts:
            return "expired"
    if revision.drift_score >= 0.35:
        return "stale"
    return "fresh"


def calculate_answer_impact(answer: RagAnswer, now: Optional[datetime] = None) -> Dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)
    if not answer.citations:
        return {
            "impact_score": 0.0,
            "freshness_status": "fresh",
            "primary_citation_stale": False,
            "stale_reasons": ["No citations linked."],
            "affected_revisions": []
        }

    stale_reasons: List[str] = []
    affected_revisions: List[str] = []
    has_expired_citation = False
    has_superseded_citation = False
    primary_citation_compromised = False
    edge_impact_scores: List[float] = []

    for edge in answer.citations:
        rev = edge.revision
        if not rev:
            continue
        rev_status = evaluate_revision_freshness_status(rev, now)
        is_compromised = rev_status in {"expired", "superseded", "stale"}
        edge_severity = 0.0
        if rev_status == "expired":
            has_expired_citation = True
            edge_severity = 1.0
            stale_reasons.append(f"Citation references expired revision v{rev.version}")
            affected_revisions.append(rev.id)
        elif rev_status == "superseded":
            has_superseded_citation = True
            edge_severity = 0.90
            stale_reasons.append(f"Citation references superseded revision v{rev.version}")
            affected_revisions.append(rev.id)
        elif rev_status == "stale":
            edge_severity = min(1.0, 0.40 + rev.drift_score * 0.60)
            stale_reasons.append(f"Citation revision v{rev.version} drift ({rev.drift_score:.2f})")
            affected_revisions.append(rev.id)

        role_multiplier = 1.0 if edge.is_primary else 0.45
        confidence = max(0.2, min(1.0, edge.confidence_weight))
        effective_edge_impact = edge_severity * role_multiplier * confidence
        edge_impact_scores.append(effective_edge_impact)

        if edge.is_primary and is_compromised:
            primary_citation_compromised = True

    if not edge_impact_scores:
        overall_score = 0.0
    else:
        max_edge = max(edge_impact_scores)
        avg_edge = sum(edge_impact_scores) / len(edge_impact_scores)
        overall_score = (0.70 * max_edge) + (0.30 * avg_edge)

    if primary_citation_compromised:
        overall_score = max(overall_score, 0.75)
    if has_expired_citation and primary_citation_compromised:
        overall_score = max(overall_score, 0.90)

    overall_score = round(max(0.0, min(1.0, overall_score)), 4)
    if overall_score >= 0.70 or (primary_citation_compromised and (has_expired_citation or has_superseded_citation)):
        status_label = "critical_stale"
    elif overall_score >= 0.25:
        status_label = "stale"
    else:
        status_label = "fresh"

    return {
        "impact_score": overall_score,
        "freshness_status": status_label,
        "primary_citation_stale": primary_citation_compromised,
        "stale_reasons": stale_reasons,
        "affected_revisions": list(set(affected_revisions))
    }


def propagate_all_impacts(db: Session) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    answers = db.query(RagAnswer).all()
    impacted_items: List[Dict[str, Any]] = []

    for ans in answers:
        prior_status = ans.freshness_status
        eval_result = calculate_answer_impact(ans, now)
        ans.impact_score = eval_result["impact_score"]
        ans.freshness_status = eval_result["freshness_status"]

        if ans.freshness_status in {"stale", "critical_stale"}:
            impacted_items.append({
                "answer_id": ans.id,
                "query_text": ans.query_text,
                "prior_status": prior_status,
                "current_status": ans.freshness_status,
                "impact_score": ans.impact_score,
                "stale_reasons": eval_result["stale_reasons"],
                "primary_citation_stale": eval_result["primary_citation_stale"],
                "affected_revisions": eval_result["affected_revisions"]
            })

    db.commit()
    docs_count = db.query(Document).count()
    stale_rev_count = db.query(DocumentRevision).filter(
        DocumentRevision.status.in_(["stale", "expired", "superseded"])
    ).count()

    return {
        "analyzed_documents": docs_count,
        "stale_or_expired_revisions": stale_rev_count,
        "total_answers_evaluated": len(answers),
        "impacted_answers_count": len(impacted_items),
        "impacted_answers": impacted_items
    }


def extract_citation_graph_data(db: Session) -> Dict[str, Any]:
    documents = db.query(Document).all()
    revisions = db.query(DocumentRevision).all()
    answers = db.query(RagAnswer).all()
    edges = db.query(CitationEdge).all()

    nodes = [
        {"id": f"doc_{d.id}", "type": "document", "label": d.title, "category": d.category, "status": "active"}
        for d in documents
    ]
    for r in revisions:
        nodes.append({
            "id": f"rev_{r.id}", "type": "revision", "label": f"v{r.version} ({r.status})",
            "status": r.status, "drift_score": r.drift_score, "parent_doc_id": f"doc_{r.document_id}"
        })
    for a in answers:
        nodes.append({
            "id": f"ans_{a.id}", "type": "answer",
            "label": a.query_text[:35] + ("..." if len(a.query_text) > 35 else ""),
            "status": a.freshness_status, "impact_score": a.impact_score
        })

    links = [{"source": f"doc_{r.document_id}", "target": f"rev_{r.id}", "type": "has_revision", "weight": 1.0} for r in revisions]
    for e in edges:
        links.append({
            "source": f"ans_{e.answer_id}", "target": f"rev_{e.revision_id}",
            "type": "cites", "is_primary": e.is_primary, "weight": e.confidence_weight
        })

    return {
        "nodes": nodes,
        "links": links,
        "summary": {
            "total_documents": len(documents),
            "total_revisions": len(revisions),
            "total_answers": len(answers),
            "total_citations": len(edges)
        }
    }
