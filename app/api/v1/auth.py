"""
Authentication endpoints for Micelia.

Provides JWT-based login for dashboard access.
Does NOT require auth itself (it's the entry point).
"""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.core.security import audit_logger, jwt_auth, pwd_context, verify_auth
from app.services.user_store import DuplicateEmailError

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Validación de email sin dependencia externa (email-validator no está instalado).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    """Alta de un nuevo usuario del funnel (email + contraseña)."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("email inválido")
        return v

    @field_validator("password")
    @classmethod
    def _valid_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("la contraseña debe tener al menos 8 caracteres")
        return v


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


def _issue_tokens(subject: str) -> TokenResponse:
    """Emite el par access/refresh para un `subject` (user_id o admin)."""
    return TokenResponse(
        access_token=jwt_auth.create_access_token(subject=subject),
        refresh_token=jwt_auth.create_refresh_token(subject=subject),
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, request: Request):
    """Registra un nuevo usuario del funnel y devuelve tokens JWT (auto-login)."""
    user_store = getattr(request.app.state, "user_store", None)
    if user_store is None:
        raise HTTPException(status_code=503, detail="User registration not available")

    password_hash = pwd_context.hash(data.password)
    try:
        user = await user_store.create_user(data.email, password_hash)
    except DuplicateEmailError:
        await audit_logger.log_security_event(
            "register_failed", request, {"reason": "email already registered"}
        )
        raise HTTPException(status_code=409, detail="Email already registered")

    await audit_logger.log_security_event(
        "register_success", request, {"user_id": user["user_id"]}
    )
    return _issue_tokens(subject=user["user_id"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request):
    """
    Autentica con email/usuario + contraseña y devuelve tokens JWT.

    Prioriza usuarios registrados (UserStore, subject=user_id). Mantiene el login
    legacy del admin único (settings.auth_username) como fallback para el dashboard.
    """
    user_store = getattr(request.app.state, "user_store", None)
    if user_store is not None:
        user = await user_store.get_user_by_email(data.username, include_hash=True)
        if user and pwd_context.verify(data.password, user["password_hash"]):
            if not user["is_active"]:
                raise HTTPException(status_code=403, detail="Account disabled")
            await user_store.touch_last_login(UUID(user["user_id"]))
            return _issue_tokens(subject=user["user_id"])

    # Fallback legacy: admin único configurado en .env
    if data.username != settings.auth_username or not jwt_auth.verify_password(
        data.password
    ):
        await audit_logger.log_security_event(
            "login_failed", request, {"reason": "invalid credentials"}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return _issue_tokens(subject=data.username)


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
