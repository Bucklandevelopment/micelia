"""
Tests for ProviderStore (app.services.frangels.provider_store).

Pure-logic suite: the only external boundary is an encrypted JSON file whose
directory is the `storage_path` constructor argument, pointed at pytest's
`tmp_path`. Encryption uses the real Fernet derived from `settings.secret_key`
(default value, deterministic salt) so save/load round-trips genuinely, mirroring
the style of test_quota_manager_codex.py (tmp_path + real ANGEL_REGISTRY).

Covers:
  - ProviderCredential.__post_init__ (created_at set-or-preserved, updated_at always)
  - __init__ / _init_encryption (directory creation, empty load)
  - _load (missing file, real round-trip, corrupt file -> empty)
  - _save exception branch (write_bytes raising is swallowed and logged)
  - get / get_api_key (present-enabled, present-disabled, missing)
  - set (create new, update existing)
  - delete / enable / disable / mark_used (present + absent branches)
  - list_configured / get_all_status
  - export_to_env (enabled, disabled skip, unknown provider skip, extra_key)
  - sync_from_env (only sets absent + present-key providers; extra_key)
  - get_provider_store singleton (cached branch)
"""

from unittest.mock import patch

import pytest

import app.services.frangels.provider_store as ps_module
from app.services.frangels.provider_store import (
    ProviderCredential,
    ProviderStore,
    get_provider_store,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton around each test."""
    ps_module._provider_store = None
    yield
    ps_module._provider_store = None


@pytest.fixture
def store(tmp_path):
    """A ProviderStore writing its providers.enc under an isolated tmp dir."""
    return ProviderStore(storage_path=str(tmp_path))


# ---------------------------------------------------------------------------
# ProviderCredential.__post_init__
# ---------------------------------------------------------------------------


def test_credential_post_init_sets_timestamps():
    cred = ProviderCredential(provider_id="groq", api_key="k")
    assert cred.created_at != ""
    assert cred.updated_at != ""


def test_credential_post_init_preserves_created_at():
    cred = ProviderCredential(
        provider_id="groq", api_key="k", created_at="2020-01-01T00:00:00+00:00"
    )
    # created_at preserved when provided; updated_at always refreshed to now
    assert cred.created_at == "2020-01-01T00:00:00+00:00"
    assert cred.updated_at != "2020-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# __init__ / _load
# ---------------------------------------------------------------------------


def test_init_creates_storage_dir(tmp_path):
    target = tmp_path / "nested" / "frangels"
    ProviderStore(storage_path=str(target))
    assert target.exists()


def test_load_missing_file_is_empty(store):
    assert store.list_configured() == {}


def test_save_load_round_trip(tmp_path):
    s1 = ProviderStore(storage_path=str(tmp_path))
    s1.set("groq", "secret-key", extra_key="x", enabled=True)
    assert (tmp_path / "providers.enc").exists()

    # A fresh store over the same dir must decrypt and reload the credential.
    s2 = ProviderStore(storage_path=str(tmp_path))
    cred = s2.get("groq")
    assert cred is not None
    assert cred.api_key == "secret-key"
    assert cred.extra_key == "x"
    assert cred.enabled is True


def test_load_corrupt_file_is_empty(tmp_path):
    (tmp_path / "providers.enc").write_bytes(b"not-a-valid-fernet-token")
    s = ProviderStore(storage_path=str(tmp_path))
    assert s.list_configured() == {}


def test_save_exception_is_swallowed(store):
    # _save catches any exception and logs it; the in-memory state still updated.
    with patch.object(
        ps_module.Path, "write_bytes", side_effect=OSError("disk full")
    ):
        store.set("groq", "k")  # calls _save internally; must not raise
    assert store.get("groq") is not None


# ---------------------------------------------------------------------------
# get / get_api_key
# ---------------------------------------------------------------------------


def test_get_missing_returns_none(store):
    assert store.get("nope") is None


def test_get_api_key_enabled(store):
    store.set("groq", "k")
    assert store.get_api_key("groq") == "k"


def test_get_api_key_disabled_returns_none(store):
    store.set("groq", "k", enabled=False)
    assert store.get_api_key("groq") is None


def test_get_api_key_missing_returns_none(store):
    assert store.get_api_key("nope") is None


# ---------------------------------------------------------------------------
# set (create / update)
# ---------------------------------------------------------------------------


def test_set_creates_new(store):
    store.set("groq", "k1")
    assert store.get("groq").api_key == "k1"


def test_set_updates_existing(store):
    store.set("groq", "k1")
    store.set("groq", "k2", extra_key="e", enabled=False)
    cred = store.get("groq")
    assert cred.api_key == "k2"
    assert cred.extra_key == "e"
    assert cred.enabled is False


# ---------------------------------------------------------------------------
# delete / enable / disable / mark_used
# ---------------------------------------------------------------------------


def test_delete_present(store):
    store.set("groq", "k")
    store.delete("groq")
    assert store.get("groq") is None


def test_delete_absent_is_noop(store):
    store.delete("nope")  # must not raise
    assert store.get("nope") is None


def test_enable_present(store):
    store.set("groq", "k", enabled=False)
    store.enable("groq")
    assert store.get("groq").enabled is True


def test_enable_absent_is_noop(store):
    store.enable("nope")  # must not raise


def test_disable_present(store):
    store.set("groq", "k", enabled=True)
    store.disable("groq")
    assert store.get("groq").enabled is False


def test_disable_absent_is_noop(store):
    store.disable("nope")  # must not raise


def test_mark_used_present(store):
    store.set("groq", "k")
    assert store.get("groq").last_used is None
    store.mark_used("groq")
    assert store.get("groq").last_used is not None


def test_mark_used_absent_is_noop(store):
    store.mark_used("nope")  # must not raise


# ---------------------------------------------------------------------------
# list_configured / get_all_status
# ---------------------------------------------------------------------------


def test_list_configured(store):
    store.set("groq", "k", enabled=True)
    store.set("gemini", "k", enabled=False)
    assert store.list_configured() == {"groq": True, "gemini": False}


def test_get_all_status(store):
    store.set("groq", "k", extra_key="e")
    status = store.get_all_status()["groq"]
    assert status["configured"] is True
    assert status["enabled"] is True
    assert status["has_extra_key"] is True
    assert status["last_used"] is None


# ---------------------------------------------------------------------------
# export_to_env
# ---------------------------------------------------------------------------


def test_export_to_env_enabled_with_extra(store):
    # kaggle has env_key=KAGGLE_KEY and env_key_extra=KAGGLE_USERNAME
    store.set("kaggle", "kkey", extra_key="kuser")
    env = store.export_to_env()
    assert env["KAGGLE_KEY"] == "kkey"
    assert env["KAGGLE_USERNAME"] == "kuser"


def test_export_to_env_skips_disabled(store):
    store.set("groq", "k", enabled=False)
    assert "GROQ_API_KEY" not in store.export_to_env()


def test_export_to_env_skips_unknown_provider(store):
    store.set("not-an-angel", "k")
    assert store.export_to_env() == {}


# ---------------------------------------------------------------------------
# sync_from_env
# ---------------------------------------------------------------------------


def test_sync_from_env_sets_present_key(store):
    def fake_getenv(name, default=None):
        return "env-groq" if name == "GROQ_API_KEY" else None

    with patch.object(ps_module.os, "getenv", side_effect=fake_getenv):
        store.sync_from_env()
    assert store.get_api_key("groq") == "env-groq"


def test_sync_from_env_skips_when_already_present(store):
    store.set("groq", "original")

    def fake_getenv(name, default=None):
        return "env-groq" if name == "GROQ_API_KEY" else None

    with patch.object(ps_module.os, "getenv", side_effect=fake_getenv):
        store.sync_from_env()
    # existing credential is not overwritten
    assert store.get_api_key("groq") == "original"


def test_sync_from_env_no_env_is_noop(store):
    with patch.object(ps_module.os, "getenv", return_value=None):
        store.sync_from_env()
    assert store.list_configured() == {}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_provider_store_singleton(tmp_path, monkeypatch):
    # Point the default storage path at tmp so no ./data/frangels is touched.
    monkeypatch.chdir(tmp_path)
    a = get_provider_store()
    b = get_provider_store()
    assert a is b
