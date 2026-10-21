"""Tests for webhook notification service."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.services.webhook_service import WebhookService, notify_critical_stale_transition
from backend.app.core.config import settings


def test_webhook_service_not_configured():
    """Webhook service should report not configured when URL is empty."""
    service = WebhookService()
    # Override settings
    original_url = settings.WEBHOOK_URL
    settings.WEBHOOK_URL = ""
    try:
        assert not service.is_configured()
    finally:
        settings.WEBHOOK_URL = original_url


def test_webhook_service_configured():
    """Webhook service should report configured when URL is set."""
    service = WebhookService()
    original_url = settings.WEBHOOK_URL
    original_secret = settings.WEBHOOK_SECRET
    settings.WEBHOOK_URL = "https://example.com/webhook"
    settings.WEBHOOK_SECRET = "test-secret"
    try:
        assert service.is_configured()
    finally:
        settings.WEBHOOK_URL = original_url
        settings.WEBHOOK_SECRET = original_secret


def test_generate_signature():
    """HMAC signature generation should produce consistent results."""
    service = WebhookService()
    original_secret = settings.WEBHOOK_SECRET
    settings.WEBHOOK_SECRET = "test-secret"
    try:
        payload = b'{"event_type":"test","data":{}}'
        sig1 = service._generate_signature(payload)
        sig2 = service._generate_signature(payload)
        assert sig1 == sig2
        assert len(sig1) == 64  # SHA256 hex length
    finally:
        settings.WEBHOOK_SECRET = original_secret


def test_generate_signature_empty_secret():
    """Empty secret should return empty signature."""
    service = WebhookService()
    original_secret = settings.WEBHOOK_SECRET
    settings.WEBHOOK_SECRET = ""
    try:
        payload = b'{"event_type":"test","data":{}}'
        sig = service._generate_signature(payload)
        assert sig == ""
    finally:
        settings.WEBHOOK_SECRET = original_secret


def test_build_payload():
    """Payload building should create standardized structure."""
    service = WebhookService()
    payload = service._build_payload("answer.critical_stale", {"answer_id": "ans_123"})
    assert payload["event_type"] == "answer.critical_stale"
    assert payload["data"]["answer_id"] == "ans_123"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_dispatch_skipped_when_not_configured():
    """Dispatch should return skipped when not configured."""
    service = WebhookService()
    original_url = settings.WEBHOOK_URL
    settings.WEBHOOK_URL = ""
    try:
        result = await service.dispatch("test.event", {"key": "value"})
        assert result["success"] is False
        assert result["skipped"] is True
        assert result["reason"] == "Webhook URL not configured"
        assert result["attempts"] == 0
    finally:
        settings.WEBHOOK_URL = original_url


@pytest.mark.asyncio
async def test_dispatch_success_with_mock():
    """Dispatch should succeed with mocked HTTP response."""
    service = WebhookService()
    original_url = settings.WEBHOOK_URL
    original_secret = settings.WEBHOOK_SECRET
    settings.WEBHOOK_URL = "https://example.com/webhook"
    settings.WEBHOOK_SECRET = "test-secret"
    try:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_response.elapsed.total_seconds.return_value = 0.05
            mock_post.return_value = mock_response

            result = await service.dispatch("test.event", {"key": "value"})

            assert result["success"] is True
            assert result["status_code"] == 200
            assert result["attempts"] == 1
            assert "response_time_ms" in result
            mock_post.assert_called_once()
    finally:
        settings.WEBHOOK_URL = original_url
        settings.WEBHOOK_SECRET = original_secret


@pytest.mark.asyncio
async def test_dispatch_retry_on_failure():
    """Dispatch should retry on failure with exponential backoff."""
    service = WebhookService()
    original_url = settings.WEBHOOK_URL
    original_secret = settings.WEBHOOK_SECRET
    original_max_retries = settings.WEBHOOK_MAX_RETRIES
    original_base_delay = settings.WEBHOOK_RETRY_BASE_DELAY_SECONDS
    settings.WEBHOOK_URL = "https://example.com/webhook"
    settings.WEBHOOK_SECRET = "test-secret"
    settings.WEBHOOK_MAX_RETRIES = 2
    settings.WEBHOOK_RETRY_BASE_DELAY_SECONDS = 0  # No delay for test
    try:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Network error")

            result = await service.dispatch("test.event", {"key": "value"})

            assert result["success"] is False
            assert result["skipped"] is False
            assert result["attempts"] == 3  # Initial + 2 retries
            assert mock_post.call_count == 3
    finally:
        settings.WEBHOOK_URL = original_url
        settings.WEBHOOK_SECRET = original_secret
        settings.WEBHOOK_MAX_RETRIES = original_max_retries
        settings.WEBHOOK_RETRY_BASE_DELAY_SECONDS = original_base_delay


@pytest.mark.asyncio
async def test_notify_critical_stale_transition():
    """notify_critical_stale_transition should call dispatch with correct data."""
    original_url = settings.WEBHOOK_URL
    settings.WEBHOOK_URL = "https://example.com/webhook"
    try:
        with patch("backend.app.services.webhook_service.webhook_service.dispatch", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = {"success": True, "attempts": 1}

            result = await notify_critical_stale_transition(
                answer_id="ans_123",
                query_text="Test query",
                prior_status="fresh",
                current_status="critical_stale",
                impact_score=0.85,
                stale_reasons=["Revision expired"],
                primary_citation_stale=True,
                affected_revisions=["rev_456"]
            )

            assert result["success"] is True
            mock_dispatch.assert_called_once()
            call_args = mock_dispatch.call_args
            assert call_args[0][0] == "answer.critical_stale"
            assert call_args[0][1]["answer_id"] == "ans_123"
            assert call_args[0][1]["impact_score"] == 0.85
            assert call_args[0][1]["primary_citation_stale"] is True
    finally:
        settings.WEBHOOK_URL = original_url