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
    # Cada entrada expone el contrato completo de ServiceStatus, incluida la
    # `version` que el dominio reporta en su health-check (Ciclo 42: antes se
    # capturaba en ServiceInfo pero /services nunca la devolvía).
    for entry in data["services"].values():
        assert "version" in entry


@pytest.mark.asyncio
async def test_services_status_key_set_matches_frontend_catalog(client):
    """Pin del CONTRATO cross-layer que consume el panel de Micelia.

    `GET /api/v1/health/services` serializa un set FIJO de claves de dominio
    (`app/api/v1/health.py:132` itera `["health","research","education","security"]`,
    los 4 dominios con sonda de salud en el registry — no los 6 internos, que
    incluyen `devtools`/`testlab` sin frontend).

    Consumidor VIVO: la página `/servicios` del panel (commit b7b5d9a) lee la
    salud de cada dominio por `registryKey` en `frontend/src/lib/services.ts`,
    tipado como la unión literal `'health'|'research'|'education'|'security'`.
    Si alguien renombra/elimina una clave en health.py:132 (p.ej. quita
    `"security"`), el badge de salud de ESE dominio (cybertools) quedaría
    silenciosamente en "sin sonda" en el panel, sin que ningún test lo cace:
    `test_services_status` solo comprueba presencia de `services`+`version`.

    Este pin rompe ante cualquier deriva del set y nombra el fichero frontend a
    actualizar en lockstep. El lado frontend ya está blindado por su propia
    unión de tipos (un typo en `registryKey` lo caza `tsc --noEmit`); juntos
    cierran el contrato por ambos extremos.
    """
    response = await client.get("/api/v1/health/services")
    assert response.status_code == 200
    served = set(response.json()["services"].keys())
    frontend_registry_keys = {"health", "research", "education", "security"}
    assert served == frontend_registry_keys, (
        "El set de claves de /health/services cambió respecto a lo que el panel "
        "lee en frontend/src/lib/services.ts (registryKey). Actualiza health.py:132 "
        "y services.ts en lockstep, o el badge de salud del dominio afectado morirá "
        f"en silencio. Servido={sorted(served)} Frontend={sorted(frontend_registry_keys)}"
    )
