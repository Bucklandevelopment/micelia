"""
Tests for UserStore (app.services.user_store).

Mirrors the mocked-async-session pattern of test_prompt_store_codex.py: the store
is instantiated directly and `async_session` is replaced with a MagicMock returning
an async-context-manager that yields a mock session. No real Postgres involved.

Covers:
  - create_user (success, email normalization, duplicate → DuplicateEmailError)
  - get_user_by_email (found with/without hash, not found, normalization)
  - get_user_by_id (found, not found)
  - touch_last_login (updates + commits)
  - _to_dict (hash excluded by default)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.user import UserModel
from app.services.user_store import DuplicateEmailError, UserStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**overrides):
    defaults = dict(
        user_id=uuid4(),
        email="user@example.com",
        password_hash="hashed-secret",
        is_active=True,
        is_verified=False,
        plan_code="free",
        stripe_customer_id=None,
        created_at=datetime.now(timezone.utc),
        last_login_at=None,
    )
    defaults.update(overrides)
    obj = MagicMock(spec=UserModel)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _mock_session_ctx(session_mock):
    """Return an async context manager that yields the mock session."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _result_scalar(value):
    """A mock Result whose scalar_one_or_none() returns `value`."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


@pytest.fixture
def store():
    s = UserStore()
    s.engine = MagicMock()
    return s


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _wire(store, session):
    store.async_session = MagicMock(return_value=_mock_session_ctx(session))


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


async def test_create_user_success(store, mock_session):
    mock_session.execute = AsyncMock(return_value=_result_scalar(None))  # no duplicate
    _wire(store, mock_session)

    result = await store.create_user("New@Example.com ", "hash123")

    assert result["email"] == "new@example.com"  # normalized
    assert result["plan_code"] == "free"
    assert result["is_active"] is True
    assert "password_hash" not in result  # hash never leaks in public dict
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()


async def test_create_user_duplicate_raises(store, mock_session):
    mock_session.execute = AsyncMock(return_value=_result_scalar(_make_user()))
    _wire(store, mock_session)

    with pytest.raises(DuplicateEmailError):
        await store.create_user("user@example.com", "hash123")
    mock_session.add.assert_not_called()


async def test_create_user_normalizes_email(store, mock_session):
    mock_session.execute = AsyncMock(return_value=_result_scalar(None))
    _wire(store, mock_session)

    result = await store.create_user("  MiXeD@CASE.COM  ", "hash123")
    assert result["email"] == "mixed@case.com"


# ---------------------------------------------------------------------------
# get_user_by_email
# ---------------------------------------------------------------------------


async def test_get_user_by_email_found_excludes_hash_by_default(store, mock_session):
    mock_session.execute = AsyncMock(
        return_value=_result_scalar(_make_user(email="a@b.com"))
    )
    _wire(store, mock_session)

    result = await store.get_user_by_email("A@B.com")
    assert result is not None
    assert result["email"] == "a@b.com"
    assert "password_hash" not in result


async def test_get_user_by_email_include_hash(store, mock_session):
    mock_session.execute = AsyncMock(
        return_value=_result_scalar(_make_user(password_hash="pbkdf2$xyz"))
    )
    _wire(store, mock_session)

    result = await store.get_user_by_email("user@example.com", include_hash=True)
    assert result["password_hash"] == "pbkdf2$xyz"


async def test_get_user_by_email_not_found(store, mock_session):
    mock_session.execute = AsyncMock(return_value=_result_scalar(None))
    _wire(store, mock_session)

    assert await store.get_user_by_email("missing@example.com") is None


# ---------------------------------------------------------------------------
# get_user_by_id / touch_last_login
# ---------------------------------------------------------------------------


async def test_get_user_by_id_found(store, mock_session):
    uid = uuid4()
    mock_session.execute = AsyncMock(
        return_value=_result_scalar(_make_user(user_id=uid))
    )
    _wire(store, mock_session)

    result = await store.get_user_by_id(uid)
    assert result is not None
    assert result["user_id"] == str(uid)


async def test_get_user_by_id_not_found(store, mock_session):
    mock_session.execute = AsyncMock(return_value=_result_scalar(None))
    _wire(store, mock_session)

    assert await store.get_user_by_id(uuid4()) is None


async def test_touch_last_login_sets_timestamp_and_commits(store, mock_session):
    user = _make_user(last_login_at=None)
    mock_session.execute = AsyncMock(return_value=_result_scalar(user))
    _wire(store, mock_session)

    await store.touch_last_login(user.user_id)

    assert user.last_login_at is not None
    mock_session.commit.assert_awaited_once()


async def test_touch_last_login_missing_user_is_noop(store, mock_session):
    mock_session.execute = AsyncMock(return_value=_result_scalar(None))
    _wire(store, mock_session)

    await store.touch_last_login(uuid4())
    mock_session.commit.assert_not_called()
