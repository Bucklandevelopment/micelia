"""
Tripwire de coherencia del CONTRATO DE DEPLOY del gateway.

Contexto (Ciclo 73): la prioridad #6 (deploy) llevaba 72 ciclos sin tocarse. Al
ejercerla por primera vez —construir la imagen del gateway con `podman build`
(build-only, arm64 nativo)— queda claro que el puerto y la ruta de health del
gateway viven DUPLICADOS en tres artefactos de deploy, sin un solo guard que los
ate al código:

  * CÓDIGO — `app/core/config.py`  → `gateway_port: int = 8888` (el default real
    que uvicorn bindea) y la ruta de health que el gateway sirve
    (`app/api/v1/health.py` `APIRouter(prefix="/health")` + `@router.get("")`,
    montado en `app/main.py` bajo `prefix="/api/v1"` → `/api/v1/health`).
  * `Dockerfile` — `EXPOSE 8888` + `HEALTHCHECK ... curl -f
    http://localhost:8888/api/v1/health`.
  * `docker-compose.yml` — servicio `idm-core`: env `GATEWAY_PORT=8888`, mapeo
    de puertos `"8888:8888"` y healthcheck `curl -f
    http://localhost:8888/api/v1/health`.

Por qué es un acoplamiento REAL con lector vivo (no un pin tautológico): la imagen
que HOY se construye ejecuta ese HEALTHCHECK. Si alguien cambia `gateway_port` a
otro puerto en `config.py` (o mueve la ruta de health) sin actualizar el Dockerfile
y el compose, el healthcheck del contenedor haría `curl` a un puerto/ruta muerto →
el contenedor quedaría PERPETUAMENTE `unhealthy`, `depends_on: condition:
service_healthy` no arrancaría los dominios, y el deploy se rompería EN SILENCIO
(ningún test lo caza: la suite nunca lee los artefactos de deploy, y `make verify`
no construye la imagen). Este pin —que `make verify` sí ejecuta— es el único sitio
donde ese drift se caza sin un build de contenedor.

Complementa a `test_main_boot_codex.py` (que ya prueba que `/api/v1/health`
responde de verdad vía TestClient) y a `test_health.py`: aquellos garantizan que la
RUTA sirve; este garantiza que los artefactos de deploy apuntan EXACTAMENTE a esa
ruta y a ese puerto. Juntos cierran la cadena código ↔ imagen ↔ compose.

NOTA de campo (C73): al construir la imagen con `podman build` se observó que
podman usa formato OCI por default y `HEALTHCHECK is not supported for OCI image
format and will be ignored`. Es decir: bajo el `podman-compose` que usan TODOS los
targets del Makefile, el HEALTHCHECK del Dockerfile se IGNORA y el que realmente
gobierna `depends_on: condition: service_healthy` es el healthcheck del PROPIO
compose. Por eso el pin del healthcheck de compose (abajo) es el load-bearing: es la
única sonda que de verdad decide si los dominios arrancan.

Solo lee ficheros del propio repo (código + Dockerfile + compose, cero secretos).
Test-only; no toca `app/`, infra, `.env` ni repos hermanos.
"""

import re
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parent.parent
_CONFIG = _REPO / "app" / "core" / "config.py"
_HEALTH = _REPO / "app" / "api" / "v1" / "health.py"
_MAIN = _REPO / "app" / "main.py"
_DOCKERFILE = _REPO / "Dockerfile"
_ENTRYPOINT = _REPO / "scripts" / "entrypoint.sh"
_COMPOSE = _REPO / "docker-compose.yml"

# Nombre del servicio del gateway en docker-compose.yml. `idm-core` se mantiene por
# retrocompat (el rebrand conserva `idm` como alias; ver PLAN_MICELIA_v0 §1.6). Si el
# servicio se renombra a `micelia-core`, actualiza esta constante Y el fallback de
# `make docker-logs`.
_GATEWAY_SERVICE = "idm-core"


# --------------------------------------------------------------------------- #
# Parsers del CÓDIGO (la fuente de verdad del puerto y la ruta de health).
# --------------------------------------------------------------------------- #
def _code_gateway_port() -> int:
    """Default de `gateway_port` en app/core/config.py."""
    text = _CONFIG.read_text(encoding="utf-8")
    m = re.search(r"gateway_port:\s*int\s*=\s*(\d+)", text)
    assert m, "no se encontró el default `gateway_port: int = ...` en config.py"
    return int(m.group(1))


def _code_health_path() -> str:
    """
    Ruta completa de health que el gateway sirve, derivada del CÓDIGO:
    montaje de main.py (`prefix=`) + prefix del router de health + el path del
    `@router.get(...)` del endpoint raíz de health.
    """
    health_text = _HEALTH.read_text(encoding="utf-8")
    router_prefix = re.search(r'APIRouter\(prefix="([^"]+)"', health_text)
    assert router_prefix, "no se encontró `APIRouter(prefix=...)` en health.py"

    # El endpoint raíz de health es el `@router.get("")` (los demás son sub-rutas).
    root_get = re.search(r'@router\.get\((["\'])(.*?)\1\)', health_text)
    assert root_get, "no se encontró el primer `@router.get(...)` en health.py"
    endpoint_path = root_get.group(2)  # "" para el endpoint raíz

    main_text = _MAIN.read_text(encoding="utf-8")
    mount = re.search(
        r'include_router\(\s*health\.router\s*,\s*prefix="([^"]+)"', main_text
    )
    assert mount, "no se encontró el montaje de health.router con prefix en main.py"

    return f"{mount.group(1)}{router_prefix.group(1)}{endpoint_path}"


# --------------------------------------------------------------------------- #
# Parsers de los ARTEFACTOS DE DEPLOY.
# --------------------------------------------------------------------------- #
def _dockerfile() -> dict[str, object]:
    text = _DOCKERFILE.read_text(encoding="utf-8")
    expose = re.search(r"^EXPOSE\s+(\d+)", text, re.MULTILINE)
    hc = re.search(r"curl\s+-f\s+http://localhost:(\d+)(\S*?)(?:\s|\|\|)", text)
    assert expose, "no se encontró `EXPOSE <puerto>` en el Dockerfile"
    assert hc, "no se encontró el `curl -f http://localhost:...` del HEALTHCHECK"
    return {"expose": int(expose.group(1)), "hc_port": int(hc.group(1)), "hc_path": hc.group(2)}


def _entrypoint_default_port() -> int:
    text = _ENTRYPOINT.read_text(encoding="utf-8")
    m = re.search(r'GATEWAY_PORT="\$\{GATEWAY_PORT:-(\d+)\}"', text)
    assert m, "no se encontró el default `GATEWAY_PORT:-<puerto>` en entrypoint.sh"
    return int(m.group(1))


def _compose_gateway() -> dict[str, object]:
    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    svc = data["services"][_GATEWAY_SERVICE]

    # env: GATEWAY_PORT (la lista es "KEY=VALUE").
    env_port = None
    for item in svc.get("environment", []):
        if isinstance(item, str) and item.startswith("GATEWAY_PORT="):
            env_port = int(item.split("=", 1)[1])
    assert env_port is not None, "el servicio del gateway no define GATEWAY_PORT en compose"

    # ports: "HOST:CONTAINER".
    host_port, container_port = svc["ports"][0].split(":")

    # healthcheck: la URL del curl.
    hc_cmd = " ".join(svc["healthcheck"]["test"])
    hc = re.search(r"http://localhost:(\d+)(\S*)", hc_cmd)
    assert hc, "no se encontró la URL del healthcheck del gateway en compose"

    return {
        "env_port": env_port,
        "host_port": int(host_port),
        "container_port": int(container_port),
        "hc_port": int(hc.group(1)),
        "hc_path": hc.group(2),
    }


# --------------------------------------------------------------------------- #
# Guards anti-vacío: si un parser deja de encontrar su patrón, el pin pasaría en
# vacío. Estos tests fijan valores conocidos hoy para que un parser roto se note.
# --------------------------------------------------------------------------- #
def test_deploy_artifacts_exist():
    for p in (_CONFIG, _HEALTH, _MAIN, _DOCKERFILE, _ENTRYPOINT, _COMPOSE):
        assert p.is_file(), f"falta un artefacto del contrato de deploy: {p}"


def test_parsers_are_not_vacuously_empty():
    assert _code_gateway_port() == 8888, "¿cambió el default de gateway_port?"
    assert _code_health_path() == "/api/v1/health", "¿se movió la ruta de health?"
    assert _dockerfile()["expose"] == 8888
    assert _entrypoint_default_port() == 8888
    assert _compose_gateway()["container_port"] == 8888


# --------------------------------------------------------------------------- #
# El pin real: todo el puerto del gateway, atado al default del CÓDIGO.
# --------------------------------------------------------------------------- #
def test_gateway_port_consistent_code_dockerfile_compose():
    """
    El puerto que el gateway bindea (`gateway_port` en config.py) debe coincidir con
    el EXPOSE/HEALTHCHECK del Dockerfile, el default del entrypoint y el
    GATEWAY_PORT/ports/healthcheck del servicio en compose.

    Mutación: cambia `gateway_port: int = 8888` a `8900` en config.py sin tocar el
    Dockerfile → este test falla nombrando ambos. El contenedor real quedaría
    `unhealthy` porque el HEALTHCHECK curl-earía :8888 mientras uvicorn escucha :8900.
    """
    code = _code_gateway_port()
    df = _dockerfile()
    comp = _compose_gateway()
    ep = _entrypoint_default_port()

    mismatches = {
        "config.gateway_port": code,
        "Dockerfile EXPOSE": df["expose"],
        "Dockerfile HEALTHCHECK port": df["hc_port"],
        "entrypoint.sh GATEWAY_PORT default": ep,
        "compose GATEWAY_PORT env": comp["env_port"],
        "compose container port": comp["container_port"],
        "compose host port": comp["host_port"],
        "compose HEALTHCHECK port": comp["hc_port"],
    }
    distinct = set(mismatches.values())
    assert distinct == {code}, (
        f"DRIFT del puerto del gateway: se esperaba :{code} (default de "
        f"config.gateway_port) en todos los artefactos de deploy, pero hay valores "
        f"distintos: {mismatches}. Actualiza código + Dockerfile + compose en lockstep."
    )


def test_healthcheck_path_matches_served_route():
    """
    La ruta que el HEALTHCHECK del contenedor consulta debe ser EXACTAMENTE la que el
    gateway sirve (derivada del código: montaje + prefix del router + path del get).

    Mutación: cambia el prefix del router de health (`/health` → `/healthz`) en
    health.py sin tocar el Dockerfile → falla. El contenedor curl-earía /api/v1/health
    (404) y quedaría `unhealthy` para siempre pese a que el gateway arranca bien.
    """
    served = _code_health_path()
    df_path = _dockerfile()["hc_path"]
    comp_path = _compose_gateway()["hc_path"]
    assert df_path == served, (
        f"DRIFT: el HEALTHCHECK del Dockerfile consulta '{df_path}' pero el gateway "
        f"sirve health en '{served}' (app/api/v1/health.py + montaje en main.py). "
        f"El contenedor quedaría unhealthy. Actualiza el Dockerfile."
    )
    assert comp_path == served, (
        f"DRIFT: el healthcheck de compose consulta '{comp_path}' pero el gateway "
        f"sirve health en '{served}'. Actualiza docker-compose.yml."
    )
