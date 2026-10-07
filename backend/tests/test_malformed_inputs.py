"""Tests for malformed inputs, boundary conditions, and validation errors."""
from fastapi import status


def test_malformed_document_creation(client, auth_headers_factory):
    """Payloads failing validation are rejected with 422 Unprocessable Entity."""
    headers = auth_headers_factory(role="analyst")
    # Title too short, invalid retention days
    payload = {
        "title": "A",
        "source_uri": "invalid",
        "category": "test",
        "retention_days": -5,
        "initial_content": "Too short"
    }
    res = client.post("/api/documents", json=payload, headers=headers)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_malformed_revision_creation(client, auth_headers_factory):
    """Empty or too short revision content is rejected with 422."""
    headers = auth_headers_factory(role="analyst")
    res = client.post("/api/documents/non_existent_doc/revisions", json={"text_content": "short"}, headers=headers)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_nonexistent_document_revision_404(client, auth_headers_factory):
    """Submitting a valid revision payload to non-existent document yields 404."""
    headers = auth_headers_factory(role="analyst")
    res = client.post(
        "/api/documents/non_existent_doc/revisions",
        json={"text_content": "Valid long enough revision content to pass validation."},
        headers=headers
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_malformed_task_status_transition(client, auth_headers_factory):
    """Invalid task status values are rejected with 422."""
    headers = auth_headers_factory(role="analyst")
    res = client.patch(
        "/api/revalidation/tasks/dummy_task_id",
        json={"status": "invalid_unsupported_state"},
        headers=headers
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
