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


def _redis_service_block() -> str:
    text = _COMPOSE.read_text(encoding="utf-8")
    m = re.search(r"^  redis:$(.*?)(?=^  [a-z_-]+:$)", text, re.M | re.S)
    assert m, "no se encontró el servicio `redis` en docker-compose.yml"
    return m.group(1)


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
