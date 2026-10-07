"""Authentication and authorization role-based security tests."""
import pytest
from fastapi import status
from backend.app.core.config import Settings, settings


def test_unauthenticated_request_rejected(client):
    """Endpoints requiring authentication must reject unauthenticated requests with 401."""
    res = client.get("/api/documents")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Authentication required" in res.json()["detail"]


def test_viewer_role_denied_analyst_action(client, auth_headers_factory):
    """Viewers must be denied access to mutating analyst endpoints with 403."""
    headers = auth_headers_factory(role="viewer")
    payload = {
        "title": "Unauthorized Document Creation",
        "source_uri": "https://example.com/doc",
        "category": "policy",
        "retention_days": 30,
        "initial_content": "This content should not be written by a viewer."
    }
    res = client.post("/api/documents", json=payload, headers=headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "Access denied" in res.json()["detail"]


def test_analyst_role_denied_admin_action(client, auth_headers_factory):
    """Analysts must be denied access to admin-only destructive endpoints with 403."""
    headers = auth_headers_factory(role="analyst")
    res = client.delete("/api/documents/non_existent_doc_id", headers=headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "Access denied" in res.json()["detail"]


def test_demo_login_success_in_development(client):
    """Demo login succeeds in development mode and sets session cookie."""
    res = client.post("/api/auth/demo-login", json={"role": "analyst", "username": "analyst_tester"})
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["role"] == "analyst"
    assert data["username"] == "analyst_tester"
    assert "kfm_session" in res.cookies


def test_demo_login_refused_in_production(client, monkeypatch):
    """Demo login is strictly rejected with 403 when ENVIRONMENT is production."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    res = client.post("/api/auth/demo-login", json={"role": "analyst"})
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "strictly disabled in production" in res.json()["detail"]


def test_production_startup_guards_raise():
    """Startup validation refuses production mode when demo auth is active."""
    prod_settings = Settings(ENVIRONMENT="production", AUTH_METHOD="demo")
    with pytest.raises(RuntimeError) as exc_info:
        prod_settings.validate_production_guards()
    assert "Local demo authentication is strictly forbidden in production" in str(exc_info.value)


def test_logout_terminates_session(client, auth_headers_factory):
    """Logout invalidates active server session and returns success."""
    headers = auth_headers_factory(role="analyst")
    res = client.post("/api/auth/logout", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "logged_out"

    # Subsequent request using same token should be rejected
    res2 = client.get("/api/auth/me", headers=headers)
    assert res2.status_code == status.HTTP_401_UNAUTHORIZED
