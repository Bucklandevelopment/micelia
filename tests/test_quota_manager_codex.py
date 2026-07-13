"""
Tests for QuotaManager (app.services.frangels.quota_manager).

Pure-logic suite: the only external boundary is a JSON file whose directory is the
`storage_path` constructor argument, pointed at pytest's `tmp_path`. Uses the real
`ANGEL_REGISTRY` (static data), mirroring the style of test_policy_engine_codex.py.

Covers:
  - record_usage + _check_reset (counter increments, daily/minute reset, persistence)
  - can_use (unknown, paid special-case, and each of the 4 quota limit branches)
  - get_quota_status (the 4 limit-selection branches, percentage cap, is_exhausted, None)
  - get_usage_stats (today/month aggregation + cost rounding)
  - get_best_provider (capability filters, quota exclusion, tier ordering, category fallback)
  - _load/_save round-trip
  - get_quota_manager singleton (cached branch)
"""

from datetime import datetime, timezone

import pytest

import app.services.frangels.quota_manager as qm_module
from app.services.frangels.quota_manager import (
    QuotaManager,
    UsageRecord,
    get_quota_manager,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton around each test (policy-engine pattern)."""
    qm_module._quota_manager = None
    yield
    qm_module._quota_manager = None


@pytest.fixture
def qm(tmp_path):
    """A QuotaManager writing its usage.json under an isolated tmp dir."""
    return QuotaManager(storage_path=str(tmp_path))


def _now_strings():
    """Return (today, this_minute) exactly as _check_reset computes them."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d %H:%M")


def _seed_current(usage):
    """Stamp reset markers to 'now' so _check_reset does not wipe seeded counters."""
    today, minute = _now_strings()
    usage.last_reset_day = today
    usage.last_reset_minute = minute


# ---------------------------------------------------------------------------
# record_usage + _check_reset
# ---------------------------------------------------------------------------


def test_record_usage_increments_and_persists(qm, tmp_path):
    qm.record_usage("groq", tokens_input=100, tokens_output=50, latency_ms=12.0)

    usage = qm._usage["groq"]
    assert usage.requests_today == 1
    assert usage.requests_this_minute == 1
    assert usage.tokens_today == 150
    assert usage.tokens_this_minute == 150
    assert usage.last_request is not None
    # Persistence: usage.json written under the tmp storage path.
    assert (tmp_path / "usage.json").exists()
    # History captured the record.
    assert len(qm._history) == 1
    assert qm._history[0].tokens_input == 100


def test_record_usage_counts_errors(qm):
    qm.record_usage("groq", success=False, error="boom")
    assert qm._usage["groq"].errors_24h == 1


def test_check_reset_clears_stale_day_and_minute(qm):
    qm.record_usage("groq", tokens_input=10, tokens_output=10)
    usage = qm._usage["groq"]
    # Force stale counters from the distant past.
    usage.requests_today = 99
    usage.tokens_today = 999
    usage.errors_24h = 5
    usage.requests_this_minute = 42
    usage.tokens_this_minute = 500
    usage.last_reset_day = "2000-01-01"
    usage.last_reset_minute = "2000-01-01 00:00"

    qm.record_usage("groq", tokens_input=5, tokens_output=5)

    # Counters were reset to 0 by _check_reset, then bumped by this single call.
    assert usage.requests_today == 1
    assert usage.requests_this_minute == 1
    assert usage.tokens_today == 10
    assert usage.tokens_this_minute == 10
    assert usage.errors_24h == 0


def test_load_save_round_trip(qm, tmp_path):
    qm.record_usage("groq", tokens_input=10, tokens_output=10)
    # A fresh manager over the same path reloads persisted usage + history.
    qm2 = QuotaManager(storage_path=str(tmp_path))
    assert "groq" in qm2._usage
    assert qm2._usage["groq"].requests_today == 1
    assert len(qm2._history) == 1


def test_load_corrupt_json_is_swallowed(tmp_path):
    # usage.json existe pero está corrupto -> json.loads lanza y la rama
    # `except Exception` de _load (84-85) lo registra y degrada a estado vacío.
    (tmp_path / "usage.json").write_text("{ esto no es json valido ")
    qm2 = QuotaManager(storage_path=str(tmp_path))
    assert qm2._usage == {}
    assert qm2._history == []


def test_save_write_error_is_swallowed(qm, tmp_path):
    # usage_file apunta a un directorio -> write_text lanza IsADirectoryError,
    # la rama `except Exception` de _save (95-96) lo registra sin propagar.
    as_dir = tmp_path / "usage_as_dir"
    as_dir.mkdir()
    qm.usage_file = as_dir
    qm._save()  # no raise


# ---------------------------------------------------------------------------
# can_use
# ---------------------------------------------------------------------------


def test_can_use_unknown_provider_is_false(qm):
    assert qm.can_use("does-not-exist") is False


def test_can_use_paid_providers_special_cased(qm):
    assert qm.can_use("openai") is True
    assert qm.can_use("anthropic") is True


def test_can_use_below_limits_is_true(qm):
    assert qm.can_use("groq") is True


def test_can_use_requests_per_minute_exhausted(qm):
    usage = qm._get_usage("groq")  # groq: requests_per_minute=30
    _seed_current(usage)
    usage.requests_this_minute = 30
    assert qm.can_use("groq") is False


def test_can_use_tokens_per_minute_exhausted(qm):
    usage = qm._get_usage("groq")  # groq: tokens_per_minute=20000
    _seed_current(usage)
    usage.tokens_this_minute = 20000
    assert qm.can_use("groq") is False


def test_can_use_requests_per_day_exhausted(qm):
    usage = qm._get_usage("gemini")  # gemini: requests_per_day=1000
    _seed_current(usage)
    usage.requests_today = 1000
    assert qm.can_use("gemini") is False


def test_can_use_tokens_per_day_exhausted(qm):
    usage = qm._get_usage("deepseek")  # deepseek: tokens_per_day=5_000_000 (no rpm/rpd)
    _seed_current(usage)
    usage.tokens_today = 5_000_000
    assert qm.can_use("deepseek") is False


# ---------------------------------------------------------------------------
# get_quota_status
# ---------------------------------------------------------------------------


def test_quota_status_requests_per_day_branch(qm):
    status = qm.get_quota_status("groq")
    assert status is not None
    assert status.unit == "requests"
    assert status.limit == 14400
    assert status.provider_name == "Groq"
    assert status.category == "inference"


def test_quota_status_tokens_per_day_branch(qm):
    status = qm.get_quota_status("deepseek")
    assert status is not None
    assert status.unit == "tokens"
    assert status.limit == 5_000_000


def test_quota_status_tokens_per_minute_branch(qm):
    status = qm.get_quota_status("mistral")  # only requests/tokens per minute set
    assert status is not None
    assert status.unit == "tokens/min"
    assert status.limit == 10000


def test_quota_status_unlimited_fallback_branch(qm):
    status = qm.get_quota_status("openrouter")  # empty QuotaConfig
    assert status is not None
    assert status.unit == "requests"
    assert status.limit == 10000
    assert status.reset_time == "N/A"


def test_quota_status_percentage_capped_and_exhausted(qm):
    usage = qm._get_usage("groq")
    _seed_current(usage)
    usage.requests_today = 20000  # over the 14400 daily cap
    status = qm.get_quota_status("groq")
    assert status is not None
    assert status.percentage == 100  # capped
    assert status.is_exhausted is True


def test_quota_status_unknown_provider_returns_none(qm):
    assert qm.get_quota_status("does-not-exist") is None


def test_get_all_quotas_only_tracked_providers(qm):
    qm.record_usage("groq")
    qm.record_usage("gemini")
    quotas = qm.get_all_quotas()
    ids = {q.provider_id for q in quotas}
    assert ids == {"groq", "gemini"}


# ---------------------------------------------------------------------------
# get_usage_stats
# ---------------------------------------------------------------------------


def test_usage_stats_aggregates_today_and_month(qm):
    today, _ = _now_strings()
    # One record clearly today, one clearly in the distant past (excluded from both).
    qm._history = [
        UsageRecord(
            provider_id="groq",
            timestamp=f"{today}T10:00:00+00:00",
            requests=1,
            tokens_input=500,
            tokens_output=500,
        ),
        UsageRecord(
            provider_id="groq",
            timestamp="2000-01-01T00:00:00+00:00",
            requests=1,
            tokens_input=999,
            tokens_output=999,
        ),
    ]

    stats = qm.get_usage_stats()

    # Only the today record counts for both windows; cost = 1000/1000 * 0.002.
    assert stats["today"] == {
        "requests": 1,
        "tokens": 1000,
        "cost_equivalent_usd": 0.002,
    }
    assert stats["thisMonth"] == stats["today"]
    assert "quotas" in stats


# ---------------------------------------------------------------------------
# get_best_provider
# ---------------------------------------------------------------------------


def test_best_provider_prefers_premium_tier(qm):
    # groq is the first PREMIUM inference angel in registry order.
    assert qm.get_best_provider("inference") == "groq"


def test_best_provider_min_context_filters_to_gemini(qm):
    # Only gemini has max_context_tokens >= 200_000 among inference angels.
    assert qm.get_best_provider("inference", min_context=200_000) == "gemini"


def test_best_provider_skips_exhausted(qm):
    usage = qm._get_usage("groq")
    _seed_current(usage)
    usage.requests_this_minute = 30  # exhaust groq's per-minute quota
    # Next premium inference angel is gemini.
    assert qm.get_best_provider("inference") == "gemini"


def test_best_provider_invalid_category_falls_back_to_inference(qm):
    assert qm.get_best_provider("not-a-category") == "groq"


def test_best_provider_none_when_no_eligible(qm):
    # No inference angel advertises embeddings-only impossible combo here, so use an
    # impossible min_context to exclude everyone.
    assert qm.get_best_provider("inference", min_context=10_000_000) is None


def test_best_provider_require_vision_skips_non_vision_angels(qm):
    # require_vision=True hace `continue` (línea 292) sobre los ángeles de inferencia
    # sin visión (deepseek/cohere/mistral/huggingface); groq (premium, con visión)
    # sigue ganando el orden por tier.
    assert qm.get_best_provider("inference", require_vision=True) == "groq"


def test_best_provider_require_tools_skips_non_tool_angels(qm):
    # require_tools=True hace `continue` (línea 294) sobre huggingface (tools=False);
    # groq (premium, con tools) sigue ganando.
    assert qm.get_best_provider("inference", require_tools=True) == "groq"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_quota_manager_returns_cached_singleton(qm):
    qm_module._quota_manager = qm
    assert get_quota_manager() is qm
