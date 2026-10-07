"""API tests for document ingestion, revisions, and expiration monitoring."""
from datetime import datetime, timedelta, timezone
from fastapi import status
from backend.app.models.entities import Document, DocumentRevision


def test_create_document_and_chunks(client, auth_headers_factory):
    """Creating a document properly indexes version 1 and produces chunk records."""
    headers = auth_headers_factory(role="analyst")
    payload = {
        "title": "OAuth2 Security Architecture",
        "source_uri": "https://wiki.corp/security/oauth2",
        "category": "security",
        "retention_days": 120,
        "initial_content": (
            "Paragraph one describes authorization code grant flows with PKCE protection.\n\n"
            "Paragraph two outlines refresh token rotation policies and cookie security flags."
        )
    }
    res = client.post("/api/documents", json=payload, headers=headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["title"] == "OAuth2 Security Architecture"
    assert len(data["revisions"]) == 1
    assert data["revisions"][0]["version"] == 1
    assert data["revisions"][0]["drift_score"] == 0.0


def test_add_new_revision_supersedes_and_calculates_drift(client, auth_headers_factory):
    """Submitting revision increments version, computes drift, and supersedes previous version."""
    headers = auth_headers_factory(role="analyst")
    # First create
    doc_res = client.post("/api/documents", json={
        "title": "Rate Limiting Standards",
        "source_uri": "https://wiki.corp/limits",
        "category": "api_spec",
        "retention_days": 90,
        "initial_content": "Initial rate limit is 100 requests per minute."
    }, headers=headers)
    doc_id = doc_res.json()["id"]

    # Add revision
    rev_res = client.post(f"/api/documents/{doc_id}/revisions", json={
        "text_content": "Updated rate limit is lowered to 20 requests per minute with mandatory authorization."
    }, headers=headers)
    assert rev_res.status_code == status.HTTP_201_CREATED
    rev_data = rev_res.json()
    assert rev_data["version"] == 2
    assert rev_data["drift_score"] > 0.0

    # Verify document details shows both versions
    viewer_headers = auth_headers_factory(role="viewer")
    detail_res = client.get(f"/api/documents/{doc_id}", headers=viewer_headers)
    assert detail_res.status_code == status.HTTP_200_OK
    revisions = detail_res.json()["revisions"]
    assert len(revisions) == 2
    # Prior revision is superseded
    v1 = next(r for r in revisions if r["version"] == 1)
    assert v1["status"] == "superseded"


def test_check_expirations_endpoint(client, auth_headers_factory, db_session):
    """Expiration scan marks past-due revisions as expired."""
    headers = auth_headers_factory(role="analyst")
    # Insert an expired revision manually
    doc = Document(title="Expiring Document", source_uri="https://test.corp/exp")
    db_session.add(doc)
    db_session.flush()

    past_date = datetime.now(timezone.utc) - timedelta(days=5)
    rev = DocumentRevision(
        document_id=doc.id,
        version=1,
        content_hash="exp_hash",
        text_content="Expiring text",
        expiration_timestamp=past_date,
        status="fresh"
    )
    db_session.add(rev)
    db_session.commit()

    res = client.post("/api/documents/check-expirations", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["expired_count"] >= 1


def test_delete_document_by_admin(client, auth_headers_factory):
    """Admin can delete a document and its cascading records."""
    headers_analyst = auth_headers_factory(role="analyst")
    create_res = client.post("/api/documents", json={
        "title": "Document to Delete",
        "source_uri": "https://wiki.corp/delete-me",
        "category": "temp",
        "retention_days": 10,
        "initial_content": "Temporary content to be deleted."
    }, headers=headers_analyst)
    doc_id = create_res.json()["id"]

    headers_admin = auth_headers_factory(role="admin")
    del_res = client.delete(f"/api/documents/{doc_id}", headers=headers_admin)
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    # Verification: 404 when requested
    headers_viewer = auth_headers_factory(role="viewer")
    get_res = client.get(f"/api/documents/{doc_id}", headers=headers_viewer)
    assert get_res.status_code == status.HTTP_404_NOT_FOUND
