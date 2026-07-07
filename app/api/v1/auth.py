"""
Authentication endpoints for Micelia.

Provides JWT-based login for dashboard access.
Does NOT require auth itself (it's the entry point).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import audit_logger, jwt_auth, pwd_context, verify_auth

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class SetupRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request):
    """Authenticate with username/password and receive JWT tokens."""
    if data.username != settings.auth_username:
        await audit_logger.log_security_event(
            "login_failed", request, {"reason": "invalid username"}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not jwt_auth.verify_password(data.password):
        await audit_logger.log_security_event(
            "login_failed", request, {"reason": "invalid password"}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = jwt_auth.create_access_token(subject=data.username)
    refresh_token = jwt_auth.create_refresh_token(subject=data.username)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest):
    """Get a new access token using a refresh token."""
    from jose import JWTError

    try:
        payload = jwt_auth.decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        subject = payload.get("sub", "admin")
        access_token = jwt_auth.create_access_token(subject=subject)
        new_refresh = jwt_auth.create_refresh_token(subject=subject)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.get("/me")
async def get_current_user(auth: str = Depends(verify_auth)):
    """Return current authenticated user info."""
    return {
        "username": settings.auth_username,
        "auth_method": auth.split(":")[0] if ":" in auth else "unknown",
        "auth_identity": auth.split(":", 1)[1] if ":" in auth else auth,
    }


@router.post("/setup")
async def setup_password(data: SetupRequest, request: Request):
    """
    First-time password setup. Only works when no password hash is configured.
    After calling this, set AUTH_PASSWORD_HASH in .env for persistence.
    """
    if settings.auth_password_hash:
        raise HTTPException(
            status_code=403,
            detail="Password already configured. Update AUTH_PASSWORD_HASH in .env to change it.",
        )

    hashed = pwd_context.hash(data.password)

    # Update runtime settings (won't persist across restarts without .env update)
    settings.auth_username = data.username
    settings.auth_password_hash = hashed

    return {
        "status": "ok",
        "message": "Password configured for this session. Add to .env for persistence.",
        "env_line": f'AUTH_PASSWORD_HASH="{hashed}"',
        "username": data.username,
    }
