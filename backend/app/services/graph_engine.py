from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models.entities import Document, DocumentRevision, RagAnswer, CitationEdge
from backend.app.services.webhook_service import notify_critical_stale_transition

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

            # Dispatch webhook if transitioned to critical_stale
            if prior_status != "critical_stale" and ans.freshness_status == "critical_stale":
                # Use a background task to avoid blocking the API response
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(notify_critical_stale_transition(
                        answer_id=ans.id,
                        query_text=ans.query_text,
                        prior_status=prior_status,
                        current_status=ans.freshness_status,
                        impact_score=ans.impact_score,
                        stale_reasons=eval_result["stale_reasons"],
                        primary_citation_stale=eval_result["primary_citation_stale"],
                        affected_revisions=eval_result["affected_revisions"]
                    ))
                except RuntimeError:
                    # No running event loop, run in a new loop
                    asyncio.run(notify_critical_stale_transition(
                        answer_id=ans.id,
                        query_text=ans.query_text,
                        prior_status=prior_status,
                        current_status=ans.freshness_status,
                        impact_score=ans.impact_score,
                        stale_reasons=eval_result["stale_reasons"],
                        primary_citation_stale=eval_result["primary_citation_stale"],
                        affected_revisions=eval_result["affected_revisions"]
                    ))

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


def _utc(value: Optional[datetime], fallback: datetime) -> datetime:
    if value is None:
        return fallback
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def extract_citation_graph_data(
    db: Session, domain: Optional[str] = None, min_impact: Optional[float] = None,
    recency_days: Optional[int] = None, now: Optional[datetime] = None,
) -> Dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    domain_key = (domain or "").strip().lower() or None
    documents, revisions = db.query(Document).all(), db.query(DocumentRevision).all()
    answers, edges = db.query(RagAnswer).all(), db.query(CitationEdge).all()
    rev_by_id = {item.id: item for item in revisions}
    ans_by_id = {item.id: item for item in answers}
    allowed = {item.id for item in documents if domain_key is None or (item.category or "").strip().lower() == domain_key}
    cutoff = moment - timedelta(days=recency_days) if recency_days else None

    def keep(answer: RagAnswer) -> bool:
        if min_impact is not None and float(answer.impact_score or 0.0) < min_impact:
            return False
        return cutoff is None or _utc(answer.created_at, moment) >= cutoff

    filtering = domain_key is not None or min_impact is not None or cutoff is not None
    kept = [e for e in edges if (a := ans_by_id.get(e.answer_id)) and (r := rev_by_id.get(e.revision_id)) and r.document_id in allowed and keep(a)]
    if filtering:
        answer_ids = {e.answer_id for e in kept}
        if domain_key is None:
            answer_ids.update(item.id for item in answers if keep(item))
        rev_ids = {e.revision_id for e in kept if e.answer_id in answer_ids}
        doc_ids = {rev_by_id[rid].document_id for rid in rev_ids}
    else:
        kept, answer_ids, rev_ids = list(edges), set(ans_by_id), set(rev_by_id)
        doc_ids = {item.id for item in documents}
    selected_docs = [item for item in documents if item.id in doc_ids]
    selected_revs = [item for item in revisions if item.id in rev_ids and item.document_id in doc_ids]
    selected_answers = [item for item in answers if item.id in answer_ids]
    parent: Dict[str, str] = {}

    def find(node_id: str) -> str:
        parent.setdefault(node_id, node_id)
        root = node_id
        while parent[root] != root:
            root = parent[root]
        parent[node_id] = root
        return root

    def unite(left: str, right: str) -> None:
        ra, rb = find(left), find(right)
        if ra != rb:
            parent[rb] = ra

    for rev in selected_revs:
        unite(f"doc_{rev.document_id}", f"rev_{rev.id}")
    for edge in kept:
        if edge.answer_id in answer_ids and edge.revision_id in rev_ids:
            unite(f"ans_{edge.answer_id}", f"rev_{edge.revision_id}")
    for doc in selected_docs:
        find(f"doc_{doc.id}")
    for answer in selected_answers:
        find(f"ans_{answer.id}")
    nodes: List[Dict[str, Any]] = [
        {"id": f"doc_{d.id}", "type": "document", "label": d.title, "category": d.category, "status": "active"}
        for d in selected_docs
    ]
    nodes.extend(
        {"id": f"rev_{r.id}", "type": "revision", "label": f"v{r.version} ({r.status})", "status": r.status,
         "drift_score": r.drift_score, "parent_doc_id": f"doc_{r.document_id}"}
        for r in selected_revs
    )
    nodes.extend(
        {"id": f"ans_{a.id}", "type": "answer", "label": (a.query_text or "")[:35] + ("..." if len(a.query_text or "") > 35 else ""),
         "status": a.freshness_status, "impact_score": a.impact_score}
        for a in selected_answers
    )
    groups: Dict[str, List[str]] = {}
    for node in nodes:
        groups.setdefault(find(node["id"]), []).append(node["id"])
    impact_of = {f"ans_{a.id}": float(a.impact_score or 0.0) for a in selected_answers}
    domain_of = {f"doc_{d.id}": d.category for d in selected_docs}
    clusters = []
    for root, members in groups.items():
        scores = [impact_of[mid] for mid in members if mid in impact_of]
        clusters.append({
            "id": root, "node_ids": members,
            "max_impact": round(max(scores) if scores else 0.0, 4),
            "domains": sorted({domain_of[mid] for mid in members if domain_of.get(mid)}),
            "answer_count": sum(mid.startswith("ans_") for mid in members),
        })
    clusters.sort(key=lambda item: (-item["max_impact"], item["id"]))
    owned = {nid: cluster["id"] for cluster in clusters for nid in cluster["node_ids"]}
    for node in nodes:
        node["cluster_id"] = owned[node["id"]]
    links = [{"source": f"doc_{r.document_id}", "target": f"rev_{r.id}", "type": "has_revision", "weight": 1.0} for r in selected_revs]
    links.extend(
        {"source": f"ans_{e.answer_id}", "target": f"rev_{e.revision_id}", "type": "cites", "is_primary": e.is_primary, "weight": e.confidence_weight}
        for e in kept if e.answer_id in answer_ids and e.revision_id in rev_ids
    )
    return {
        "nodes": nodes, "links": links, "clusters": clusters,
        "summary": {
            "total_documents": len(selected_docs), "total_revisions": len(selected_revs),
            "total_answers": len(selected_answers), "total_citations": sum(link["type"] == "cites" for link in links),
            "cluster_count": len(clusters),
            "filters": {"domain": domain_key, "min_impact": min_impact, "recency_days": recency_days},
        },
    }
