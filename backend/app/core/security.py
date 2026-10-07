"""Authentication, authorization, session management, and CSRF protection."""
import secrets
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.entities import UserSession


def generate_secure_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")


def create_server_session(
    db: Session,
    user_id: str,
    username: str,
    email: str,
    role: str = "viewer",
    duration_hours: int = 24
) -> UserSession:
    session_token = generate_secure_token(48)
    csrf_token = generate_secure_token(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

    user_session = UserSession(
        token=session_token, user_id=user_id, username=username,
        email=email, role=role, csrf_token=csrf_token, expires_at=expires_at
    )
    db.add(user_session)
    db.commit()
    db.refresh(user_session)
    return user_session


def get_current_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    auth_header = request.headers.get("Authorization")
    if not session_token and auth_header and auth_header.startswith("Bearer "):
        session_token = auth_header[7:].strip()

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No valid session or authorization header provided."
        )

    session_record = db.query(UserSession).filter(UserSession.token == session_token).first()
    if not session_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired.")

    now = datetime.now(timezone.utc)
    expiry = session_record.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if now > expiry:
        db.delete(session_record)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")

    if request.cookies.get(settings.SESSION_COOKIE_NAME) and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if not request.url.path.startswith("/api/auth/"):
            header_csrf = request.headers.get("X-CSRF-Token")
            if not header_csrf or header_csrf != session_record.csrf_token:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing CSRF token.")

    return session_record


class RequireRole:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, session: UserSession = Depends(get_current_session)) -> UserSession:
        if session.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(self.allowed_roles)}, current role: {session.role}"
            )
        return session


require_viewer = RequireRole(["viewer", "analyst", "admin"])
require_analyst = RequireRole(["analyst", "admin"])
require_admin = RequireRole(["admin"])
