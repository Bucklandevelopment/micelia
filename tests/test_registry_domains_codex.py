"""
Pins de los dominios del registry: fantasma real vs contrato vivo (DP-14, cerrada C84).

DP-14 nació en C83 (**la escribí yo tras el primer arranque real del ecosistema**) con
esta premisa: *"el registry sondea `devtools`(ollama-code) y `testlab`(imperio-lab), que
NO EXISTEN, y omite `codking`/`auto-mat-ion`, que sí existen"*. **La auditoría C84
desmiente 3 de sus 4 afirmaciones.** Ese error nace de un método pobre: C83 comprobó
NOMBRES DE CARPETA en `projects/`, no el CABLEADO real. Este fichero convierte la
auditoría correcta en pins ejecutables para que el error no se repita — y, sobre todo,
para que nadie "limpie" un contrato vivo creyéndolo fantasma.

Veredicto por afirmación de C83:

  1. `testlab`/`imperio-lab` es un fantasma  → **FALSO**. Es **auto-mat-ion**:
     declara `servicePort: 8891, // imperio_lab_url port from config`
     (src/integrations/vital-core.ts:61) y lo fija en su propio test. Nombre heredado,
     contrato VIVO por ambos lados. Borrarlo dejaría huérfano el puerto que auto-mat-ion
     anuncia al registrarse.
  2. `auto-mat-ion` no está en el registry → **FALSO**. Está, como `testlab`.
  3. `codking` no está en el registry → **ENGAÑOSO**. No tiene slot propio porque
     comparte :8000 con cybertools (caveat YA conocido de DP-12/C76); sus eventos viajan
     con `source=codking` por el ingest, que no necesita slot.
  4. `devtools`/`ollama-code` es un fantasma → **VERDADERO** (lo único que se sostiene):
     nadie bindea :8890 en todo el árbol y no existe tal proyecto.

FIX C84 (mínimo y reversible): `ollama_code_enabled` default True→False, alineando con la
única implantación que lo configura (el compose ya declara `OLLAMA_CODE_ENABLED=false #
Service not in compose`). El slot NO se elimina — eso es decisión de Jessicache.

NO se toca `imperio_lab_*`: su default True es correcto.

Read-only sobre auto-mat-ion; SKIP si no está en el checkout. Test-only.
"""

import re
from pathlib import Path

import pytest

_MICELIA = Path(__file__).resolve().parents[1]
_PROJECTS = _MICELIA.parent
_AUTOMATION_SDK = _PROJECTS / "auto-mat-ion" / "src" / "integrations" / "vital-core.ts"


def _config_default(field: str):
    """Default DECLARADO de un campo de Settings (config.py), inmune al entorno.

    Hermeticidad (C89): estos tests pinean el DEFAULT de config.py (lo dicen sus
    docstrings: "por defecto"), pero instanciar `Settings()` LAYERea el `.env` real
    (`env_file=".env"`) y las env-vars del proceso encima del default. Micelia TIENE un
    `.env` (4.6 KB), así que `Settings().ollama_code_enabled` no reportaba el default de
    config.py sino el valor efectivo de ESTA máquina: un `OLLAMA_CODE_ENABLED=true` en el
    `.env`/entorno (o `IMPERIO_LAB_ENABLED=false`) hacía FALLAR el test sin que el default
    —lo que el test dice pinear— hubiera cambiado. `model_fields[...].default` lee el
    literal de config.py sin construir Settings → cero capas de entorno. (Eco del patrón
    `Settings(_env_file=None, ...)` que ya usa test_core_config_codex.py.)
    """
    from app.core.config import Settings

    return Settings.model_fields[field].default


# --------------------------------------------------------------------------- #
# El único fantasma REAL: devtools / ollama-code.
# --------------------------------------------------------------------------- #
def test_devtools_phantom_is_disabled_by_default():
    """`ollama-code` no existe en el ecosistema → no se sondea por defecto.

    Mutación: si alguien vuelve a poner el default en True, cada arranque local
    sondea :8890 cada 30s para siempre y lo lista como "sin conexión" (el ruido que
    destapó DP-14 en C83).
    """
    assert _config_default("ollama_code_enabled") is False, (
        "ollama_code_enabled volvió a True. `ollama-code` NO EXISTE (nadie bindea :8890 "
        "en el árbol) → se sondearía cada 30s eternamente. Si el proyecto YA existe, "
        "actualiza este test y el comentario de config.py; si no, déjalo en False."
    )


def test_devtools_slot_survives_for_a_future_project():
    """El fix de C84 DESACTIVA, no elimina: el slot sigue configurable por env.

    Anti-sobreactuación: pinea que la decisión de BORRAR el slot (de Jessicache) no se
    tomó unilateralmente — `devtools` sigue existiendo y se puede reactivar.
    """
    from app.core.config import Settings

    s = Settings(ollama_code_enabled=True)
    assert s.ollama_code_enabled is True, (
        "el slot devtools dejó de ser reactivable por configuración; C84 lo desactivó "
        "por defecto pero NO lo eliminó (eso es decisión de Jessicache)."
    )
    assert "devtools" in s.services, (
        "el slot 'devtools' desapareció de settings.services; C84 no autorizó borrarlo."
    )


# --------------------------------------------------------------------------- #
# El NO-fantasma: testlab == auto-mat-ion. Contrato vivo, cross-repo.
# --------------------------------------------------------------------------- #
def test_testlab_port_matches_the_port_automation_announces():
    """
    Pin del contrato VIVO que C83 estuvo a punto de tirar por "fantasma": el
    `imperio_lab_url` del registry y el `servicePort` que auto-mat-ion ANUNCIA al
    registrarse deben ser el MISMO puerto.

    Mutación (por cualquiera de los 2 lados): si Micelia cambia `imperio_lab_url` o
    auto-mat-ion cambia su `servicePort`, el registry sondearía un puerto que el dominio
    no sirve → `testlab` quedaría eternamente unhealthy EN SILENCIO. Hoy: 8891 ambos.
    """
    if not _AUTOMATION_SDK.is_file():
        pytest.skip(
            "auto-mat-ion/src/integrations/vital-core.ts no presente; check cross-repo "
            "omitido (esperado en checkout aislado de Micelia)."
        )
    text = _AUTOMATION_SDK.read_text(encoding="utf-8")
    m = re.search(r"servicePort:\s*(\d+)", text)
    assert m is not None, (
        "auto-mat-ion ya no declara `servicePort` en su SDK; el contrato con "
        "imperio_lab_url cambió de forma. Re-audita antes de confiar en este pin."
    )
    announced = int(m.group(1))
    # nota: el puerto del registry sale del DEFAULT de config.py (_config_default),
    # no de `Settings()` — un override local en `.env` no es "drift del contrato".

    registry_port = int(_config_default("imperio_lab_url").rsplit(":", 1)[1])
    assert announced == registry_port, (
        f"DRIFT testlab↔auto-mat-ion: auto-mat-ion anuncia servicePort={announced} pero "
        f"el registry sondea imperio_lab_url puerto {registry_port}. El registry marcaría "
        f"testlab unhealthy para siempre, en silencio."
    )


def test_automation_sdk_still_points_at_imperio_lab_by_name():
    """
    Pin de la EVIDENCIA que desmonta DP-14: auto-mat-ion referencia `imperio_lab_url`
    explícitamente. Mientras este comentario/enlace viva, `testlab` NO es un fantasma y
    NO debe "limpiarse" del registry.

    Si auto-mat-ion deja de referenciarlo, este test avisa: ese sería el momento de
    reabrir la pregunta de C83 con datos nuevos.
    """
    if not _AUTOMATION_SDK.is_file():
        pytest.skip("auto-mat-ion no presente; check cross-repo omitido.")

    text = _AUTOMATION_SDK.read_text(encoding="utf-8")
    assert "imperio_lab_url" in text, (
        "auto-mat-ion ya NO referencia `imperio_lab_url`. El vínculo testlab↔auto-mat-ion "
        "que C84 verificó puede haberse roto → reabre DP-14 y re-audita quién sirve :8891 "
        "antes de tocar el registry."
    )


def test_imperio_lab_stays_enabled_by_default():
    """`testlab` apunta a un dominio REAL (auto-mat-ion, arrancable en local con
    run-ecosystem.sh) → su default sigue en True. Contrapeso del fix de devtools: C84
    desactivó UNO de los dos, no ambos."""
    assert _config_default("imperio_lab_enabled") is True, (
        "imperio_lab_enabled pasó a False. testlab NO es un fantasma: es auto-mat-ion "
        "(servicePort 8891). Si se desactiva, el registry deja de ver un dominio real."
    )
