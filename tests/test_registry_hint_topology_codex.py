"""
DP-15 (C85): el hint del warning del registry debe ser CIERTO en su topología.

Historia honesta de la DP: C83 la anotó como un nit de estilo — *"el warning sugiere
`make docker-full`, comando que el protocolo de la rutina diaria prohíbe"*. La auditoría
de C85 encuentra que el problema real no es el protocolo (que gobierna al agente, no al
usuario), sino que **el hint promete algo que el comando no puede cumplir**:

  * El warning solo se emite con URLs `localhost:*` cuando el gateway corre NATIVO
    (`run-local.sh`), porque en compose se le inyectan hostnames de contenedor
    (`HEALTH_SERVICE_URL=http://biohack-app:8080`, …).
  * A ese gateway nativo, `make docker-full` le levanta 9 contenedores pero PUBLICA
    `health` en :8081 y `testlab`(auto-mat-ion) en :3100 — puertos que el registry NO
    sondea (:8080 y :8891) → 2 de 5 dominios seguirían unhealthy.
  * Y la rama "precisa" (`unhealthy == {health}` → `make docker-health`) era justo la
    equivocada: biohack publicado en :8081, sondeado en :8080.
  * El launcher local-first sí bindea los 5 puertos sondeados (cybertools entró en el
    launcher en C85, commit anterior).

Este módulo pinea las dos mitades del contrato:
  1. La lógica del hint (topología → comando), sobre el registry real.
  2. El HECHO que la sostiene: los puertos que el compose publica para health/testlab
     NO son los que el registry sondea (si algún día se alinean, este pin muerde y hay
     que revisar el razonamiento de arriba, no borrarlo).
"""

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.service_registry import ServiceRegistry

_REPO = Path(__file__).resolve().parent.parent
_COMPOSE = _REPO / "docker-compose.yml"
_LAUNCHER = _REPO / "scripts" / "run-ecosystem.sh"


def _unhealthy_client():
    """Cliente httpx falso: todo lo sondeado responde 503 → todos los slots unhealthy."""
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.status_code = 503
    resp.json.return_value = {}
    client.get.return_value = resp
    return client


async def _hint_for(monkeypatch, urls: dict[str, str]) -> str:
    """Arranca discover_services con las URLs dadas y devuelve el hint logueado."""
    from app.services import service_registry as sr

    for attr, value in urls.items():
        monkeypatch.setattr(sr.settings, attr, value, raising=False)
    for attr in (
        "health_service_enabled",
        "research_service_enabled",
        "education_service_enabled",
        "security_service_enabled",
        "imperio_lab_enabled",
    ):
        monkeypatch.setattr(sr.settings, attr, True, raising=False)
    monkeypatch.setattr(sr.settings, "ollama_code_enabled", False, raising=False)

    warnings: list[str] = []
    monkeypatch.setattr(sr.log, "warning", lambda msg, *a, **k: warnings.append(str(msg)))

    reg = ServiceRegistry(_unhealthy_client())
    try:
        await reg.discover_services()
    finally:
        await reg.stop_monitoring()

    assert warnings, "el registry no emitió el warning de subservicios caídos"
    return warnings[-1]


_NATIVE_URLS = {
    "health_service_url": "http://localhost:8080",
    "research_service_url": "http://localhost:3690",
    "education_service_url": "http://localhost:5050",
    "security_service_url": "http://localhost:8000",
    "imperio_lab_url": "http://localhost:8891",
}

_COMPOSE_URLS = {
    "health_service_url": "http://biohack-app:8080",
    "research_service_url": "http://canela-molida:3690",
    "education_service_url": "http://ideacursi-backend:5050",
    "security_service_url": "http://cybertools:8000",
    "imperio_lab_url": "http://auto-mat-ion:9090",
}


@pytest.mark.asyncio
async def test_native_gateway_is_pointed_at_the_local_first_launcher(monkeypatch):
    """Gateway nativo (localhost:*) → el launcher, que sí bindea los puertos sondeados."""
    hint = await _hint_for(monkeypatch, _NATIVE_URLS)
    assert "run-ecosystem.sh start" in hint, hint
    assert "docker-full" not in hint, (
        "un gateway NATIVO no debe ser dirigido a docker-full: el compose publica "
        f"health:8081 y testlab:3100, que este registry no sondea. Hint: {hint!r}"
    )


@pytest.mark.asyncio
async def test_native_gateway_with_only_health_down_is_not_sent_to_docker_health(
    monkeypatch,
):
    """
    La regresión concreta de DP-15: la rama `unhealthy == {health}` mandaba a
    `make docker-health`, que publica biohack en :8081 mientras el registry sondea
    :8080 → el usuario ejecutaba el comando y el dominio seguía caído.
    """
    from app.services import service_registry as sr

    for attr in (
        "research_service_enabled",
        "education_service_enabled",
        "security_service_enabled",
        "imperio_lab_enabled",
        "ollama_code_enabled",
    ):
        monkeypatch.setattr(sr.settings, attr, False, raising=False)
    hint = await _hint_for(
        monkeypatch, {"health_service_url": "http://localhost:8080"}
    )
    assert "docker-health" not in hint, hint
    assert "run-ecosystem.sh start" in hint, hint


@pytest.mark.asyncio
async def test_compose_gateway_still_gets_the_docker_hint(monkeypatch):
    """
    El fix NO invierte el sesgo: un gateway EN COMPOSE (hostnames de contenedor) sigue
    siendo dirigido a docker, donde los puertos son internos y el compose sí manda.
    Recomendarle `run-ecosystem.sh` sería la lie simétrica.
    """
    hint = await _hint_for(monkeypatch, _COMPOSE_URLS)
    assert "docker-full" in hint, hint
    assert "run-ecosystem.sh" not in hint, hint


def _compose_published_port(service: str) -> str:
    """host_port del primer mapeo `- "HOST:CONTAINER"` del servicio dado."""
    text = _COMPOSE.read_text(encoding="utf-8")
    block = re.search(
        rf"^  {re.escape(service)}:$(.*?)(?=^  [a-z_-]+:$)", text, re.M | re.S
    )
    assert block, f"servicio '{service}' no encontrado en docker-compose.yml"
    mapping = re.search(r'ports:\s*\n\s*-\s*"(\d+):(\d+)"', block.group(1))
    assert mapping, f"servicio '{service}' sin mapeo de puertos"
    return mapping.group(1)


def test_the_fact_that_justifies_the_fix_still_holds():
    """
    El razonamiento del hint descansa en un hecho verificable: para un gateway NATIVO,
    los puertos que el compose PUBLICA no coinciden con los que el registry SONDEA.

    Si este pin muerde es porque alguien alineó los puertos (p.ej. biohack 8081→8080).
    Eso no invalida el fix — el launcher sigue siendo el camino local-first — pero sí
    obliga a revisar el comentario de service_registry.py, que cita estos números.
    """
    assert _compose_published_port("biohack-app") == "8081", (
        "el compose ya no publica biohack en :8081 → revisa el comentario del hint"
    )
    assert _compose_published_port("auto-mat-ion") == "3100", (
        "el compose ya no publica auto-mat-ion en :3100 → revisa el comentario del hint"
    )
    assert ServiceRegistry.HEALTH_ENDPOINTS["health"] == "/api/v1/service-health"


def test_launcher_binds_every_port_the_registry_probes():
    """
    La otra mitad: el hint solo es cierto si el launcher bindea LOS 5 puertos sondeados.
    Muerde si alguien saca un dominio del launcher (o le cambia el puerto) dejando al
    hint prometiendo un arranque que ya no ocurre.
    """
    text = _LAUNCHER.read_text(encoding="utf-8")
    bound = {
        m.group(1): int(m.group(2))
        for m in re.finditer(
            r"^([a-z0-9-]+)\|[^|\n]*\|[^|\n]*\|(\d+)\|", text, re.M
        )
    }
    # slot del registry -> (id en la tabla SERVICES, puerto que config.py sondea)
    expected = {
        "health": ("biohack-be", 8080),
        "research": ("canela", 3690),  # `make run-all` sirve la API en :3690
        "education": ("ideacursi", 5050),  # `npm run dev` levanta BE(:5050)+FE
        "security": ("cybertools", 8000),
        "testlab": ("automation", 8891),
    }
    # canela e ideacursi bindean en la tabla el puerto de su FE (un solo comando levanta
    # API+FE), así que su columna-puerto NO es el puerto sondeado: para ellos solo se
    # exige que el servicio siga existiendo. Para el resto se pinea el puerto exacto.
    binds_probed_port = {"health", "security", "testlab"}
    for slot, (launcher_id, probed_port) in expected.items():
        assert launcher_id in bound, (
            f"el slot '{slot}' del registry no tiene quien lo levante: "
            f"'{launcher_id}' desapareció de run-ecosystem.sh"
        )
        if slot in binds_probed_port:
            assert bound[launcher_id] == probed_port, (
                f"el slot '{slot}' se sondea en :{probed_port} pero el launcher bindea "
                f"'{launcher_id}' en :{bound[launcher_id]} → el hint prometería un "
                f"arranque que deja el dominio unhealthy"
            )
