"""
C104 — La infra expone redis-stack en :6380 porque ideacursi lo necesita para arrancar (DP-20).

Cadena descubierta ejerciendo (C103): el backend de ideacursi, al arrancar, hace `FT.CREATE`
(índice vectorial RediSearch) desde su `RedisVectorService`, cuyo default es
`redis://localhost:6380`. Con redis PLANO crashea (`ERR unknown command 'FT.CREATE'`); con
redis-stack (RediSearch) arranca. La imagen del compose YA es `redis/redis-stack` (trae
RediSearch), pero solo exponía :6379 → un ideacursi arrancado NATIVO (run-ecosystem.sh start +
docker-infra) no alcanzaba el vector en :6380 y no arrancaba. C104 añade el bind host :6380 →
el mismo redis-stack.

Este pin fija las dos mitades del contrato para que nadie "limpie" el :6380 creyéndolo de más:
  1. compose (Micelia): el servicio `redis` usa una imagen redis-stack Y expone :6380.
  2. cross-repo (ideacursi): su RedisVectorService default apunta a :6380 y hace FT.* (la razón
     por la que :6380 debe servir RediSearch). SKIP si ideacursi no está en el checkout.
"""

import re
from pathlib import Path

import pytest

_MICELIA = Path(__file__).resolve().parents[1]
_COMPOSE = _MICELIA / "docker-compose.yml"
_IDEACURSI_VECTOR = (
    _MICELIA.parent
    / "ideacursi-tool"
    / "backend"
    / "src"
    / "cache"
    / "services"
    / "redis-vector.service.js"
)


def _service_block(service: str) -> str:
    text = _COMPOSE.read_text(encoding="utf-8")
    m = re.search(rf"^  {re.escape(service)}:$(.*?)(?=^  [a-z_-]+:$)", text, re.M | re.S)
    assert m, f"no se encontró el servicio `{service}` en docker-compose.yml"
    return m.group(1)


def _redis_service_block() -> str:
    return _service_block("redis")


def test_compose_redis_is_redis_stack():
    """El servicio redis usa una imagen redis-stack (con RediSearch) — no un redis plano.
    Sin RediSearch, el FT.CREATE del boot de ideacursi falla."""
    block = _redis_service_block()
    assert re.search(r"image:\s*redis/redis-stack", block), (
        "el servicio `redis` dejó de usar una imagen redis-stack; el FT.CREATE del boot de "
        "ideacursi (índice vectorial) fallaría con 'unknown command'."
    )


def test_compose_redis_exposes_6380_for_ideacursi_vector():
    """El servicio redis expone :6380, el puerto donde el RedisVectorService de ideacursi
    (arrancado nativo) busca RediSearch. Mutación: quitar el bind → ideacursi nativo no
    arranca (ECONNREFUSED :6380 → FT.CREATE nunca corre)."""
    block = _redis_service_block()
    assert re.search(r'"6380:6379"', block), (
        "el servicio `redis` ya no expone :6380 → un ideacursi arrancado con "
        "run-ecosystem.sh start no alcanzaría su vector redis y crashearía en el boot (DP-20)."
    )


def test_ideacursi_vector_service_targets_6380_and_uses_redisearch():
    """Cross-repo: el porqué del :6380. El RedisVectorService de ideacursi default a
    `localhost:6380` y usa comandos RediSearch (FT.*). Si ideacursi cambia su puerto o deja de
    usar RediSearch, el bind :6380 de la infra podría revisarse."""
    if not _IDEACURSI_VECTOR.is_file():
        pytest.skip("repo hermano ideacursi-tool no presente; check cross-repo omitido.")
    text = _IDEACURSI_VECTOR.read_text(encoding="utf-8")
    assert re.search(r"redis://localhost:6380", text), (
        "ideacursi ya no default-ea su vector a :6380; el bind :6380 de la infra puede "
        "haber quedado huérfano — re-audita antes de tocarlo."
    )
    assert re.search(r"FT\.", text) or "createIndex" in text or "ft.create" in text.lower(), (
        "el RedisVectorService de ideacursi ya no usa RediSearch (FT.*); la exigencia de "
        "redis-stack podría haber cambiado."
    )


# =============================================================================
# DP-21(a) — la infra DEV usa nombres `micelia-*`, desacoplada del stack prod `deploy/`
# =============================================================================

# Servicios que `docker-infra` levanta (los que colisionaban con deploy/). Su SERVICE key no
# cambia (DNS interno intacto); su container_name sí, para no chocar con los `idm-*` de deploy.
_INFRA_SERVICES = ("postgres", "redis", "ollama")


def test_infra_containers_use_micelia_namespace_not_idm():
    """La infra que `docker-infra` levanta usa container_name `micelia-*`, NO `idm-*`. Con
    `idm-*` colisionaba con el stack de producción-local `deploy/` (mismos nombres) y bloqueaba
    recrear la redis dev con el bind :6380 (DP-21, C105→C106). Mutación: volver a `idm-postgres`
    → este pin muerde y recuerda la colisión."""
    for svc in _INFRA_SERVICES:
        block = _service_block(svc)
        m = re.search(r"container_name:\s*(\S+)", block)
        assert m, f"el servicio `{svc}` perdió su container_name"
        name = m.group(1)
        assert name == f"micelia-{svc}", (
            f"el servicio `{svc}` usa container_name '{name}', no 'micelia-{svc}'. Si es "
            f"'idm-{svc}' vuelve a colisionar con el stack prod `deploy/` (DP-21)."
        )


def test_infra_service_keys_unchanged_so_internal_dns_survives():
    """El rename es SOLO del container_name: los SERVICE keys (postgres/redis/ollama) siguen,
    porque el DNS interno del compose (`@postgres:5432`, `redis://redis:6379`, `ollama:11434`)
    depende de ellos, no del container_name. Este pin garantiza que no se renombró de más."""
    text = _COMPOSE.read_text(encoding="utf-8")
    for svc in _INFRA_SERVICES:
        assert re.search(rf"^  {svc}:$", text, re.M), (
            f"desapareció el SERVICE key `{svc}:` del compose → el DNS interno que lo referencia "
            f"(p.ej. postgresql://…@{svc}) se rompería. El rename debe tocar container_name, no "
            f"el service key."
        )


def test_compose_network_is_micelia_not_idm():
    """La red del compose de micelia es `micelia-network`, no `idm-network` — que colisionaba
    con la red del stack `deploy/` ('idm-network is being used' al intentar recrear, C105)."""
    text = _COMPOSE.read_text(encoding="utf-8")
    assert re.search(r"name:\s*micelia-network", text), (
        "la red del compose dejó de llamarse micelia-network."
    )
    assert not re.search(r"name:\s*idm-network", text), (
        "reapareció `idm-network` → colisiona con la red del stack prod `deploy/` (DP-21)."
    )
