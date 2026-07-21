"""
C114 — E2E cross-proyecto: DOS dominios registrándose y latiendo contra el gateway A LA VEZ,
con el Event Store persistiendo AMBOS de forma independiente.

Los guards previos pinean el contrato de UN dominio: register→store (C86), heartbeat→store
(C88), pull (C90), cross PUSH/PULL de un dominio (C92), ingest codking (C100). Lo que NINGUNO
cubre es la COEXISTENCIA: varios dominios empujando concurrentemente al mismo store, cada uno
persistido y consultable por su `source` sin contaminarse entre sí. Ese es el eslabón que este
módulo cierra.

Método (repetible, no una verificación manual): se arranca el LIFESPAN REAL del gateway (store
real que `require_postgres` garantiza) y se conducen DOS clientes SDK REALES —el mismo código
que los dominios vendorizan— con `source` distinto (`cybertools`, `canela`), cada uno hablando
con el gateway por ASGITransport (in-process, sin bindear puerto). `register()`+`heartbeat()` de
ambos se lanzan CONCURRENTEMENTE (`asyncio.gather`). El store es append-only y persiste; se
cuenta el DELTA por source (aislado de corridas previas). `no_domain_probes` mantiene los
sondeos del registry herméticos.
"""

import asyncio

import httpx
import pytest
from httpx import ASGITransport

from tests.conftest import TEST_API_KEY

pytestmark = pytest.mark.asyncio

_SOURCES = ("cybertools", "canela")


def _sdk_client(app, source: str, version: str = "1.0.0"):
    """IdmServiceClient REAL con `source` dado, hablando con `app` in-process (ASGITransport)."""
    from app.sdk.client import IdmServiceClient

    client = IdmServiceClient(
        service_name=source,
        port=8000,
        category="security" if source == "cybertools" else "research",
        micelia_url="http://test",
        api_key=TEST_API_KEY,
        version=version,
        capabilities=["cap-a", "cap-b"],
        heartbeat_interval=0,  # sin loop de fondo; el test controla el ciclo
    )
    client._http_client = httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": TEST_API_KEY},
    )
    return client


async def _count(store, source: str, event_type: str) -> int:
    return len(await store.query_events(source=source, event_type=event_type, limit=1000))


async def test_two_domains_register_and_heartbeat_concurrently(
    require_postgres, no_domain_probes
):
    """cybertools y canela se registran y latean CONCURRENTEMENTE contra el mismo gateway;
    el store persiste los 4 eventos (2 register + 2 heartbeat), cada uno bajo su propio source,
    sin cruzarse. El delta por (source, event_type) es exactamente +1."""
    from app.main import app

    async with app.router.lifespan_context(app):
        store = app.state.event_store
        assert store is not None

        before = {
            (src, et): await _count(store, src, et)
            for src in _SOURCES
            for et in ("service.registered", "service.heartbeat")
        }

        c1 = _sdk_client(app, "cybertools")
        c2 = _sdk_client(app, "canela")
        try:
            # los 4 push a la vez: dos dominios, register + heartbeat, concurrentes.
            results = await asyncio.gather(
                c1.register(), c2.register(), c1.heartbeat(), c2.heartbeat()
            )
        finally:
            await c1._http_client.aclose()
            await c2._http_client.aclose()

        assert all(results), f"algún push falló: {results}"

        # cada (source, event_type) creció EXACTAMENTE en 1 → ambos dominios persistieron,
        # independientes y sin contaminación cruzada.
        for src in _SOURCES:
            for et in ("service.registered", "service.heartbeat"):
                after = await _count(store, src, et)
                assert after == before[(src, et)] + 1, (
                    f"delta inesperado para ({src}, {et}): {before[(src, et)]}→{after}"
                )

        # el evento más reciente de cada source lleva SU source (no el del otro).
        for src in _SOURCES:
            newest = (await store.query_events(
                source=src, event_type="service.registered", limit=1
            ))[0]
            assert newest["source"] == src


async def test_store_query_by_source_isolates_domains(
    require_postgres, no_domain_probes
):
    """La consulta por `source` aísla los dominios: el evento que registra cada uno se recupera
    bajo SU source, no el del otro. Se usa una `version` única por corrida (tag) para mirar SOLO
    los eventos de ESTE test (el store es append-only y acumula de corridas previas) → robusto y
    muerde si el store colisiona los sources (el evento de canela aparecería bajo cybertools y el
    más reciente de canela no llevaría el tag)."""
    import uuid

    from app.main import app

    tag = uuid.uuid4().hex[:12]

    async with app.router.lifespan_context(app):
        store = app.state.event_store
        c1 = _sdk_client(app, "cybertools", version=tag)
        c2 = _sdk_client(app, "canela", version=tag)
        try:
            await asyncio.gather(c1.register(), c2.register())
        finally:
            await c1._http_client.aclose()
            await c2._http_client.aclose()

        for src in _SOURCES:
            newest = (await store.query_events(
                source=src, event_type="service.registered", limit=1
            ))[0]
            assert newest["source"] == src
            assert newest["payload"]["version"] == tag, (
                f"el evento recién registrado de {src} no aparece bajo {src} con el tag de esta "
                f"corrida → ¿el store cruzó los sources?"
            )
