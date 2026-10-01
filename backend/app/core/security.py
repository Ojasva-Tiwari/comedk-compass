import secrets
from typing import Optional
from fastapi import Header, HTTPException, Request, status

from backend.app.config import settings


def verify_admin_key(
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> str:
    """Verifies internal operational credentials via X-Admin-Key or Authorization header using constant-time comparison.

    Protects internal data health dashboards and administrative endpoints.
    Query-parameter authentication is strictly prohibited to prevent secret leakage
    in URLs, browser history, referrers, and access logs.
    Public candidate counselling endpoints and health probes do NOT use this dependency.
    """
    token = x_admin_key

    # Also check Authorization: Bearer <token>
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token or not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid administrator credential",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(token.encode("utf-8"), settings.ADMIN_API_KEY.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid administrator credential",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token
