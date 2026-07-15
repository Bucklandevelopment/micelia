"""
Check de coherencia CROSS-REPO automatizado (DP-11, cerrada Ciclo 77).

DP-11 nació en C65/C66: los README/Dockerfile de los dominios pueden desincronizarse
del puerto que Micelia asume para enrutar hacia ellos, y la suite de Micelia NUNCA
lee los repos hermanos, así que ese drift es invisible hasta que el arranque integrado
falla. C66 codificó la forma más BARATA (pinear `HEALTH_ENDPOINTS` contra el contrato
auditado, dentro de Micelia); el check cross-repo REAL —comparar lo que Micelia asume
contra lo que cada dominio DECLARA en su propio Dockerfile— quedó latente como DP-11.

Este test lo cierra. Para cada dominio, Micelia declara el puerto interno al que el
gateway enruta en `docker-compose.yml` (`*_SERVICE_URL=http://<host>:<port>`), y ese
host es el nombre del servicio de compose, cuyo `build.context`/`dockerfile` apunta al
Dockerfile del repo hermano. El test resuelve ese Dockerfile y asserta que el puerto
que el dominio EXPONE/BINDEA (EXPOSE + `--port` del CMD) == el puerto que Micelia
enruta. Si un dominio bump-ea su puerto (p.ej. biohack 8080→8000 en su Dockerfile) sin
que Micelia actualice `HEALTH_SERVICE_URL`, el gateway enrutaría a un puerto muerto en
la red del compose → `depends_on: service_healthy` nunca se cumpliría y el dominio
quedaría inalcanzable, EN SILENCIO. Este pin —que `make verify` ejecuta— es el único
sitio donde ese drift cross-repo se caza sin arrancar el ecosistema.

DISEÑO local-first (M1, ecosistema co-checkout): el test LEE los repos hermanos
(read-only, permitido para auditar coherencia; ver C68) y **SKIP-ea con mensaje** cada
dominio cuyo Dockerfile no esté presente (checkout aislado de Micelia / CI sin los
hermanos) → nunca produce falsos fallos; solo asserta cuando el hermano existe. Todo
se DERIVA del compose (URLs + build context), no se hardcodea el path de cada repo.

Solo lectura de ficheros de deploy (compose + Dockerfiles de dominio, cero secretos).
Test-only; no modifica `app/`, infra, `.env` ni repos hermanos.
"""

import re
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parent.parent
_COMPOSE = _REPO / "docker-compose.yml"
_CONFIG = _REPO / "app" / "core" / "config.py"

# *_SERVICE_URL de compose -> default equivalente en config.py (misma semántica de
# puerto; compose usa DNS de red, config.py usa localhost, pero el PUERTO es el mismo).
_URL_TO_CONFIG_DEFAULT = {
    "HEALTH_SERVICE_URL": "health_service_url",
    "RESEARCH_SERVICE_URL": "research_service_url",
    "EDUCATION_SERVICE_URL": "education_service_url",
    "SECURITY_SERVICE_URL": "security_service_url",
}


def _compose() -> dict:
    return yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))


def _service_url_targets() -> dict[str, tuple[str, int]]:
    """*_SERVICE_URL -> (host, port), leído del env del servicio idm-core."""
    env = _compose()["services"]["idm-core"]["environment"]
    out: dict[str, tuple[str, int]] = {}
    for item in env:
        if not isinstance(item, str):
            continue
        m = re.match(r"(\w+_SERVICE_URL)=http://([^:/]+):(\d+)", item)
        if m:
            out[m.group(1)] = (m.group(2), int(m.group(3)))
    return out


def _sibling_dockerfile(host: str) -> Path | None:
    """Resuelve el Dockerfile del repo hermano desde el build context del servicio."""
    svc = _compose()["services"].get(host)
    if not svc:
        return None
    build = svc.get("build")
    if not isinstance(build, dict):
        return None
    context = build.get("context")
    dockerfile = build.get("dockerfile", "Dockerfile")
    if not context:
        return None
    # context es relativo a la ubicación del compose (= _REPO).
    return (_REPO / context / dockerfile).resolve()


def _dockerfile_ports(path: Path) -> dict[str, int]:
    """Puertos que el Dockerfile declara: EXPOSE y, si existe, `--port N` del CMD."""
    text = path.read_text(encoding="utf-8")
    ports: dict[str, int] = {}
    expose = re.search(r"^EXPOSE\s+(\d+)", text, re.MULTILINE)
    if expose:
        ports["EXPOSE"] = int(expose.group(1))
    cmd_port = re.search(r'--port["\s,]+["\s]*(\d+)', text)
    if cmd_port:
        ports["CMD --port"] = int(cmd_port.group(1))
    return ports


def _config_default_port(attr: str) -> int | None:
    text = _CONFIG.read_text(encoding="utf-8")
    m = re.search(rf'{attr}:\s*str\s*=\s*"http://[^:]+:(\d+)"', text)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- #
# Guards anti-vacío.
# --------------------------------------------------------------------------- #
def test_compose_exists_and_declares_service_urls():
    assert _COMPOSE.is_file()
    targets = _service_url_targets()
    # Set conocido hoy: si el parser deja de encontrar las URLs, se nota.
    assert set(targets) == {
        "HEALTH_SERVICE_URL",
        "RESEARCH_SERVICE_URL",
        "EDUCATION_SERVICE_URL",
        "SECURITY_SERVICE_URL",
        "CODKING_SERVICE_URL",
    }, f"cambió el set de *_SERVICE_URL del gateway: {sorted(targets)}"


def test_service_url_ports_match_config_defaults():
    """
    Coherencia INTERNA de Micelia (siempre ejecutable, sin repos hermanos): el puerto de
    cada `*_SERVICE_URL` del compose == el default equivalente en config.py. El gateway
    usa los defaults de config.py cuando NO corre en compose (arranque local nativo), así
    que ambos deben declarar el mismo puerto por dominio.

    Mutación: cambia `health_service_url` a `:8099` en config.py sin tocar el compose →
    falla. El registry del gateway sondearía un puerto distinto según el modo de arranque.
    """
    targets = _service_url_targets()
    for url_var, config_attr in _URL_TO_CONFIG_DEFAULT.items():
        compose_port = targets[url_var][1]
        cfg_port = _config_default_port(config_attr)
        assert cfg_port is not None, (
            f"no se encontró el default `{config_attr}` en config.py (¿renombrado?)"
        )
        assert compose_port == cfg_port, (
            f"DRIFT interno: compose {url_var}=:{compose_port} pero config.py "
            f"{config_attr}=:{cfg_port}. El gateway enrutaría a puertos distintos según "
            f"arranque en compose o nativo. Alinéalos."
        )


# --------------------------------------------------------------------------- #
# El check CROSS-REPO real: Micelia ↔ el Dockerfile propio de cada dominio.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("url_var", sorted(_service_url_targets().keys()))
def test_gateway_route_matches_sibling_dockerfile_port(url_var: str):
    """
    El puerto al que Micelia enruta (`*_SERVICE_URL`) == el que el repo hermano EXPONE y
    BINDEA en su propio Dockerfile (el que el compose construye). SKIP si el hermano no
    está en el checkout.

    Mutación: cambia `EXPOSE 8080`+`--port 8080` a `8000` en
    biohack-app/backend/Dockerfile (sin tocar el compose de Micelia) → falla nombrando
    ambos repos. En real, el gateway enrutaría a :8080 mientras biohack sirve en :8000 →
    dominio inalcanzable en la red del compose, en silencio.
    """
    host, gateway_port = _service_url_targets()[url_var]
    dockerfile = _sibling_dockerfile(host)
    if dockerfile is None:
        pytest.skip(f"{url_var}: el servicio '{host}' no tiene build context en compose")
    if not dockerfile.is_file():
        pytest.skip(
            f"{url_var}: Dockerfile del hermano '{host}' no presente en el checkout "
            f"({dockerfile}); check cross-repo omitido (esperado en checkout aislado)."
        )
    declared = _dockerfile_ports(dockerfile)
    assert declared, (
        f"el Dockerfile de '{host}' ({dockerfile}) no declara ni EXPOSE ni --port; "
        f"no se puede verificar el puerto que sirve."
    )
    for kind, port in declared.items():
        assert port == gateway_port, (
            f"DRIFT CROSS-REPO: Micelia enruta {url_var} a :{gateway_port} (host "
            f"'{host}') pero el repo hermano declara {kind}=:{port} en {dockerfile}. "
            f"El gateway no alcanzaría el dominio en la red del compose. Alinea "
            f"docker-compose.yml de Micelia y el Dockerfile del dominio en lockstep."
        )
