"""
Tests for health endpoints.

Health endpoints are public (no API key required) since they are used
by load balancers and monitoring systems.
"""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_liveness_check(client):
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_check(client):
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "not_ready")


@pytest.mark.asyncio
async def test_services_status(client):
    response = await client.get("/api/v1/health/services")
    assert response.status_code == 200
    data = response.json()
    assert "services" in data
