"""Tests for citation dependency graph engine and impact propagation."""
from datetime import datetime, timedelta, timezone
from backend.app.models.entities import Document, DocumentRevision, RagAnswer, CitationEdge
from backend.app.services.graph_engine import (
    calculate_answer_impact,
    propagate_all_impacts,
    extract_citation_graph_data
)


def test_fresh_citation_impact():
    """An answer whose citations are all fresh and unexpired has 0.0 impact and fresh status."""
    rev = DocumentRevision(
        id="rev_fresh_1",
        document_id="doc_1",
        version=1,
        content_hash="hash1",
        text_content="Clean document content.",
        drift_score=0.0,
        expiration_timestamp=datetime.now(timezone.utc) + timedelta(days=60),
        status="fresh"
    )
    ans = RagAnswer(
        id="ans_1",
        query_text="What is clean content?",
        answer_text="Clean document content is verified.",
        query_hash="qhash1"
    )
    edge = CitationEdge(
        answer_id=ans.id,
        revision_id=rev.id,
        confidence_weight=1.0,
        is_primary=True
    )
    ans.citations = [edge]
    edge.revision = rev

    impact_res = calculate_answer_impact(ans)
    assert impact_res["impact_score"] == 0.0
    assert impact_res["freshness_status"] == "fresh"
    assert impact_res["primary_citation_stale"] is False


def test_expired_primary_citation_triggers_critical_stale():
    """An answer with an expired primary citation is marked critical_stale with impact >= 0.75."""
    rev_expired = DocumentRevision(
        id="rev_exp_1",
        document_id="doc_2",
        version=1,
        content_hash="hash2",
        text_content="Expired compliance rules.",
        drift_score=0.0,
        expiration_timestamp=datetime.now(timezone.utc) - timedelta(days=2),
        status="expired"
    )
    ans = RagAnswer(
        id="ans_2",
        query_text="What are current compliance rules?",
        answer_text="Rules are derived from expired doc.",
        query_hash="qhash2"
    )
    edge = CitationEdge(
        answer_id=ans.id,
        revision_id=rev_expired.id,
        confidence_weight=1.0,
        is_primary=True
    )
    ans.citations = [edge]
    edge.revision = rev_expired

    impact_res = calculate_answer_impact(ans)
    assert impact_res["freshness_status"] == "critical_stale"
    assert impact_res["impact_score"] >= 0.75
    assert impact_res["primary_citation_stale"] is True


def test_superseded_citation_escalation():
    """An answer referencing a superseded revision has elevated impact score and stale status."""
    rev_superseded = DocumentRevision(
        id="rev_sup_1",
        document_id="doc_3",
        version=1,
        content_hash="hash3",
        text_content="Old outdated policy.",
        drift_score=0.0,
        expiration_timestamp=datetime.now(timezone.utc) + timedelta(days=30),
        status="superseded"
    )
    ans = RagAnswer(
        id="ans_3",
        query_text="Explain old policy",
        answer_text="Explanation",
        query_hash="qhash3"
    )
    edge = CitationEdge(
        answer_id=ans.id,
        revision_id=rev_superseded.id,
        confidence_weight=0.8,
        is_primary=True
    )
    ans.citations = [edge]
    edge.revision = rev_superseded

    impact_res = calculate_answer_impact(ans)
    assert impact_res["freshness_status"] in {"stale", "critical_stale"}
    assert impact_res["impact_score"] >= 0.5


def test_secondary_citation_low_severity():
    """Compromised secondary citation results in moderate impact without forcing critical status."""
    rev_secondary = DocumentRevision(
        id="rev_sec_1",
        document_id="doc_4",
        version=1,
        content_hash="hash4",
        text_content="Secondary footnote info.",
        drift_score=0.4,
        expiration_timestamp=datetime.now(timezone.utc) + timedelta(days=30),
        status="stale"
    )
    ans = RagAnswer(
        id="ans_4",
        query_text="Footnote query",
        answer_text="Answer with secondary cite",
        query_hash="qhash4"
    )
    edge = CitationEdge(
        answer_id=ans.id,
        revision_id=rev_secondary.id,
        confidence_weight=0.5,
        is_primary=False  # Secondary
    )
    ans.citations = [edge]
    edge.revision = rev_secondary

    impact_res = calculate_answer_impact(ans)
    assert impact_res["primary_citation_stale"] is False
    assert impact_res["freshness_status"] != "critical_stale"


def test_graph_data_extraction_topology(db_session):
    """Citation graph node-link extraction structures documents, revisions, answers, and edges."""
    doc = Document(id="d1", title="Doc 1", source_uri="uri1")
    rev = DocumentRevision(id="r1", document_id="d1", version=1, content_hash="h1", text_content="c1", status="fresh")
    ans = RagAnswer(id="a1", query_text="Q1", answer_text="A1", query_hash="qh1")
    edge = CitationEdge(id="e1", answer_id="a1", revision_id="r1", is_primary=True)

    db_session.add_all([doc, rev, ans, edge])
    db_session.commit()

    graph = extract_citation_graph_data(db_session)
    assert len(graph["nodes"]) == 3
    assert len(graph["links"]) == 2  # doc->rev and ans->rev
    assert graph["summary"]["cluster_count"] == 1


def test_subgraph_filters_domain_impact_recency_and_clusters(db_session):
    """Domain, impact, and recency filters keep only the matching connected clusters."""
    now = datetime.now(timezone.utc)
    policy = Document(id="doc_policy", title="Retention Policy", source_uri="uri://policy", category="Policy")
    ops = Document(id="doc_ops", title="Ops Runbook", source_uri="uri://ops", category="operations")
    policy_rev = DocumentRevision(
        id="rev_policy", document_id="doc_policy", version=2, content_hash="ph",
        text_content="Retain records for 90 days.", status="expired", drift_score=0.8
    )
    ops_rev = DocumentRevision(
        id="rev_ops", document_id="doc_ops", version=1, content_hash="oh",
        text_content="Restart the worker.", status="fresh", drift_score=0.0
    )
    recent_policy = RagAnswer(
        id="ans_policy", query_text="How long is retention?", answer_text="90 days",
        query_hash="qp", impact_score=0.91, freshness_status="critical_stale", created_at=now - timedelta(days=2)
    )
    recent_ops = RagAnswer(
        id="ans_ops", query_text="How do I restart workers?", answer_text="Restart them.",
        query_hash="qo", impact_score=0.91, freshness_status="critical_stale", created_at=now - timedelta(days=1)
    )
    old_policy = RagAnswer(
        id="ans_old", query_text="Old retention question", answer_text="stale copy",
        query_hash="qold", impact_score=0.8, freshness_status="stale", created_at=now - timedelta(days=40)
    )
    low_policy = RagAnswer(
        id="ans_low", query_text="Minor policy note", answer_text="still current",
        query_hash="qlow", impact_score=0.1, freshness_status="fresh", created_at=now - timedelta(days=1)
    )
    edges = [
        CitationEdge(id="e1", answer_id="ans_policy", revision_id="rev_policy", is_primary=True, confidence_weight=0.9),
        CitationEdge(id="e2", answer_id="ans_ops", revision_id="rev_ops", is_primary=True, confidence_weight=0.9),
        CitationEdge(id="e3", answer_id="ans_old", revision_id="rev_policy", is_primary=False, confidence_weight=0.4),
        CitationEdge(id="e4", answer_id="ans_low", revision_id="rev_policy", is_primary=False, confidence_weight=0.3),
    ]
    db_session.add_all([policy, ops, policy_rev, ops_rev, recent_policy, recent_ops, old_policy, low_policy, *edges])
    db_session.commit()

    scoped = extract_citation_graph_data(
        db_session, domain=" policy ", min_impact=0.7, recency_days=30, now=now
    )
    node_ids = {node["id"] for node in scoped["nodes"]}
    assert node_ids == {"doc_doc_policy", "rev_rev_policy", "ans_ans_policy"}
    assert scoped["summary"]["cluster_count"] == 1
    assert scoped["summary"]["filters"]["domain"] == "policy"
    assert scoped["clusters"][0]["domains"] == ["Policy"]
    assert scoped["clusters"][0]["max_impact"] == 0.91
    assert {link["type"] for link in scoped["links"]} == {"has_revision", "cites"}

    split = extract_citation_graph_data(db_session, min_impact=0.7, recency_days=7, now=now)
    assert split["summary"]["cluster_count"] == 2
    assert split["summary"]["total_answers"] == 2
    assert {node["cluster_id"] for node in split["nodes"] if node["type"] == "answer"} == {
        cluster["id"] for cluster in split["clusters"]
    }
