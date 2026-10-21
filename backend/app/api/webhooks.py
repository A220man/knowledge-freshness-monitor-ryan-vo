"""Webhook configuration and test endpoints."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.core.security import require_admin
from backend.app.models.entities import UserSession
from backend.app.core.database import get_db
from sqlalchemy.orm import Session
from backend.app.services.webhook_service import webhook_service

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WebhookConfigResponse(BaseModel):
    configured: bool
    url: str
    max_retries: int
    retry_base_delay_seconds: int
    timeout_seconds: int
    has_secret: bool


class WebhookTestRequest(BaseModel):
    test_event_type: str = "test.notification"


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int = 0
    attempts: int
    reason: str = ""


@router.get("/config", response_model=WebhookConfigResponse)
def get_webhook_config(
    session: UserSession = Depends(require_admin),
    db: Session = Depends(get_db)
) -> WebhookConfigResponse:
    """Get webhook configuration status (admin only)."""
    return WebhookConfigResponse(
        configured=webhook_service.is_configured(),
        url=settings.WEBHOOK_URL if webhook_service.is_configured() else "",
        max_retries=settings.WEBHOOK_MAX_RETRIES,
        retry_base_delay_seconds=settings.WEBHOOK_RETRY_BASE_DELAY_SECONDS,
        timeout_seconds=settings.WEBHOOK_TIMEOUT_SECONDS,
        has_secret=bool(settings.WEBHOOK_SECRET)
    )


@router.post("/test", response_model=WebhookTestResponse)
async def test_webhook(
    payload: WebhookTestRequest,
    session: UserSession = Depends(require_admin),
    db: Session = Depends(get_db)
) -> WebhookTestResponse:
    """Send a test webhook notification (admin only)."""
    if not webhook_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook URL not configured"
        )

    result = await webhook_service.dispatch(
        payload.test_event_type,
        {"message": "Test webhook from Knowledge Freshness Monitor", "source": "webhook-test-endpoint"}
    )

    return WebhookTestResponse(
        success=result.get("success", False),
        status_code=result.get("status_code", 0),
        attempts=result.get("attempts", 0),
        reason=result.get("reason", "")
    )