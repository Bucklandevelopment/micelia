"""
Unit coverage for app.core.security.

`security.py` concentrates the platform's auth surface: the in-memory API-key
manager, the sliding-window rate limiter, the AppleScript-injection sanitizer,
the audit logger (writes to the Event Store), the single-user JWT manager, and
the FastAPI auth dependencies (`verify_auth`, `verify_api_key`,
`check_rate_limit`, `require_write_permission`, `osascript_security`,
`verify_api_key_global`) plus the `OSAScriptSecurityContext` risk classifier.

Everything is exercised in-process with no infra:
  - `Request` is a lightweight `SimpleNamespace` fake (only the attributes the
    code touches: `.client.host`, `.headers.get`, `.url.path`, `.method`,
    `.app.state`, `.state`).
  - The Event Store is an `AsyncMock` (or absent → the None-safe path).
  - `settings` is monkeypatched per test.
  - The module-level `api_key_manager` / `rate_limiter` singletons are replaced
    with fresh instances per test (autouse fixture) so there is no cross-test
    state bleed.
  - JWT / bcrypt run for real (jose + passlib), which also guards the
    register→login funnel's crypto path.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import app.core.security as sec

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_singletons(monkeypatch):
    """Replace the module singletons with fresh, empty instances per test.

    `APIKeyManager()` reads `settings.system_api_key`; with the default
    placeholder no keys are loaded, so each test starts from an empty keyring.
    The rate limiter gets a high default so unrelated dependency tests are not
    throttled; the throttling test overrides it locally.
    """
    monkeypatch.setattr(sec, "api_key_manager", sec.APIKeyManager())
    monkeypatch.setattr(
        sec, "rate_limiter", sec.RateLimiter(default_limit=1000, window_seconds=60)
    )


def _make_request(
    *,
    client_host="1.2.3.4",
    headers=None,
    path="/api/v1/thing",
    method="POST",
    event_store="__unset__",
    client_present=True,
):
    """Build a minimal object that quacks like a FastAPI Request."""
    app_state = SimpleNamespace()
    if event_store != "__unset__":
        app_state.event_store = event_store
    return SimpleNamespace(
        client=SimpleNamespace(host=client_host) if client_present else None,
        headers=headers or {},
        url=SimpleNamespace(path=path),
        method=method,
        app=SimpleNamespace(state=app_state),
        state=SimpleNamespace(),
    )


# ---------------------------------------------------------------------------
# APIKeyManager
# ---------------------------------------------------------------------------


def test_load_default_keys_master_and_readonly(monkeypatch):
    monkeypatch.setattr(sec.settings, "system_api_key", "master-secret", raising=False)
    monkeypatch.setattr(
        sec.settings, "system_api_key_readonly", "ro-secret", raising=False
    )
    mgr = sec.APIKeyManager()

    master = mgr.validate_key("master-secret")
    assert master is not None
    assert master["name"] == "master"
    assert master["permissions"] == {"all"}
    assert master["rate_limit"] == 1000

    ro = mgr.validate_key("ro-secret")
    assert ro is not None
    assert ro["name"] == "readonly"
    assert ro["permissions"] == {"read"}


def test_load_default_keys_skips_placeholder_and_missing(monkeypatch):
    monkeypatch.setattr(
        sec.settings, "system_api_key", "change-me-in-production", raising=False
    )
    monkeypatch.setattr(sec.settings, "system_api_key_readonly", None, raising=False)
    mgr = sec.APIKeyManager()
    assert mgr.validate_key("change-me-in-production") is None


def test_validate_key_empty_returns_none():
    mgr = sec.APIKeyManager()
    assert mgr.validate_key("") is None
    assert mgr.validate_key(None) is None


def test_has_permission_variants():
    mgr = sec.APIKeyManager()
    read_key = mgr.generate_key("reader", {"read"})
    all_key = mgr.generate_key("root", {"all"})

    assert mgr.has_permission(read_key, "read") is True
    assert mgr.has_permission(read_key, "write") is False
    assert mgr.has_permission(all_key, "write") is True  # "all" grants everything
    assert mgr.has_permission("nonexistent-key", "read") is False


def test_generate_key_roundtrip():
    mgr = sec.APIKeyManager()
    key = mgr.generate_key("service", {"write"}, rate_limit=50)
    data = mgr.validate_key(key)
    assert data is not None
    assert data["name"] == "service"
    assert data["permissions"] == {"write"}
    assert data["rate_limit"] == 50


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


def test_is_allowed_under_and_at_limit():
    rl = sec.RateLimiter(default_limit=2, window_seconds=60)
    allowed1, info1 = rl.is_allowed("client")
    allowed2, info2 = rl.is_allowed("client")
    allowed3, info3 = rl.is_allowed("client")

    assert allowed1 is True and allowed2 is True
    assert allowed3 is False  # third request exceeds limit of 2
    assert info1["limit"] == 2
    assert info3["remaining"] == 0
    assert info3["reset_at"] > 0


def test_is_allowed_custom_limit_overrides_default():
    rl = sec.RateLimiter(default_limit=100, window_seconds=60)
    allowed, info = rl.is_allowed("client", limit=1)
    assert allowed is True
    assert info["limit"] == 1
    # Next call with the same explicit limit is refused.
    assert rl.is_allowed("client", limit=1)[0] is False


def test_cleanup_old_requests_drops_stale_timestamps():
    rl = sec.RateLimiter(default_limit=1, window_seconds=60)
    # Inject a timestamp far outside the window (epoch 0) → must be pruned,
    # freeing the single slot so the next request is allowed.
    rl._requests["client"] = [0.0]
    allowed, _ = rl.is_allowed("client")
    assert allowed is True
    assert 0.0 not in rl._requests["client"]


def test_get_limit_for_key():
    rl = sec.RateLimiter(default_limit=30, window_seconds=60)
    key = sec.api_key_manager.generate_key("tiered", {"read"}, rate_limit=500)
    assert rl.get_limit_for_key(key) == 500
    assert rl.get_limit_for_key(None) == 30
    assert rl.get_limit_for_key("unknown-key") == 30


# ---------------------------------------------------------------------------
# AppleScriptSanitizer
# ---------------------------------------------------------------------------


def test_sanitize_empty_returns_empty():
    assert sec.sanitizer.sanitize_string("") == ""


def test_sanitize_truncates_to_field_max():
    long = "a" * 500
    out = sec.sanitizer.sanitize_string(long, "query")  # query max = 100
    assert len(out) == 100


def test_sanitize_rejects_dangerous_patterns():
    with pytest.raises(ValueError):
        sec.sanitizer.sanitize_string("please do shell script rm -rf /")


def test_sanitize_escapes_and_strips_control_chars():
    out = sec.sanitizer.sanitize_string('he said "hi"\n\x00ok')
    assert '\\"' in out  # quotes escaped
    assert "\\n" in out  # newline escaped
    assert "\x00" not in out  # null byte stripped


def test_validate_url_paths():
    s = sec.sanitizer
    assert s.validate_url("https://example.com/x").startswith("https://example.com")

    with pytest.raises(ValueError):
        s.validate_url("")
    with pytest.raises(ValueError):
        s.validate_url("ftp://example.com")  # not http/https


def test_validate_url_localhost_blocked_when_not_debug(monkeypatch):
    monkeypatch.setattr(sec.settings, "debug", False)
    with pytest.raises(ValueError):
        sec.sanitizer.validate_url("https://localhost/api")


def test_validate_url_localhost_allowed_when_debug(monkeypatch):
    monkeypatch.setattr(sec.settings, "debug", True)
    assert sec.sanitizer.validate_url("https://localhost/api").startswith("https://")


def test_validate_path_variants():
    s = sec.sanitizer
    assert s.validate_path("/Users/me/file.txt") == "/Users/me/file.txt"

    with pytest.raises(ValueError):
        s.validate_path("")
    with pytest.raises(ValueError):
        s.validate_path("/Users/me/../etc/passwd")  # traversal
    with pytest.raises(ValueError):
        s.validate_path("/etc/passwd")  # not an allowed prefix


def test_is_safe():
    assert sec.sanitizer.is_safe("perfectly normal text") is True
    assert sec.sanitizer.is_safe("run script evil") is False


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_operation_without_store_is_noop():
    req = _make_request()  # no event_store attribute → None
    await sec.audit_logger.log_operation("send_notification", req)


@pytest.mark.asyncio
async def test_log_operation_writes_to_store_with_masked_key():
    store = AsyncMock()
    req = _make_request(headers={"user-agent": "pytest"}, event_store=store)
    await sec.audit_logger.log_operation(
        "send_notification",
        req,
        api_key="abcdefghijkl1234",  # len > 12 → masked as prefix...suffix
        success=True,
        details={"foo": "bar"},
    )
    store.append_event.assert_awaited_once()
    kwargs = store.append_event.await_args.kwargs
    assert kwargs["category"] == "security"
    assert kwargs["source"] == "osascript"
    assert kwargs["payload"]["api_key"] == "abcdefgh...1234"


@pytest.mark.asyncio
async def test_log_operation_short_key_and_no_client():
    store = AsyncMock()
    req = _make_request(event_store=store, client_present=False)
    await sec.audit_logger.log_operation("say_text", req, api_key="short")
    kwargs = store.append_event.await_args.kwargs
    assert kwargs["payload"]["api_key"] == "***"  # short key fully masked
    assert kwargs["payload"]["client_ip"] == "unknown"  # no request.client


@pytest.mark.asyncio
async def test_log_operation_swallows_store_errors():
    store = AsyncMock()
    store.append_event = AsyncMock(side_effect=RuntimeError("db down"))
    req = _make_request(event_store=store)
    # Must not raise.
    await sec.audit_logger.log_operation("send_notification", req)


@pytest.mark.asyncio
async def test_log_security_event_store_and_none_and_error():
    # store present
    store = AsyncMock()
    req = _make_request(event_store=store)
    await sec.audit_logger.log_security_event("auth_missing", req, {"reason": "x"})
    assert store.append_event.await_args.kwargs["action"] == "alert"

    # store absent
    await sec.audit_logger.log_security_event("auth_missing", _make_request(), {"r": 1})

    # store raises → swallowed
    bad = AsyncMock()
    bad.append_event = AsyncMock(side_effect=RuntimeError("boom"))
    await sec.audit_logger.log_security_event(
        "rate_limit_exceeded", _make_request(event_store=bad), {"limit": 1}
    )


# ---------------------------------------------------------------------------
# JWTAuthManager  (real jose + bcrypt)
# ---------------------------------------------------------------------------


def test_verify_password_no_hash_returns_false(monkeypatch):
    monkeypatch.setattr(sec.settings, "auth_password_hash", "")
    assert sec.jwt_auth.verify_password("whatever") is False


def test_verify_password_true_and_false(monkeypatch):
    hashed = sec.JWTAuthManager.hash_password("correct horse")
    monkeypatch.setattr(sec.settings, "auth_password_hash", hashed)
    assert sec.jwt_auth.verify_password("correct horse") is True
    assert sec.jwt_auth.verify_password("wrong") is False


def test_hash_password_is_bcrypt():
    h = sec.jwt_auth.hash_password("pw")
    assert h.startswith("$2")  # bcrypt marker


def test_token_roundtrip():
    access = sec.jwt_auth.create_access_token("user-1")
    refresh = sec.jwt_auth.create_refresh_token("user-1")

    decoded_a = sec.jwt_auth.decode_token(access)
    decoded_r = sec.jwt_auth.decode_token(refresh)
    assert decoded_a["sub"] == "user-1"
    assert decoded_a["type"] == "access"
    assert decoded_r["type"] == "refresh"


# ---------------------------------------------------------------------------
# verify_auth (unified API key OR JWT bearer)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_auth_valid_api_key():
    key = sec.api_key_manager.generate_key("sat", {"all"})
    res = await sec.verify_auth(_make_request(), api_key=key, bearer=None)
    assert res == "apikey:sat"


@pytest.mark.asyncio
async def test_verify_auth_invalid_api_key_401():
    with pytest.raises(HTTPException) as exc:
        await sec.verify_auth(_make_request(), api_key="nope", bearer=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_auth_valid_bearer():
    token = sec.jwt_auth.create_access_token("admin")
    bearer = SimpleNamespace(credentials=token)
    res = await sec.verify_auth(_make_request(), api_key=None, bearer=bearer)
    assert res == "jwt:admin"


@pytest.mark.asyncio
async def test_verify_auth_bearer_wrong_type_401():
    token = sec.jwt_auth.create_refresh_token("admin")  # type=refresh
    bearer = SimpleNamespace(credentials=token)
    with pytest.raises(HTTPException) as exc:
        await sec.verify_auth(_make_request(), api_key=None, bearer=bearer)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token type"


@pytest.mark.asyncio
async def test_verify_auth_bearer_jwt_error_401():
    bearer = SimpleNamespace(credentials="not.a.jwt")
    with pytest.raises(HTTPException) as exc:
        await sec.verify_auth(_make_request(), api_key=None, bearer=bearer)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_auth_nothing_provided_401():
    with pytest.raises(HTTPException) as exc:
        await sec.verify_auth(_make_request(), api_key=None, bearer=None)
    assert exc.value.status_code == 401
    # Empty-credentials bearer also falls through to the final 401.
    empty = SimpleNamespace(credentials="")
    with pytest.raises(HTTPException):
        await sec.verify_auth(_make_request(), api_key=None, bearer=empty)


# ---------------------------------------------------------------------------
# verify_api_key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_api_key_required_missing_401(monkeypatch):
    monkeypatch.setattr(sec.settings, "osascript_require_auth", True, raising=False)
    with pytest.raises(HTTPException) as exc:
        await sec.verify_api_key(_make_request(), api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_required_invalid_401(monkeypatch):
    monkeypatch.setattr(sec.settings, "osascript_require_auth", True, raising=False)
    with pytest.raises(HTTPException) as exc:
        await sec.verify_api_key(_make_request(), api_key="bad")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_required_valid(monkeypatch):
    monkeypatch.setattr(sec.settings, "osascript_require_auth", True, raising=False)
    key = sec.api_key_manager.generate_key("svc", {"read"})
    assert await sec.verify_api_key(_make_request(), api_key=key) == key


@pytest.mark.asyncio
async def test_verify_api_key_optional_when_auth_off(monkeypatch):
    monkeypatch.setattr(sec.settings, "osascript_require_auth", False, raising=False)
    assert await sec.verify_api_key(_make_request(), api_key=None) is None


# ---------------------------------------------------------------------------
# check_rate_limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_rate_limit_allowed_sets_state():
    req = _make_request()
    await sec.check_rate_limit(req, api_key=None)
    assert req.state.rate_limit_info["limit"] == 1000


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded_429(monkeypatch):
    monkeypatch.setattr(
        sec, "rate_limiter", sec.RateLimiter(default_limit=1, window_seconds=60)
    )
    req = _make_request(client_host="9.9.9.9")
    await sec.check_rate_limit(req, api_key=None)  # first ok
    with pytest.raises(HTTPException) as exc:
        await sec.check_rate_limit(req, api_key=None)  # second exceeds
    assert exc.value.status_code == 429
    assert exc.value.headers["X-RateLimit-Remaining"] == "0"


# ---------------------------------------------------------------------------
# require_write_permission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_write_permission_granted(monkeypatch):
    monkeypatch.setattr(sec.settings, "osascript_require_auth", True, raising=False)
    key = sec.api_key_manager.generate_key("writer", {"write"})
    await sec.require_write_permission(_make_request(), api_key=key)  # no raise
    allkey = sec.api_key_manager.generate_key("root", {"all"})
    await sec.require_write_permission(_make_request(), api_key=allkey)  # no raise


@pytest.mark.asyncio
async def test_require_write_permission_denied_403(monkeypatch):
    monkeypatch.setattr(sec.settings, "osascript_require_auth", True, raising=False)
    key = sec.api_key_manager.generate_key("reader", {"read"})
    with pytest.raises(HTTPException) as exc:
        await sec.require_write_permission(_make_request(), api_key=key)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_write_permission_skipped_paths(monkeypatch):
    # auth off → block skipped entirely
    monkeypatch.setattr(sec.settings, "osascript_require_auth", False, raising=False)
    await sec.require_write_permission(_make_request(), api_key="anything")
    # auth on but no key → block skipped (api_key falsy)
    monkeypatch.setattr(sec.settings, "osascript_require_auth", True, raising=False)
    await sec.require_write_permission(_make_request(), api_key=None)


# ---------------------------------------------------------------------------
# osascript_security combined dependency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_osascript_security_read(monkeypatch):
    monkeypatch.setattr(sec.settings, "osascript_require_auth", True, raising=False)
    key = sec.api_key_manager.generate_key("svc", {"read"})
    dep = sec.osascript_security(write=False)
    assert await dep(_make_request(), api_key=key) == key


@pytest.mark.asyncio
async def test_osascript_security_write_requires_permission(monkeypatch):
    monkeypatch.setattr(sec.settings, "osascript_require_auth", True, raising=False)
    dep = sec.osascript_security(write=True)

    all_key = sec.api_key_manager.generate_key("root", {"all"})
    assert await dep(_make_request(), api_key=all_key) == all_key

    read_key = sec.api_key_manager.generate_key("reader", {"read"})
    with pytest.raises(HTTPException) as exc:
        await dep(_make_request(), api_key=read_key)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# verify_api_key_global
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_api_key_global():
    with pytest.raises(HTTPException) as exc_missing:
        await sec.verify_api_key_global(_make_request(), api_key=None)
    assert exc_missing.value.status_code == 401

    with pytest.raises(HTTPException) as exc_invalid:
        await sec.verify_api_key_global(_make_request(), api_key="bad")
    assert exc_invalid.value.status_code == 401

    key = sec.api_key_manager.generate_key("svc", {"all"})
    assert await sec.verify_api_key_global(_make_request(), api_key=key) == key


# ---------------------------------------------------------------------------
# add_security_headers
# ---------------------------------------------------------------------------


def test_add_security_headers():
    resp = SimpleNamespace(headers={})
    out = sec.add_security_headers(resp)
    assert out is resp
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-XSS-Protection"] == "1; mode=block"


# ---------------------------------------------------------------------------
# OSAScriptSecurityContext
# ---------------------------------------------------------------------------


def test_context_disabled_operation(monkeypatch):
    monkeypatch.setattr(
        sec.settings, "osascript_disabled_operations", ["send_notification"],
        raising=False,
    )
    ctx = sec.OSAScriptSecurityContext(_make_request())
    assert ctx.is_allowed("send_notification") is False


def test_context_high_risk_in_production(monkeypatch):
    monkeypatch.setattr(sec.settings, "environment", "production")
    monkeypatch.setattr(sec.settings, "osascript_disabled_operations", [], raising=False)
    monkeypatch.setattr(sec.settings, "osascript_allow_high_risk", False, raising=False)
    ctx = sec.OSAScriptSecurityContext(_make_request())
    assert ctx.is_allowed("set_volume") is False  # high-risk blocked in prod


def test_context_high_risk_allowed_when_flag_set(monkeypatch):
    monkeypatch.setattr(sec.settings, "environment", "production")
    monkeypatch.setattr(sec.settings, "osascript_disabled_operations", [], raising=False)
    monkeypatch.setattr(sec.settings, "osascript_allow_high_risk", True, raising=False)
    ctx = sec.OSAScriptSecurityContext(_make_request())
    assert ctx.is_allowed("set_volume") is True


def test_context_normal_operation_allowed(monkeypatch):
    monkeypatch.setattr(sec.settings, "environment", "development")
    monkeypatch.setattr(sec.settings, "osascript_disabled_operations", [], raising=False)
    ctx = sec.OSAScriptSecurityContext(_make_request())
    assert ctx.is_allowed("get_system_info") is True


def test_context_is_write_operation():
    ctx = sec.OSAScriptSecurityContext(_make_request())
    assert ctx.is_write_operation("send_notification") is True
    assert ctx.is_write_operation("get_system_info") is False


@pytest.mark.asyncio
async def test_context_async_contextmanager():
    async with sec.OSAScriptSecurityContext(_make_request(), api_key="k") as ctx:
        assert ctx.is_write_operation("set_clipboard") is True
