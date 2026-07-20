"""
C101 — Contrato de health del slot `education` (ideacursi) que el registry SONDEA.

Verificación live intentada en C101 y BLOQUEADA (DP-19): el `node_modules` de ideacursi está
incompleto (`reflect-metadata`, declarado en `backend/package.json`, no está instalado) → el
backend NestJS crashea al arrancar, así que el slot `education` no pudo ejercerse en vivo. Pero
la lectura del código confirmó que el CONTRATO es sano y solo lo bloquean las deps locales:

  * ideacursi sirve health en **`/api/health`** (`main.js: app.setGlobalPrefix('api')` +
    `health.controller.js: @Controller('health')`), justo lo que el registry sondea.
  * su `/api/health` devuelve **`category: 'education'`, `port` 5050 y un campo `version`**
    (`'0.1.0'`) — a diferencia de canela, cuyo `/health` NO trae version (DP-8). O sea: cuando
    ideacursi arranque, el registry verá `healthy=True` con version.
  * el `PG_POOL` es LAZY (`new Pool()` no conecta hasta la 1ª query) → arranca degradado sin
    postgres; el único blocker real es la completitud de deps.

Este pin convierte esa lectura en guard ejecutable, cruzando el sondeo de Micelia con lo que
ideacursi sirve (patrón cross-repo de C82/C86/C100). Estático y read-only; SKIP si ideacursi no
está en el checkout. Micelia-side usa el DEFAULT de config (no `Settings()`) para no leer el
`.env` real (hermeticidad, C89).
"""

import re
from pathlib import Path

import pytest

from app.services.service_registry import ServiceRegistry

_PROJECTS = Path(__file__).resolve().parents[2]
_IDEACURSI = _PROJECTS / "ideacursi-tool"
_MAIN = _IDEACURSI / "backend" / "src" / "main.js"
_HEALTH = _IDEACURSI / "backend" / "src" / "health" / "health.controller.js"


def _config_default(field: str):
    """Default declarado de un campo de Settings (config.py), inmune al `.env` (C89)."""
    from app.core.config import Settings

    return Settings.model_fields[field].default


def _skip_if_absent():
    if not _MAIN.is_file() or not _HEALTH.is_file():
        pytest.skip("repo hermano ideacursi-tool no presente; check cross-repo omitido.")


# =============================================================================
# Micelia sondea education donde ideacursi lo sirve (path + puerto)
# =============================================================================


def test_registry_probes_education_at_api_health():
    """Micelia-side: el registry sondea `education` en `/api/health` sobre :5050."""
    assert ServiceRegistry.HEALTH_ENDPOINTS["education"] == "/api/health", (
        "el registry dejó de sondear education en /api/health; si ideacursi no cambió su "
        "ruta, esto rompería el health-check del slot."
    )
    assert _config_default("education_service_url").endswith(":5050"), (
        "education_service_url ya no apunta a :5050 (el puerto que ideacursi sirve)."
    )


def test_ideacursi_serves_health_at_api_health():
    """ideacursi-side: `setGlobalPrefix('api')` + `@Controller('health')` ⇒ la ruta REAL es
    `/api/health`, la misma que Micelia sondea. Si ideacursi cambia el prefijo o el controller,
    el registry sondearía una ruta muerta y `education` quedaría unhealthy en silencio."""
    _skip_if_absent()
    main = _MAIN.read_text(encoding="utf-8")
    health = _HEALTH.read_text(encoding="utf-8")
    assert re.search(r"setGlobalPrefix\(\s*['\"]api['\"]\s*\)", main), (
        "ideacursi ya no usa el prefijo global 'api'; su health dejó de estar en /api/*."
    )
    assert re.search(r"@Controller\(\s*['\"]health['\"]\s*\)", health), (
        "ideacursi movió el HealthController fuera de 'health'; la ruta /api/health cambió."
    )


# =============================================================================
# La identidad que el registry lee del /api/health de ideacursi (DP-8: SÍ trae version)
# =============================================================================


def test_ideacursi_health_reports_education_identity_and_version():
    """El `/api/health` de ideacursi declara `category: 'education'`, `port` 5050 y un campo
    `version` — este último es el que el registry parsea (`data.get("version")`). A diferencia
    de canela (DP-8, /health sin version), ideacursi SÍ lo trae: cuando arranque, el slot
    education tendrá version. Pin de esa identidad para que no derive en silencio."""
    _skip_if_absent()
    health = _HEALTH.read_text(encoding="utf-8")
    assert re.search(r"category:\s*['\"]education['\"]", health), (
        "el /api/health de ideacursi ya no se declara category 'education'."
    )
    assert re.search(r"version:\s*['\"][\w.]+['\"]", health), (
        "el /api/health de ideacursi perdió el campo `version` → el registry lo vería sin "
        "version (como canela, DP-8)."
    )
    assert re.search(r"BACKEND_PORT,\s*10\)\s*\|\|\s*5050", health), (
        "el puerto por defecto del health de ideacursi ya no es 5050 (el que Micelia sondea)."
    )
