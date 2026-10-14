"""API tests for RAG citation mapping and impact analysis."""
from fastapi import status
from backend.app.models.entities import Document, DocumentRevision


def test_register_rag_answer_and_citations(client, auth_headers_factory, db_session):
    """Registers a generated RAG answer and binds citation dependencies."""
    headers = auth_headers_factory(role="analyst")

    # Seed document & revision
    doc = Document(title="Architecture Spec", source_uri="https://wiki.corp/arch")
    db_session.add(doc)
    db_session.flush()

    rev = DocumentRevision(
        document_id=doc.id,
        version=1,
        content_hash="arch_hash",
        text_content="Microservices use gRPC for internal RPC.",
        status="fresh"
    )
    db_session.add(rev)
    db_session.commit()

    payload = {
        "query_text": "What protocol do internal microservices use?",
        "answer_text": "Internal microservices communicate via gRPC according to Architecture Spec.",
        "citations": [
            {
                "revision_id": rev.id,
                "citation_excerpt": "Microservices use gRPC for internal RPC.",
                "confidence_weight": 0.95,
                "is_primary": True
            }
        ]
    }
    res = client.post("/api/citations/answers", json=payload, headers=headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["freshness_status"] == "fresh"
    assert len(data["citations"]) == 1
    assert data["citations"][0]["revision_id"] == rev.id


def test_trigger_impact_analysis_endpoint(client, auth_headers_factory):
    """Triggering impact analysis propagates freshness scores across the graph."""
    headers = auth_headers_factory(role="analyst")
    res = client.post("/api/citations/impact-analysis", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "analyzed_documents" in data
    assert "execution_time_ms" in data
    assert isinstance(data["impacted_answers"], list)


def test_get_citation_graph_endpoint(client, auth_headers_factory):
    """Retrieves full citation topology for visualization."""
    headers = auth_headers_factory(role="viewer")
    res = client.get("/api/citations/graph", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "nodes" in data
    assert "links" in data
    assert "summary" in data
    assert "clusters" in data


def test_citation_graph_filter_query_and_validation(client, auth_headers_factory, db_session):
    """HTTP graph reads honor domain, impact, and recency filters and reject bad bounds."""
    headers = auth_headers_factory(role="viewer")
    doc = Document(title="Policy Handbook", source_uri="https://wiki.example/policy", category="policy")
    other = Document(title="Ops Notes", source_uri="https://wiki.example/ops", category="operations")
    db_session.add_all([doc, other])
    db_session.flush()
    rev = DocumentRevision(
        document_id=doc.id, version=1, content_hash="p", text_content="90 days",
        status="stale", drift_score=0.9
    )
    other_rev = DocumentRevision(document_id=other.id, version=1, content_hash="o", text_content="restart", status="fresh")
    db_session.add_all([rev, other_rev])
    db_session.commit()

    analyst = auth_headers_factory(role="analyst")
    created = client.post("/api/citations/answers", headers=analyst, json={
        "query_text": "What is the retention window?",
        "answer_text": "Records stay for 90 days.",
        "citations": [{"revision_id": rev.id, "citation_excerpt": "90 days", "confidence_weight": 0.9, "is_primary": True}],
    })
    assert created.status_code == status.HTTP_201_CREATED
    answer_id = created.json()["id"]
    assert created.json()["impact_score"] >= 0.25

    filtered = client.get(
        "/api/citations/graph",
        headers=headers,
        params={"domain": "policy", "min_impact": 0.25, "recency_days": 30},
    )
    assert filtered.status_code == status.HTTP_200_OK
    body = filtered.json()
    assert body["summary"]["filters"]["domain"] == "policy"
    assert body["summary"]["total_documents"] == 1
    assert any(node["id"] == f"ans_{answer_id}" for node in body["nodes"])
    assert all(node["category"] != "operations" for node in body["nodes"] if node["type"] == "document")
    assert body["summary"]["cluster_count"] >= 1

    hidden = client.get("/api/citations/graph", headers=headers, params={"domain": "operations", "min_impact": 0.7})
    assert hidden.status_code == status.HTTP_200_OK
    assert hidden.json()["nodes"] == []

    assert client.get("/api/citations/graph", headers=headers, params={"min_impact": 1.5}).status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert client.get("/api/citations/graph", headers=headers, params={"recency_days": 0}).status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
