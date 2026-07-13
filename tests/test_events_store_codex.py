"""
Tests for EventStore service (app/events/store.py).

Async Event Store con persistencia PostgreSQL (event sourcing, append-only).
Se testea con AsyncSession mockeada (MagicMock/AsyncMock) — sin Postgres, sin
dependencias nuevas — replicando el patrón de tests/test_prompt_store_codex.py.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.events.store import EventStore, IdmEventModel
from app.models.base import Base

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event_model(**overrides):
    """Create an IdmEventModel-like object with sensible defaults."""
    defaults = dict(
        event_id=uuid4(),
        correlation_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        category="energy",
        subcategory="battery",
        source="micelia",
        action="measured",
        event_type="energy.battery.measured",
        payload={"level": 80},
        event_metadata={"host": "m1"},
        tags=["auto"],
        compute_provider="local",
        compute_model="ollama",
        compute_latency_ms=12.5,
    )
    defaults.update(overrides)
    obj = MagicMock(spec=IdmEventModel)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _mock_session_ctx(session_mock):
    """Return an async context manager that yields the mock session."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _scalars_result(items):
    """Build a mock result whose .scalars().all() returns `items`."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    return result_mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store():
    """EventStore with a placeholder engine; async_session overridden per test."""
    s = EventStore()
    s.engine = MagicMock()
    return s


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _bind(store, mock_session):
    store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------


class TestInitialize:
    """initialize(): create_async_engine + async_sessionmaker + create_all (mockeado)."""

    @pytest.mark.asyncio
    async def test_initialize_creates_engine_session_and_tables(self, monkeypatch):
        conn = AsyncMock()
        conn.run_sync = AsyncMock()
        begin_cm = AsyncMock()
        begin_cm.__aenter__ = AsyncMock(return_value=conn)
        begin_cm.__aexit__ = AsyncMock(return_value=False)
        engine = MagicMock()
        engine.begin = MagicMock(return_value=begin_cm)
        sentinel_sessionmaker = MagicMock()

        monkeypatch.setattr(
            "app.events.store.create_async_engine", lambda *a, **k: engine
        )
        monkeypatch.setattr(
            "app.events.store.async_sessionmaker", lambda *a, **k: sentinel_sessionmaker
        )

        s = EventStore()
        await s.initialize()

        assert s.engine is engine
        assert s.async_session is sentinel_sessionmaker
        conn.run_sync.assert_awaited_once_with(Base.metadata.create_all)

    @pytest.mark.asyncio
    async def test_initialize_reraises_on_error(self, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("engine down")

        monkeypatch.setattr("app.events.store.create_async_engine", _boom)

        s = EventStore()
        with pytest.raises(RuntimeError, match="engine down"):
            await s.initialize()


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    @pytest.mark.asyncio
    async def test_close_disposes_engine(self):
        engine = AsyncMock()
        s = EventStore()
        s.engine = engine
        await s.close()
        engine.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_no_engine(self):
        s = EventStore()
        s.engine = None
        # Should not raise
        await s.close()


# ---------------------------------------------------------------------------
# append_event
# ---------------------------------------------------------------------------


class TestAppendEvent:
    @pytest.mark.asyncio
    async def test_append_event_returns_uuid_and_persists(self, store, mock_session):
        _bind(store, mock_session)

        result = await store.append_event(
            category="energy",
            source="micelia",
            action="measured",
            event_type="energy.battery.measured",
        )
        assert isinstance(result, UUID)
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_append_event_with_all_fields(self, store, mock_session):
        _bind(store, mock_session)
        corr = uuid4()
        caus = uuid4()
        uid = uuid4()

        result = await store.append_event(
            category="ai",
            source="canela",
            action="ingested",
            event_type="paper.ingested",
            payload={"doi": "10.1/x"},
            subcategory="papers",
            event_metadata={"origin": "arxiv"},
            tags=["research", "bio"],
            correlation_id=corr,
            causation_id=caus,
            user_id=uid,
            compute_provider="openai",
            compute_model="gpt",
            compute_latency_ms=42.0,
            compute_cost_usd=0.01,
        )
        assert isinstance(result, UUID)

        added = mock_session.add.call_args[0][0]
        assert added.category == "ai"
        assert added.source == "canela"
        assert added.action == "ingested"
        assert added.event_type == "paper.ingested"
        assert added.payload == {"doi": "10.1/x"}
        assert added.subcategory == "papers"
        assert added.event_metadata == {"origin": "arxiv"}
        assert added.tags == ["research", "bio"]
        assert added.correlation_id == corr
        assert added.causation_id == caus
        assert added.user_id == uid
        assert added.compute_provider == "openai"
        assert added.compute_model == "gpt"
        assert added.compute_latency_ms == 42.0
        assert added.compute_cost_usd == 0.01

    @pytest.mark.asyncio
    async def test_append_event_defaults(self, store, mock_session):
        _bind(store, mock_session)

        await store.append_event(
            category="system",
            source="micelia",
            action="ping",
            event_type="system.ping",
        )
        added = mock_session.add.call_args[0][0]
        assert added.payload == {}
        assert added.event_metadata == {}
        assert added.tags == []
        assert added.subcategory is None
        assert added.user_id is None

    @pytest.mark.asyncio
    async def test_append_event_legacy_source_normalized_with_warning(
        self, store, mock_session
    ):
        _bind(store, mock_session)

        with pytest.warns(DeprecationWarning):
            result = await store.append_event(
                category="system",
                source="idm-core",
                action="ping",
                event_type="system.ping",
            )
        assert isinstance(result, UUID)
        added = mock_session.add.call_args[0][0]
        assert added.source == "micelia"


# ---------------------------------------------------------------------------
# query_events
# ---------------------------------------------------------------------------


class TestQueryEvents:
    @pytest.mark.asyncio
    async def test_query_events_no_filters(self, store, mock_session):
        e1 = _make_event_model(event_type="a")
        e2 = _make_event_model(event_type="b")
        mock_session.execute = AsyncMock(return_value=_scalars_result([e1, e2]))
        _bind(store, mock_session)

        results = await store.query_events()
        assert len(results) == 2
        assert results[0]["event_type"] == "a"
        assert results[1]["event_type"] == "b"
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_events_all_filters(self, store, mock_session):
        e1 = _make_event_model()
        mock_session.execute = AsyncMock(return_value=_scalars_result([e1]))
        _bind(store, mock_session)

        results = await store.query_events(
            category="energy",
            subcategory="battery",
            source="micelia",
            event_type="energy.battery.measured",
            since=datetime(2026, 1, 1),
            until=datetime(2026, 12, 31),
            user_id=uuid4(),
            limit=10,
            offset=5,
        )
        assert len(results) == 1
        assert results[0]["category"] == "energy"

    @pytest.mark.asyncio
    async def test_query_events_empty(self, store, mock_session):
        mock_session.execute = AsyncMock(return_value=_scalars_result([]))
        _bind(store, mock_session)

        results = await store.query_events(source="micelia")
        assert results == []


# ---------------------------------------------------------------------------
# get_by_correlation
# ---------------------------------------------------------------------------


class TestGetByCorrelation:
    @pytest.mark.asyncio
    async def test_get_by_correlation_returns_events(self, store, mock_session):
        corr = uuid4()
        e1 = _make_event_model(correlation_id=corr)
        mock_session.execute = AsyncMock(return_value=_scalars_result([e1]))
        _bind(store, mock_session)

        results = await store.get_by_correlation(corr)
        assert len(results) == 1
        assert results[0]["correlation_id"] == str(corr)

    @pytest.mark.asyncio
    async def test_get_by_correlation_empty(self, store, mock_session):
        mock_session.execute = AsyncMock(return_value=_scalars_result([]))
        _bind(store, mock_session)

        results = await store.get_by_correlation(uuid4())
        assert results == []


# ---------------------------------------------------------------------------
# get_timeline
# ---------------------------------------------------------------------------


class TestGetTimeline:
    @pytest.mark.asyncio
    async def test_get_timeline_without_categories(self, store, mock_session):
        e1 = _make_event_model()
        mock_session.execute = AsyncMock(return_value=_scalars_result([e1]))
        _bind(store, mock_session)

        results = await store.get_timeline(datetime(2026, 7, 13))
        assert len(results) == 1
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_timeline_with_categories(self, store, mock_session):
        e1 = _make_event_model(category="ai")
        mock_session.execute = AsyncMock(return_value=_scalars_result([e1]))
        _bind(store, mock_session)

        results = await store.get_timeline(
            datetime(2026, 7, 13), categories=["ai", "energy"]
        )
        assert len(results) == 1
        assert results[0]["category"] == "ai"

    @pytest.mark.asyncio
    async def test_get_timeline_empty(self, store, mock_session):
        mock_session.execute = AsyncMock(return_value=_scalars_result([]))
        _bind(store, mock_session)

        results = await store.get_timeline(datetime(2026, 7, 13))
        assert results == []


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    @pytest.mark.asyncio
    async def test_get_stats_populated(self, store, mock_session):
        total_result = MagicMock()
        total_result.scalar.return_value = 12

        cat_result = MagicMock()
        cat_result.all.return_value = [("energy", 7), ("ai", 5)]

        source_result = MagicMock()
        source_result.all.return_value = [("micelia", 8), ("canela", 4)]

        mock_session.execute = AsyncMock(
            side_effect=[total_result, cat_result, source_result]
        )
        _bind(store, mock_session)

        stats = await store.get_stats()
        assert stats["total_events"] == 12
        assert stats["by_category"] == {"energy": 7, "ai": 5}
        assert stats["by_source"] == {"micelia": 8, "canela": 4}

    @pytest.mark.asyncio
    async def test_get_stats_with_since(self, store, mock_session):
        total_result = MagicMock()
        total_result.scalar.return_value = 3
        cat_result = MagicMock()
        cat_result.all.return_value = [("energy", 3)]
        source_result = MagicMock()
        source_result.all.return_value = [("micelia", 3)]

        mock_session.execute = AsyncMock(
            side_effect=[total_result, cat_result, source_result]
        )
        _bind(store, mock_session)

        since = datetime.now(timezone.utc) - timedelta(days=1)
        stats = await store.get_stats(since=since)
        assert stats["total_events"] == 3
        assert stats["by_category"] == {"energy": 3}
        assert stats["by_source"] == {"micelia": 3}

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, store, mock_session):
        total_result = MagicMock()
        total_result.scalar.return_value = 0
        cat_result = MagicMock()
        cat_result.all.return_value = []
        source_result = MagicMock()
        source_result.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[total_result, cat_result, source_result]
        )
        _bind(store, mock_session)

        stats = await store.get_stats()
        assert stats["total_events"] == 0
        assert stats["by_category"] == {}
        assert stats["by_source"] == {}


# ---------------------------------------------------------------------------
# _event_to_dict
# ---------------------------------------------------------------------------


class TestEventToDict:
    def test_event_to_dict_full(self, store):
        eid = uuid4()
        corr = uuid4()
        now = datetime.now(timezone.utc)
        event = _make_event_model(
            event_id=eid,
            correlation_id=corr,
            timestamp=now,
            category="energy",
            subcategory="battery",
            source="micelia",
            action="measured",
            event_type="energy.battery.measured",
            payload={"level": 90},
            event_metadata={"host": "m1"},
            tags=["a", "b"],
            compute_provider="local",
            compute_model="ollama",
            compute_latency_ms=9.9,
        )
        result = store._event_to_dict(event)
        assert result["event_id"] == str(eid)
        assert result["correlation_id"] == str(corr)
        assert result["timestamp"] == now.isoformat()
        assert result["category"] == "energy"
        assert result["subcategory"] == "battery"
        assert result["source"] == "micelia"
        assert result["action"] == "measured"
        assert result["event_type"] == "energy.battery.measured"
        assert result["payload"] == {"level": 90}
        assert result["metadata"] == {"host": "m1"}
        assert result["tags"] == ["a", "b"]
        assert result["compute_provider"] == "local"
        assert result["compute_model"] == "ollama"
        assert result["compute_latency_ms"] == 9.9

    def test_event_to_dict_none_correlation(self, store):
        event = _make_event_model(correlation_id=None)
        result = store._event_to_dict(event)
        assert result["correlation_id"] is None

    def test_event_to_dict_none_timestamp(self, store):
        event = _make_event_model(timestamp=None)
        result = store._event_to_dict(event)
        assert result["timestamp"] is None
