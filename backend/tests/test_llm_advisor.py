"""Tests for opt-in LLM advisory service, provider mocking, and credential redaction."""
import pytest
import httpx
from backend.app.core.config import settings
from backend.app.models.entities import RagAnswer
from backend.app.services.llm_advisor import generate_advisory_report, redact_sensitive_strings


@pytest.mark.asyncio
async def test_offline_deterministic_fallback_when_no_api_key(db_session, monkeypatch):
    """When LLM_API_KEY is not configured, the service returns grounded deterministic fallback."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "")

    ans = RagAnswer(
        id="ans_llm_1",
        query_text="What is the refund policy?",
        answer_text="Refunds are processed within 14 business days.",
        query_hash="hash_llm_1",
        freshness_status="stale",
        impact_score=0.45
    )
    ans.citations = []
    db_session.add(ans)
    db_session.commit()

    report = await generate_advisory_report(db=db_session, answer_id=ans.id)
    assert report["is_advisory"] is True
    assert report["provider_used"] == "offline-deterministic-engine"
    assert "MODERATE" in report["recommendation"]
    assert report["grounding_verified"] is True


@pytest.mark.asyncio
async def test_mocked_openai_compatible_provider(db_session, monkeypatch):
    """Network requests to LLM provider are mocked and return grounded advisory response."""
    # Build synthetic test credential at runtime (never a real or token-shaped literal)
    synthetic_key = "testkey_" + ("0" * 20)
    monkeypatch.setattr(settings, "LLM_API_KEY", synthetic_key)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai-compatible")

    ans = RagAnswer(
        id="ans_llm_2",
        query_text="What are the rate limit rules?",
        answer_text="Rate limit is 100 requests per minute.",
        query_hash="hash_llm_2",
        freshness_status="critical_stale",
        impact_score=0.85
    )
    ans.citations = []
    db_session.add(ans)
    db_session.commit()

    # Mock httpx AsyncClient post
    async def mock_post(self, url, *args, **kwargs):
        mock_data = {
            "choices": [
                {
                    "message": {
                        "content": "Advisory Analysis: Primary citation has drifted. Suggest regenerating answer with revised rates."
                    }
                }
            ]
        }
        req = httpx.Request("POST", url)
        return httpx.Response(200, json=mock_data, request=req)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    report = await generate_advisory_report(db=db_session, answer_id=ans.id)
    assert report["is_advisory"] is True
    assert report["provider_used"] == "openai-compatible"
    assert "Suggest regenerating answer" in report["raw_reasoning"]


def test_credential_redaction_utility():
    """Redaction utility strips token and key patterns from error messages."""
    # Generate synthetic sensitive error string at runtime
    fake_token = "Bearer test_bearer_token_" + ("a" * 16)
    fake_key_param = "?key=synthetic_key_" + ("9" * 16)
    raw_error = f"HTTP 401 unauthorized with header {fake_token} and url {fake_key_param}"

    sanitized = redact_sensitive_strings(raw_error)
    assert "synthetic_key" not in sanitized
    assert "[REDACTED_CREDENTIAL]" in sanitized or "[REDACTED_TOKEN]" in sanitized
