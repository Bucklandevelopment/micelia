"""
Tests for the Events API router (app/api/v1/events.py).

The router reads the event store from ``request.app.state.event_store`` directly
(NOT via ``getattr(..., None)`` like ``sync.py``), so the app **must** set
``app.state.event_store`` explicitly — to ``None`` to exercise the 503
"not available" branch, or to an ``AsyncMock`` for the happy paths. All of the
store methods the router awaits (``query_events``/``get_timeline``/
``get_by_correlation``/``append_event``/``get_stats``) are async → ``AsyncMock``.
Nothing here touches Postgres, Redis or the network.

``list_categories`` is a static endpoint (no store) and is asserted on its own.
Auth is the real ``verify_auth`` dependency; a dedicated valid key is generated.
"""

import contextlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import events
from app.core.security import api_key_manager

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-events", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app(event_store=None) -> FastAPI:
    """Mount only the events router; seed app.state.event_store.

    The router accesses ``request.app.state.event_store`` directly, so we always
    set it (default ``None`` → the 503 branch). Pass an AsyncMock for happy paths.
    """
    app = FastAPI()
    app.include_router(events.router, prefix="/api/v1")
    app.state.event_store = event_store
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def fake_store(**overrides) -> AsyncMock:
    """EventStore double: every method the router awaits is an AsyncMock."""
    store = AsyncMock()
    store.query_events.return_value = overrides.get("query_events", [{"id": "e1"}])
    store.get_timeline.return_value = overrides.get("get_timeline", [{"id": "t1"}])
    store.get_by_correlation.return_value = overrides.get(
        "get_by_correlation", [{"id": "c1"}]
    )
    store.append_event.return_value = overrides.get("append_event", uuid4())
    store.get_stats.return_value = overrides.get(
        "get_stats", {"total": 3, "by_category": {"health": 3}}
    )
    return store


# ============================================================ 503 branches


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/events"),
        ("get", "/api/v1/events/timeline/2026-07-13"),
        ("get", f"/api/v1/events/by-correlation/{uuid4()}"),
        ("get", "/api/v1/events/stats"),
    ],
)
async def test_503_when_store_missing_get(method, path):
    async with client_for(build_app(None)) as ac:
        resp = await getattr(ac, method)(path, headers=AUTH)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Event store not available"


async def test_503_when_store_missing_create():
    body = {
        "category": "health",
        "source": "biohack",
        "action": "create",
        "event_type": "health.vitals.create",
    }
    async with client_for(build_app(None)) as ac:
        resp = await ac.post("/api/v1/events", json=body, headers=AUTH)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Event store not available"


# ============================================================ GET "" list_events


async def test_list_events_happy_echoes_and_forwards_filters():
    store = fake_store(query_events=[{"id": "a"}, {"id": "b"}])
    since = "2026-07-01T00:00:00+00:00"
    until = "2026-07-13T00:00:00+00:00"
    async with client_for(build_app(store)) as ac:
        resp = await ac.get(
            "/api/v1/events",
            params={
                "category": "health",
                "subcategory": "vitals",
                "source": "biohack",
                "event_type": "health.vitals.create",
                "since": since,
                "until": until,
                "limit": 50,
                "offset": 5,
            },
            headers=AUTH,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["limit"] == 50
    assert data["offset"] == 5
    kwargs = store.query_events.call_args.kwargs
    assert kwargs["category"] == "health"
    assert kwargs["subcategory"] == "vitals"
    assert kwargs["source"] == "biohack"
    assert kwargs["event_type"] == "health.vitals.create"
    assert kwargs["limit"] == 50
    assert kwargs["offset"] == 5
    assert kwargs["since"] == datetime.fromisoformat(since)
    assert kwargs["until"] == datetime.fromisoformat(until)


async def test_list_events_forwards_subcategory():
    """Ciclo 45: el filtro `subcategory` (soportado por EventStore.query_events
    y serializado por _event_to_dict) ahora se cablea end-to-end desde el
    endpoint — antes se descartaba en silencio pese a estar soportado."""
    store = fake_store(query_events=[{"id": "s1"}])
    async with client_for(build_app(store)) as ac:
        resp = await ac.get(
            "/api/v1/events", params={"subcategory": "sleep"}, headers=AUTH
        )
    assert resp.status_code == 200
    assert store.query_events.call_args.kwargs["subcategory"] == "sleep"


async def test_list_events_defaults_no_filters():
    store = fake_store(query_events=[])
    async with client_for(build_app(store)) as ac:
        resp = await ac.get("/api/v1/events", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"events": [], "count": 0, "limit": 100, "offset": 0}
    kwargs = store.query_events.call_args.kwargs
    assert kwargs["category"] is None and kwargs["since"] is None
    assert kwargs["subcategory"] is None


async def test_list_events_limit_over_cap_422():
    async with client_for(build_app(fake_store())) as ac:
        resp = await ac.get("/api/v1/events", params={"limit": 1001}, headers=AUTH)
    assert resp.status_code == 422


# ============================================================ GET /timeline/{date}


async def test_timeline_valid_date_with_categories():
    store = fake_store(get_timeline=[{"id": "x"}])
    async with client_for(build_app(store)) as ac:
        resp = await ac.get(
            "/api/v1/events/timeline/2026-07-13",
            params={"categories": "health,education"},
            headers=AUTH,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-07-13"
    assert data["count"] == 1
    kwargs = store.get_timeline.call_args.kwargs
    assert kwargs["date"] == datetime(2026, 7, 13)
    assert kwargs["categories"] == ["health", "education"]


async def test_timeline_valid_date_without_categories():
    store = fake_store(get_timeline=[])
    async with client_for(build_app(store)) as ac:
        resp = await ac.get("/api/v1/events/timeline/2026-07-13", headers=AUTH)
    assert resp.status_code == 200
    assert store.get_timeline.call_args.kwargs["categories"] is None


async def test_timeline_invalid_date_400():
    async with client_for(build_app(fake_store())) as ac:
        resp = await ac.get("/api/v1/events/timeline/not-a-date", headers=AUTH)
    assert resp.status_code == 400
    assert "Invalid date format" in resp.json()["detail"]


# ============================================================ GET /by-correlation/{id}


async def test_by_correlation_happy():
    cid = uuid4()
    store = fake_store(get_by_correlation=[{"id": "1"}, {"id": "2"}])
    async with client_for(build_app(store)) as ac:
        resp = await ac.get(f"/api/v1/events/by-correlation/{cid}", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["correlation_id"] == str(cid)
    assert data["count"] == 2
    store.get_by_correlation.assert_awaited_once()
    assert store.get_by_correlation.call_args.args[0] == cid


async def test_by_correlation_invalid_uuid_422():
    async with client_for(build_app(fake_store())) as ac:
        resp = await ac.get("/api/v1/events/by-correlation/not-a-uuid", headers=AUTH)
    assert resp.status_code == 422


# ============================================================ POST "" create_event


async def test_create_event_happy_forwards_all_fields():
    new_id = uuid4()
    store = fake_store(append_event=new_id)
    body = {
        "category": "health",
        "subcategory": "vitals",
        "source": "biohack",
        "action": "create",
        "event_type": "health.vitals.create",
        "payload": {"hr": 60},
        "metadata": {"device": "watch"},
        "tags": ["a", "b"],
    }
    async with client_for(build_app(store)) as ac:
        resp = await ac.post("/api/v1/events", json=body, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == str(new_id)
    assert data["status"] == "created"
    # timestamp is a valid ISO datetime
    datetime.fromisoformat(data["timestamp"])
    kwargs = store.append_event.call_args.kwargs
    assert kwargs["category"] == "health"
    assert kwargs["subcategory"] == "vitals"
    assert kwargs["source"] == "biohack"
    assert kwargs["event_metadata"] == {"device": "watch"}
    assert kwargs["tags"] == ["a", "b"]
    # Sin correlation_id en el body → se propaga None (canela/codking/auto-mat-ion).
    assert kwargs["correlation_id"] is None


async def test_create_event_forwards_correlation_id():
    # biohack/cybertools POST `VitalEvent.to_dict()` con `correlation_id` cuando
    # el emisor lo fija. Debe llegar a `append_event` para que la traza
    # `GET /events/by-correlation/{id}` encuentre el evento (Ciclo 43).
    cid = uuid4()
    store = fake_store(append_event=uuid4())
    body = {
        "category": "security",
        "source": "cybertools",
        "action": "analyze",
        "event_type": "security.alert",
        "correlation_id": str(cid),
    }
    async with client_for(build_app(store)) as ac:
        resp = await ac.post("/api/v1/events", json=body, headers=AUTH)
    assert resp.status_code == 200
    assert store.append_event.call_args.kwargs["correlation_id"] == cid


async def test_create_event_invalid_correlation_id_422():
    body = {
        "category": "health",
        "source": "biohack",
        "action": "create",
        "event_type": "health.vitals.create",
        "correlation_id": "not-a-uuid",
    }
    async with client_for(build_app(fake_store())) as ac:
        resp = await ac.post("/api/v1/events", json=body, headers=AUTH)
    assert resp.status_code == 422


async def test_create_event_response_matches_output_contract():
    # Contrato de SALIDA auditado en Ciclo 44: el `response_model`
    # `EventCreateResponse` fija exactamente {event_id, status, timestamp}.
    # biohack/cybertools leen `event_id` (UUID-string); canela/codking dependen
    # del shape. Ninguna clave extra debe filtrarse.
    new_id = uuid4()
    store = fake_store(append_event=new_id)
    body = {
        "category": "security",
        "source": "cybertools",
        "action": "analyze",
        "event_type": "security.alert",
    }
    async with client_for(build_app(store)) as ac:
        resp = await ac.post("/api/v1/events", json=body, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"event_id", "status", "timestamp"}
    # `event_id` es lo único que consumen biohack/cybertools → debe ser un UUID.
    assert UUID(data["event_id"]) == new_id
    assert data["status"] == "created"
    datetime.fromisoformat(data["timestamp"])


async def test_create_event_missing_required_field_422():
    body = {"category": "health", "source": "biohack"}  # missing action/event_type
    async with client_for(build_app(fake_store())) as ac:
        resp = await ac.post("/api/v1/events", json=body, headers=AUTH)
    assert resp.status_code == 422


# ============================================================ GET /stats


async def test_stats_happy_default_days():
    store = fake_store(get_stats={"total": 7})
    async with client_for(build_app(store)) as ac:
        resp = await ac.get("/api/v1/events/stats", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_days"] == 7
    assert data["stats"] == {"total": 7}
    # since ≈ now - 7 days, passed as kwarg
    since = store.get_stats.call_args.kwargs["since"]
    delta = datetime.now(timezone.utc) - since
    assert 6.9 < delta.days + delta.seconds / 86400 < 7.1


async def test_stats_custom_days():
    store = fake_store()
    async with client_for(build_app(store)) as ac:
        resp = await ac.get("/api/v1/events/stats", params={"days": 30}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["period_days"] == 30


# ============================================================ GET /categories (static)


async def test_categories_static_shape():
    async with client_for(build_app(None)) as ac:
        resp = await ac.get("/api/v1/events/categories", headers=AUTH)
    assert resp.status_code == 200
    cats = resp.json()["categories"]
    names = {c["name"] for c in cats}
    assert names == {"health", "education", "identity", "system"}
    health = next(c for c in cats if c["name"] == "health")
    assert "vitals" in health["subcategories"]


# ============================================================ auth


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/events"),
        ("get", "/api/v1/events/timeline/2026-07-13"),
        ("post", "/api/v1/events"),
        ("get", "/api/v1/events/stats"),
        ("get", "/api/v1/events/categories"),
    ],
)
async def test_requires_auth(method, path):
    async with client_for(build_app(fake_store())) as ac:
        resp = await getattr(ac, method)(path)
    assert resp.status_code in (401, 403)


async def test_invalid_key_rejected():
    async with client_for(build_app(fake_store())) as ac:
        resp = await ac.get("/api/v1/events", headers={"X-API-Key": "bogus"})
    assert resp.status_code == 401
