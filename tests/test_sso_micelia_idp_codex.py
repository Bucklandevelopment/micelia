"""
C119 — Micelia como Identity Provider (SSO): el ACCESS token de un usuario del funnel lleva los
claims que los dominios necesitan para resolverlo y auto-provisionarlo (`email` + `iss:"micelia"`),
sin romper la semántica propia de Micelia (`sub` = user_id, refresh sin claims SSO).

Fase 1 del plan SSO (piloto biohack). Aquí se pinea SOLO el lado emisor (Micelia). El lado
receptor (biohack acepta este token) vive en el repo de biohack.
"""

from app.api.v1.auth import _issue_tokens
from app.core.security import jwt_auth


def test_create_access_token_without_extra_is_backward_compatible():
    """Sin `extra_claims`, el token es idéntico al de siempre: {sub, exp, type}, sin email/iss."""
    payload = jwt_auth.decode_token(jwt_auth.create_access_token(subject="admin"))
    assert payload["sub"] == "admin"
    assert payload["type"] == "access"
    assert "email" not in payload and "iss" not in payload


def test_create_access_token_merges_extra_claims():
    """`extra_claims` se fusionan en el payload (email, iss)."""
    token = jwt_auth.create_access_token(
        subject="uuid-123", extra_claims={"email": "a@b.com", "iss": "micelia"}
    )
    payload = jwt_auth.decode_token(token)
    assert payload["sub"] == "uuid-123"  # subject intacto
    assert payload["email"] == "a@b.com"
    assert payload["iss"] == "micelia"
    assert payload["type"] == "access"


def test_issue_tokens_for_funnel_user_carries_sso_claims():
    """`_issue_tokens(subject=uuid, email=...)` → el ACCESS token lleva email + iss=micelia,
    con sub = user_id. Es lo que un dominio (biohack) leerá para resolver por email."""
    tokens = _issue_tokens(subject="user-uuid-abc", email="jbuck@icloud.com")
    access = jwt_auth.decode_token(tokens.access_token)
    assert access["sub"] == "user-uuid-abc"
    assert access["email"] == "jbuck@icloud.com"
    assert access["iss"] == "micelia"
    assert access["type"] == "access"


def test_issue_tokens_refresh_has_no_sso_claims():
    """El REFRESH token NO lleva claims SSO (solo se usa contra Micelia)."""
    tokens = _issue_tokens(subject="user-uuid-abc", email="jbuck@icloud.com")
    refresh = jwt_auth.decode_token(tokens.refresh_token)
    assert refresh["type"] == "refresh"
    assert "email" not in refresh and "iss" not in refresh


def test_issue_tokens_admin_without_email_has_no_sso_claims():
    """El login legacy del admin (sin email) NO emite claims SSO: no es un usuario del funnel."""
    tokens = _issue_tokens(subject="admin")
    access = jwt_auth.decode_token(tokens.access_token)
    assert access["sub"] == "admin"
    assert "email" not in access and "iss" not in access
