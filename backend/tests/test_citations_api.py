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
