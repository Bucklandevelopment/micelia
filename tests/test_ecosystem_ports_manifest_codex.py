"""
Tripwire que ancla el mapa de puertos del ecosistema a su FUENTE DE VERDAD declarada.

Contexto (Ciclo 76, cierre de DP-12): el mapa de puertos vivía triplicado —tabla
`SERVICES` de `scripts/run-ecosystem.sh`, defaults de `frontend/src/lib/services.ts`,
y `frontend/.env.local.example`— y los pins de C72 (`test_ecosystem_ports_codex.py`)
solo impedían el DRIFT entre esas copias por pares, sin un origen autoritativo. C76
introduce `scripts/ecosystem-ports.json` como la fuente declarada y este test fuerza
que las 3 copias de runtime DERIVEN de ella (topología en estrella):

  * launcher: cada servicio con `launcher_id` en el manifest debe bindear su `port` en
    la tabla SERVICES de run-ecosystem.sh.
  * hub: cada servicio con `hub_card` debe tener, en services.ts, el default
    `http://localhost:<port><hub_url_suffix>` para esa tarjeta.
  * env-template: la misma URL debe estar documentada en .env.local.example para la
    var `NEXT_PUBLIC_<CARD>_URL`.

DECISIÓN documentada en el propio manifest: NO se consolida en un loader único de
runtime (bash/TS/dotenv piden formatos nativos distintos; unificar exigiría jq/codegen
y tocaría 3 runtimes sin runner de frontend que lo valide). El manifest + estos pins
dan "una sola fuente declarada, drift imposible" a coste de runtime cero. Editar el
mapa = cambiar el JSON primero; el test señala qué espejo actualizar.

Complementa (no reemplaza) a `test_ecosystem_ports_codex.py`, que pinea las copias
entre sí; juntos forman la estrella + los pares. Solo lee ficheros del repo (JSON +
launcher + services.ts + .env.local.example, cero secretos). Test-only; no toca
`app/`, infra, `.env` real ni repos hermanos.
"""

import json
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_MANIFEST = _REPO / "scripts" / "ecosystem-ports.json"
_LAUNCHER = _REPO / "scripts" / "run-ecosystem.sh"
_SERVICES_TS = _REPO / "frontend" / "src" / "lib" / "services.ts"
_ENV_EXAMPLE = _REPO / "frontend" / ".env.local.example"


# --------------------------------------------------------------------------- #
# La FUENTE DE VERDAD.
# --------------------------------------------------------------------------- #
def _manifest() -> dict:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))["services"]


# --------------------------------------------------------------------------- #
# Parsers de las 3 copias de runtime (mismos patrones que test_ecosystem_ports).
# --------------------------------------------------------------------------- #
def _launcher_ports() -> dict[str, int]:
    text = _LAUNCHER.read_text(encoding="utf-8")
    ports: dict[str, int] = {}
    for m in re.finditer(r"^([a-z0-9-]+)\|[^|\n]*\|[^|\n]*\|(\d+)\|", text, re.MULTILINE):
        ports[m.group(1)] = int(m.group(2))
    return ports


def _hub_default_urls() -> dict[str, str]:
    """id de tarjeta -> URL del default `http://localhost:...` en services.ts."""
    text = _SERVICES_TS.read_text(encoding="utf-8")
    urls: dict[str, str] = {}
    for m in re.finditer(r"id:\s*'([^']+)'[\s\S]*?\|\|\s*'([^']+)'", text):
        urls.setdefault(m.group(1), m.group(2))
    return urls


def _env_example_urls() -> dict[str, str]:
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"^(NEXT_PUBLIC_\w+)=(\S+)$", text, re.MULTILINE)
    }


def _expected_hub_url(spec: dict) -> str:
    return f"http://localhost:{spec['port']}{spec.get('hub_url_suffix', '')}"


# --------------------------------------------------------------------------- #
# Guards anti-vacío.
# --------------------------------------------------------------------------- #
def test_artifacts_exist():
    for p in (_MANIFEST, _LAUNCHER, _SERVICES_TS, _ENV_EXAMPLE):
        assert p.is_file(), f"falta un artefacto del mapa de puertos: {p}"


def test_manifest_is_not_vacuously_empty():
    services = _manifest()
    # Conjunto conocido hoy: si el manifest se vacía o se renombra, se nota.
    assert {"biohack-fe", "canela", "cybertools", "codking-vis"} <= set(services)
    for name, spec in services.items():
        assert isinstance(spec.get("port"), int), f"'{name}' sin puerto entero"
        assert spec.get("launcher_id") or spec.get("hub_card"), (
            f"'{name}' no es ni servicio del launcher ni tarjeta del hub: no pinta nada"
        )


# --------------------------------------------------------------------------- #
# Los pins en estrella: cada copia de runtime deriva del manifest.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", sorted(_manifest().keys()))
def test_launcher_binds_manifest_port(name: str):
    """
    Cada servicio con `launcher_id` en el manifest debe bindear ese `port` en la tabla
    SERVICES del launcher.

    Mutación: cambia `canela|...|8501` a `8502` en run-ecosystem.sh sin tocar el JSON →
    falla nombrando el manifest como fuente de verdad.
    """
    spec = _manifest()[name]
    launcher_id = spec.get("launcher_id")
    if not launcher_id:
        pytest.skip(f"'{name}' no lo arranca el launcher (hub-only)")
    launcher = _launcher_ports()
    assert launcher_id in launcher, (
        f"el manifest declara el servicio '{launcher_id}' pero no está en la tabla "
        f"SERVICES de run-ecosystem.sh. Añádelo o corrige el manifest."
    )
    assert launcher[launcher_id] == spec["port"], (
        f"DRIFT: el manifest (scripts/ecosystem-ports.json) declara '{name}' en "
        f":{spec['port']} pero run-ecosystem.sh bindea '{launcher_id}' en "
        f":{launcher[launcher_id]}. El manifest es la fuente de verdad: alinea el launcher."
    )


@pytest.mark.parametrize("name", sorted(_manifest().keys()))
def test_hub_card_url_matches_manifest(name: str):
    """
    Cada servicio con `hub_card` debe tener en services.ts el default
    `http://localhost:<port><hub_url_suffix>` para esa tarjeta.

    Mutación: cambia el manifest de codking a :3011 sin tocar services.ts → falla; o al
    revés. El botón "Abrir…" del hub caería en un puerto muerto si divergen.
    """
    spec = _manifest()[name]
    card = spec.get("hub_card")
    if not card:
        pytest.skip(f"'{name}' no tiene tarjeta en el hub")
    hub = _hub_default_urls()
    assert card in hub, (
        f"el manifest declara la tarjeta de hub '{card}' pero no está en services.ts"
    )
    assert hub[card] == _expected_hub_url(spec), (
        f"DRIFT: el manifest declara la tarjeta '{card}' → {_expected_hub_url(spec)} "
        f"pero services.ts usa '{hub[card]}'. Alinea services.ts con el manifest."
    )


@pytest.mark.parametrize("name", sorted(_manifest().keys()))
def test_env_example_url_matches_manifest(name: str):
    """
    Para cada tarjeta del hub, la var `NEXT_PUBLIC_<CARD>_URL` del .env.local.example
    debe documentar la misma URL que declara el manifest.

    Mutación: cambia NEXT_PUBLIC_CANELA_URL en el .env.local.example sin tocar el JSON
    → falla. El template que un dev copia mentiría respecto a la fuente de verdad.
    """
    spec = _manifest()[name]
    card = spec.get("hub_card")
    if not card:
        pytest.skip(f"'{name}' no tiene tarjeta en el hub")
    var = f"NEXT_PUBLIC_{card.upper()}_URL"
    env = _env_example_urls()
    assert var in env, (
        f"el manifest declara la tarjeta '{card}' pero {var} no está en "
        f".env.local.example. Añádela o el template queda cojo."
    )
    assert env[var] == _expected_hub_url(spec), (
        f"DRIFT: el manifest declara {var} → {_expected_hub_url(spec)} pero "
        f".env.local.example documenta '{env[var]}'. Alinea el template con el manifest."
    )
