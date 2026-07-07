"""
Tests for root endpoint.
"""

import pytest


@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Micelia"
    assert data["version"] == "0.1.0"
    assert data["status"] == "operational"
