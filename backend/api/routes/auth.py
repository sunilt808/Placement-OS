"""
api/routes/auth.py — JWT authentication logic.

Credentials come ONLY from config (env/.env). No hardcoded fallbacks.
Fail-closed: if admin credentials or JWT secret are unset, login and
token verification are refused.
"""
import hmac
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"


class LoginRequest(BaseModel):
    username: str
    password: str
    security_code: str


def _admin_creds_configured() -> bool:
    return bool(
        settings.admin_username
        and settings.admin_password
        and settings.admin_security_code
        and settings.jwt_secret
    )


@router.post("/login")
async def login(body: LoginRequest):
    if not _admin_creds_configured():
        # Fail closed — no default credentials exist anywhere.
        raise HTTPException(
            status_code=503,
            detail="Auth not configured. Set ADMIN_USERNAME/ADMIN_PASSWORD/ADMIN_SECURITY_CODE/JWT_SECRET in .env.",
        )

    ok_user = hmac.compare_digest(body.username.lower(), settings.admin_username.lower())
    ok_pass = hmac.compare_digest(body.password, settings.admin_password)
    ok_code = hmac.compare_digest(body.security_code, settings.admin_security_code)
    if not (ok_user and ok_pass and ok_code):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode(
        {"sub": body.username, "exp": datetime.utcnow() + timedelta(days=30)},
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    return {"access_token": token, "user": {"username": settings.admin_username, "role": "admin"}}


def _verify_token(token: str) -> None:
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="Auth not configured")
    try:
        jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.get("/me")
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401)
    _verify_token(credentials.credentials)
    return {"username": settings.admin_username, "role": "admin"}


async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Shared dependency — protects every data router."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    _verify_token(credentials.credentials)
