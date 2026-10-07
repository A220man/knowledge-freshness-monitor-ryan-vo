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
