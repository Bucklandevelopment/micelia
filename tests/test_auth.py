"""
Tests for global API key authentication.

Verifies that protected endpoints require valid API keys
and that health endpoints remain public.
"""

import pytest


@pytest.mark.asyncio
async def test_events_requires_auth(client):
    """Events endpoint should reject requests without API key."""
    response = await client.get("/api/v1/events")
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"] or "API key required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_events_rejects_invalid_key(client):
    """Events endpoint should reject invalid API keys."""
    response = await client.get(
        "/api/v1/events",
        headers={"X-API-Key": "invalid-key-12345"},
    )
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_events_accepts_valid_key(client, auth_headers):
    """Events endpoint should accept valid API keys (returns 503 because event store is None)."""
    response = await client.get("/api/v1/events", headers=auth_headers)
    # 503 because event store is mocked as None, but auth passed
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_ai_status_requires_auth(client):
    """AI status endpoint should require auth."""
    response = await client.get("/api/v1/ai/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ai_status_with_auth(client, auth_headers):
    """AI status endpoint should work with valid auth."""
    response = await client.get("/api/v1/ai/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "ollama" in data
    assert "codking" in data


@pytest.mark.asyncio
async def test_energy_status_requires_auth(client):
    """Energy status endpoint should require auth."""
    response = await client.get("/api/v1/energy/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_frangels_requires_auth(client):
    """Frangels providers endpoint should require auth."""
    response = await client.get("/api/v1/frangels/providers")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_gateway_requires_auth(client):
    """Gateway proxy endpoints should require auth."""
    response = await client.get("/api/v1/gateway/health/test")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_does_not_require_auth(client):
    """Health endpoints should remain public."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_event_categories_requires_auth(client):
    """Event categories endpoint should require auth."""
    response = await client.get("/api/v1/events/categories")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_event_categories_with_auth(client, auth_headers):
    """Event categories endpoint should work with valid auth."""
    response = await client.get("/api/v1/events/categories", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
