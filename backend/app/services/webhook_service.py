"""Webhook notification service with retry backoff and HMAC signature verification."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx
from backend.app.core.config import settings


class WebhookService:
    """Service for dispatching webhook notifications with retry logic and HMAC signing."""

    def _get_config(self):
        """Get current webhook configuration from settings."""
        return {
            "url": settings.WEBHOOK_URL,
            "secret": settings.WEBHOOK_SECRET,
            "max_retries": settings.WEBHOOK_MAX_RETRIES,
            "base_delay": settings.WEBHOOK_RETRY_BASE_DELAY_SECONDS,
            "timeout": settings.WEBHOOK_TIMEOUT_SECONDS,
        }

    def is_configured(self) -> bool:
        """Check if webhook is configured with a URL."""
        return bool(self._get_config()["url"] and self._get_config()["url"].strip())

    def _generate_signature(self, payload: bytes) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        secret = self._get_config()["secret"]
        if not secret:
            return ""
        return hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()

    def _build_payload(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build standardized webhook payload."""
        return {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }

    async def dispatch(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch webhook with exponential backoff retry.
        Returns dispatch result with success status and attempt details.
        """
        config = self._get_config()
        if not config["url"] or not config["url"].strip():
            return {
                "success": False,
                "skipped": True,
                "reason": "Webhook URL not configured",
                "attempts": 0
            }

        payload = self._build_payload(event_type, data)
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = self._generate_signature(payload_bytes)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "knowledge-freshness-monitor/1.0",
        }
        if signature:
            headers["X-Webhook-Signature"] = f"sha256={signature}"
            headers["X-Webhook-Timestamp"] = payload["timestamp"]

        last_error = None
        for attempt in range(config["max_retries"] + 1):
            try:
                async with httpx.AsyncClient(timeout=config["timeout"]) as client:
                    response = await client.post(
                        config["url"],
                        content=payload_bytes,
                        headers=headers
                    )
                    if 200 <= response.status_code < 300:
                        return {
                            "success": True,
                            "status_code": response.status_code,
                            "attempts": attempt + 1,
                            "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2)
                        }
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            except httpx.TimeoutException:
                last_error = f"Timeout after {config['timeout']}s"
            except httpx.RequestError as e:
                last_error = f"Request error: {type(e).__name__}"
            except Exception as e:
                last_error = f"Unexpected error: {type(e).__name__}"

            # Exponential backoff with jitter
            if attempt < config["max_retries"]:
                delay = config["base_delay"] * (2 ** attempt)
                await asyncio.sleep(delay)

        return {
            "success": False,
            "skipped": False,
            "reason": last_error or "Max retries exceeded",
            "attempts": config["max_retries"] + 1
        }


# Module-level instance
webhook_service = WebhookService()


async def notify_critical_stale_transition(
    answer_id: str,
    query_text: str,
    prior_status: str,
    current_status: str,
    impact_score: float,
    stale_reasons: list[str],
    primary_citation_stale: bool,
    affected_revisions: list[str]
) -> Dict[str, Any]:
    """
    Notify webhook when an answer transitions to critical_stale status.
    """
    data = {
        "answer_id": answer_id,
        "query_text": query_text,
        "prior_status": prior_status,
        "current_status": current_status,
        "impact_score": impact_score,
        "stale_reasons": stale_reasons,
        "primary_citation_stale": primary_citation_stale,
        "affected_revisions": affected_revisions
    }
    return await webhook_service.dispatch("answer.critical_stale", data)