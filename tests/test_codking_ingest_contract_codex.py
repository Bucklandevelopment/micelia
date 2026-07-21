"""
C100 — El contrato de INGEST de codking: un dominio PUSH-only, sin slot en el registry.

Anotado desde DP-12 (C76) / C84 y nunca pineado: **codking comparte :8000 con cybertools**,
así que NO tiene slot propio en el registry (Micelia no lo sondea por `/health`). Sus eventos
llegan por el **ingest** (`POST /api/v1/events`) con `source=codking`, un canal independiente
del PULL del registry (C92 pineó que PUSH y PULL son mecanismos independientes; esto pinea el
caso concreto de codking, que es PUSH puro).

Verificado por lectura de AMBOS lados (no asumido):
  * **Micelia (ingest):** `source` admite cualquier string; `_normalize_source` solo toca el
    legacy `idm-core→micelia`, así que `codking` se persiste literal. El registry declara 6
    slots (health/research/education/security/testlab) — codking NO está.
  * **codking (SDK hermano):** `integrations/vital_sdk/config.py` fija `service_name="codking"`
    y `client.py::publish_event` manda `source=self.config.service_name`, hace
    `resp.raise_for_status()` y devuelve `resp.json()` → depende de un 2xx + el SHAPE de la
    respuesta, no de campos concretos.

Los pins estáticos corren siempre; el e2e (ingest real → store) exige postgres (`require_postgres`).
Lectura read-only del repo hermano codking; SKIP si no está en el checkout.
"""

import re
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from app.events.store import _normalize_source
from app.services.service_registry import ServiceRegistry
from tests.conftest import TEST_API_KEY

_SOURCE = "codking"

_PROJECTS = Path(__file__).resolve().parents[2]
_CK_CONFIG = _PROJECTS / "codking" / "integrations" / "vital_sdk" / "config.py"
_CK_CLIENT = _PROJECTS / "codking" / "integrations" / "vital_sdk" / "client.py"

# Los 6 slots que el registry SÍ sondea (fuente: ServiceRegistry.HEALTH_ENDPOINTS).
_REGISTRY_SLOTS = {"health", "research", "education", "security", "testlab"}


# =============================================================================
# Estático — la asimetría (sin postgres, corre siempre)
# =============================================================================


def test_codking_is_not_a_registry_slot():
    """codking NO se sondea por el registry (comparte :8000 con cybertools, DP-12). El
    registry declara 6 slots y codking no es uno — es visible por PUSH, no por PULL."""
    endpoints = set(ServiceRegistry.HEALTH_ENDPOINTS)
    assert endpoints == _REGISTRY_SLOTS, (
        f"cambió el set de slots del registry: {endpoints} (esperado {_REGISTRY_SLOTS})"
    )
    assert "codking" not in endpoints, (
        "codking apareció como slot del registry; comparte :8000 con cybertools y debe "
        "seguir siendo PUSH-only (DP-12). Si de verdad tendrá slot, re-audita el puerto."
    )


def test_ingest_persists_codking_source_unnormalized():
    """El ingest persiste `source=codking` LITERAL: `_normalize_source` solo reescribe el
    legacy `idm-core→micelia`. Si codking se normalizara, sus eventos no serían consultables
    por `source=codking` y la traza del dominio se rompería en silencio."""
    assert _normalize_source("codking") == "codking", (
        "codking dejó de persistirse literal (¿se le añadió normalización?) → sus eventos "
        "no se encontrarían por source=codking."
    )
    # contraste: la ÚNICA normalización viva es idm-core→micelia (para no pinear en vacío).
    assert _normalize_source("idm-core") == "micelia"


# =============================================================================
# Cross-repo — el SDK de codking espera del ingest (SKIP si no está el checkout)
# =============================================================================


def test_codking_sdk_pushes_source_codking_and_depends_on_shape():
    """El SDK hermano de codking manda `source=codking` y hace `raise_for_status()` +
    `resp.json()` → el ingest de Micelia debe aceptar ese source y devolver un 2xx con un
    JSON dict. Pin cross-repo del contrato PUSH (como C82/C86)."""
    if not _CK_CONFIG.is_file() or not _CK_CLIENT.is_file():
        pytest.skip("repo hermano codking no presente; check cross-repo omitido.")

    config = _CK_CONFIG.read_text(encoding="utf-8")
    assert re.search(r'service_name:\s*str\s*=\s*"codking"', config), (
        "el SDK de codking ya no fija service_name='codking'; el source de sus eventos "
        "cambió → re-audita el contrato de ingest."
    )

    client = _CK_CLIENT.read_text(encoding="utf-8")
    assert "source=self.config.service_name" in client, (
        "codking ya no publica con source=service_name; el ingest recibiría otro source."
    )
    assert "raise_for_status()" in client and "resp.json()" in client, (
        "codking dejó de depender de un 2xx + JSON dict; el shape del contrato de salida "
        "(EventCreateResponse) cambió de expectativa."
    )


# =============================================================================
# e2e — el ingest real persiste codking, PUSH-only (exige postgres)
# =============================================================================


async def _post_event(app, **fields) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": TEST_API_KEY},
    ) as raw:
        return await raw.post("/api/v1/events", json=fields)


async def test_codking_event_ingests_and_is_queryable_push_only(
    require_postgres, no_domain_probes
):
    """La asimetría en vivo: un evento `source=codking` entra por el ingest, se persiste y es
    consultable por source — mientras codking sigue SIN slot en el registry (PUSH sí, PULL no).
    """
    from app.main import app

    async with app.router.lifespan_context(app):
        store = app.state.event_store
        assert store is not None

        before = await store.query_events(
            source=_SOURCE, event_type="threat.detected", limit=1000
        )
        resp = await _post_event(
            app,
            category="security",
            source=_SOURCE,
            action="analyze",
            event_type="threat.detected",
            payload={"score": 0.98, "label": "malware"},
            tags=["codking"],
        )
        assert resp.status_code in (200, 201), resp.text
        assert "event_id" in resp.json()

        after = await store.query_events(
            source=_SOURCE, event_type="threat.detected", limit=1000
        )
        assert len(after) == len(before) + 1, "el evento de codking no se persistió"
        assert after[0]["source"] == _SOURCE, "codking se persistió con otro source"

        # …y sigue sin slot en el registry vivo: PUSH funcionó, PULL no aplica.
        registry = app.state.service_registry
        assert "codking" not in registry.services, (
            "codking apareció en el registry vivo; debe seguir siendo PUSH-only (DP-12)."
        )


async def test_ingest_accepts_codking_even_when_ai_engine_disabled(
    require_postgres, no_domain_probes, monkeypatch
):
    """`settings.codking_enabled` gobierna el MOTOR de IA (ai.py), no el ingest de eventos.
    Con el motor DESACTIVADO, un evento `source=codking` se sigue aceptando → los dos
    mecanismos son independientes (eco de C92). Si alguien cableara el ingest al flag, esto
    se rompería."""
    from app.core.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "codking_enabled", False, raising=False)

    async with app.router.lifespan_context(app):
        assert app.state.event_store is not None
        resp = await _post_event(
            app,
            category="security",
            source=_SOURCE,
            action="analyze",
            event_type="classification.completed",
            payload={"label": "benign"},
        )
        assert resp.status_code in (200, 201), (
            f"el ingest rechazó a codking con el motor de IA off ({resp.status_code}); "
            f"el flag codking_enabled no debe gatear el ingest: {resp.text}"
        )
