"""
api/routes/auth.py — JWT authentication logic.
"""
import os
import hmac
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "sunil")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Sunil@369")
ADMIN_SECURITY_CODE = os.environ.get("ADMIN_SECURITY_CODE", "48411")
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-369")
JWT_ALGORITHM = "HS256"

class LoginRequest(BaseModel):
    username: str
    password: str
    security_code: str

@router.post("/login")
async def login(body: LoginRequest):
    if not hmac.compare_digest(body.username.lower(), ADMIN_USERNAME.lower()) or \
       not hmac.compare_digest(body.password, ADMIN_PASSWORD) or \
       not hmac.compare_digest(body.security_code, ADMIN_SECURITY_CODE):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = jwt.encode(
        {"sub": body.username, "exp": datetime.utcnow() + timedelta(days=30)},
        JWT_SECRET, algorithm=JWT_ALGORITHM
    )
    return {"access_token": token, "user": {"username": ADMIN_USERNAME, "role": "admin"}}

@router.get("/me")
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401)
    try:
        jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"username": ADMIN_USERNAME, "role": "admin"}
    except:
        raise HTTPException(status_code=401)
