"""Authentication and OIDC identity brokering routes."""
from typing import Dict, Any, Optional
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
import httpx
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import (
    create_server_session,
    generate_secure_token,
    generate_code_verifier,
    generate_code_challenge,
    get_current_session
)
from backend.app.models.entities import UserSession
from backend.app.models.schemas import UserProfile, DemoLoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])
_pkce_store: Dict[str, Dict[str, str]] = {}


@router.get("/me", response_model=UserProfile)
def get_authenticated_user(session: UserSession = Depends(get_current_session)) -> UserProfile:
    return UserProfile(
        user_id=session.user_id, username=session.username, email=session.email,
        role=session.role, csrf_token=session.csrf_token
    )


@router.post("/demo-login", response_model=UserProfile)
def demo_login(
    payload: DemoLoginRequest,
    response: Response,
    db: Session = Depends(get_db)
) -> UserProfile:
    if settings.ENVIRONMENT.strip().lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Startup Refusal: Demo mode is strictly disabled in production environments."
        )

    role = payload.role if payload.role in {"viewer", "analyst", "admin"} else "analyst"
    username = payload.username or f"demo_{role}"
    session = create_server_session(
        db=db, user_id=f"usr_{role}_001", username=username,
        email=f"{username}@local.dev", role=role, duration_hours=24
    )
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME, value=session.token,
        httponly=True, samesite="lax", secure=settings.COOKIE_SECURE, max_age=86400
    )
    return UserProfile(
        user_id=session.user_id, username=session.username, email=session.email,
        role=session.role, csrf_token=session.csrf_token
    )


@router.post("/logout")
def logout(
    response: Response,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    db.delete(session)
    db.commit()
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME, httponly=True, samesite="lax", secure=settings.COOKIE_SECURE
    )
    return {"status": "logged_out", "message": "Session successfully terminated."}


@router.get("/oidc/login")
def oidc_login_redirect() -> Dict[str, str]:
    state = generate_secure_token(24)
    nonce = generate_secure_token(24)
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    _pkce_store[state] = {"verifier": verifier, "nonce": nonce}

    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "nonce": nonce
    }
    auth_url = f"{settings.OIDC_ISSUER_URL.rstrip('/')}/protocol/openid-connect/auth?{urllib.parse.urlencode(params)}"
    return {"auth_url": auth_url, "state": state}


@router.get("/callback")
async def oidc_callback(
    code: str,
    state: str,
    response: Response,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    pkce_data = _pkce_store.pop(state, None)
    if not pkce_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OIDC state parameter.")

    token_url = f"{settings.OIDC_ISSUER_URL.rstrip('/')}/protocol/openid-connect/token"
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": settings.OIDC_CLIENT_ID,
        "code": code,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "code_verifier": pkce_data["verifier"]
    }
    if settings.OIDC_CLIENT_SECRET:
        token_payload["client_secret"] = settings.OIDC_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=10.0) as client:
        token_res = await client.post(token_url, data=token_payload)
        if token_res.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token exchange failed.")
        tokens = token_res.json()

        userinfo_url = f"{settings.OIDC_ISSUER_URL.rstrip('/')}/protocol/openid-connect/userinfo"
        userinfo_res = await client.get(userinfo_url, headers={"Authorization": f"Bearer {tokens['access_token']}"})
        if userinfo_res.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Userinfo request failed.")
        user_info = userinfo_res.json()

    roles = user_info.get("realm_access", {}).get("roles", [])
    role = "admin" if "admin" in roles else ("analyst" if "analyst" in roles else "viewer")
    user_id = user_info.get("sub", generate_secure_token(16))
    username = user_info.get("preferred_username", user_info.get("name", "oidc_user"))

    session = create_server_session(
        db=db, user_id=user_id, username=username,
        email=user_info.get("email", f"{username}@idp.domain"), role=role, duration_hours=24
    )
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME, value=session.token,
        httponly=True, samesite="lax", secure=settings.COOKIE_SECURE, max_age=86400
    )
    return {
        "status": "authenticated", "user_id": session.user_id,
        "username": session.username, "role": session.role, "csrf_token": session.csrf_token
    }
