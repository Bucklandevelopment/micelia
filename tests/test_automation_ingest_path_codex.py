"""
C108 — El camino REAL de auto-mat-ion hacia Micelia es REST, no pub/sub (corrige la premisa
de C107) + guard del drift DP-7 latente.

C107 anotó "el 4º mecanismo: auto-mat-ion registra/latea por Redis pub/sub, no REST". **La
auditoría C108 lo desmiente** (patrón C84: verificar la severidad/premisa heredada):

  * auto-mat-ion **registra por REST**: `registerService()` → `postEventToGateway()` →
    `POST /api/v1/events` con `service.registered`. Es el MISMO mecanismo que C86; el store
    de Micelia lo recibe por ahí.
  * auto-mat-ion **también** publica a Redis (`publishEvent` → canal `vital.${category}` +
    una key `vital:event:{id}`), PERO ese camino **no llega al store de Micelia**: Micelia
    NO se suscribe a canales de dominio (su event_bus publica `idm.*` interno y consume
    eventos de dominio por el REST del Event Store), y además el prefijo no casa —
    Micelia usa `idm.*`, auto-mat-ion `vital.*`. Es el **DRIFT DP-7** (Ciclo 41), **conocido
    y latente**, ya documentado en `app/sdk/models.py`: su resolución (namespace canónico
    `micelia.*`) es una migración coordinada irreversible de 6 servicios → decisión del dueño.

Este módulo pinea la REALIDAD (para que el camino vivo no derive y el drift latente no se
"arregle" a medias creando un fallo silencioso). Cross-repo read-only; SKIP si auto-mat-ion
no está en el checkout.
"""

import re
from pathlib import Path

import pytest

from app.sdk.models import EVENT_CHANNELS

_PROJECTS = Path(__file__).resolve().parents[2]
_AUTOMATION_VC = _PROJECTS / "auto-mat-ion" / "src" / "integrations" / "vital-core.ts"


def _automation_src() -> str:
    if not _AUTOMATION_VC.is_file():
        pytest.skip("repo hermano auto-mat-ion no presente; check cross-repo omitido.")
    return _AUTOMATION_VC.read_text(encoding="utf-8")


# =============================================================================
# El camino VIVO: auto-mat-ion → REST → store de Micelia
# =============================================================================


def test_automation_registers_via_rest_post_events():
    """`registerService()` anuncia su presencia por REST (`postEventToGateway`), y
    `postEventToGateway` hace `POST /api/v1/events` — el mismo canal que C86 pinea. Este es
    el camino que DE VERDAD llega al store de Micelia. Si auto-mat-ion moviera el registro a
    Redis-only, dejaría de registrarse (Micelia no consume ese pub/sub) — este pin lo caza."""
    src = _automation_src()
    # registerService delega el anuncio en postEventToGateway (no en el publish de Redis).
    reg = re.search(r"async registerService\([^)]*\)[^{]*\{(.*?)\n  \}", src, re.DOTALL)
    assert reg, "no se encontró registerService en auto-mat-ion"
    assert "postEventToGateway" in reg.group(1), (
        "registerService ya no anuncia por REST (postEventToGateway); si pasó a Redis-only, "
        "Micelia no lo recibiría (no consume pub/sub de dominio)."
    )
    # postEventToGateway hace POST /api/v1/events (el endpoint REST del Event Store).
    post = re.search(r"async postEventToGateway\([^)]*\)[^{]*\{(.*?)\n  \}", src, re.DOTALL)
    assert post, "no se encontró postEventToGateway"
    assert re.search(r"/api/v1/events", post.group(1)) and re.search(
        r"method:\s*'POST'", post.group(1)
    ), "postEventToGateway dejó de hacer POST /api/v1/events (el camino REST vivo)."


# =============================================================================
# El camino LATENTE (DP-7): Redis pub/sub con prefijo `vital.*` que Micelia no consume
# =============================================================================


def test_automation_redis_publish_uses_vital_prefix():
    """El `publishEvent` de auto-mat-ion publica al canal `vital.${category}` — el prefijo de
    la era vital-core. (Lado del drift DP-7.)"""
    src = _automation_src()
    assert re.search(r"`vital\.\$\{[^}]*category[^}]*\}`", src), (
        "auto-mat-ion dejó de publicar en `vital.${category}`; si migró de prefijo, revisa "
        "DP-7 (¿se resolvió el namespace canónico?)."
    )


def test_micelia_channels_use_idm_prefix_mismatching_automation_dp7():
    """Los EVENT_CHANNELS de Micelia usan el prefijo `idm.*`, que NO casa con el `vital.*` de
    auto-mat-ion → el pub/sub cruzado no está cableado (fallaría en silencio). Pin del DRIFT
    DP-7 latente: si algún día ambos prefijos se alinean (resolución de DP-7), este test
    muerde y recuerda actualizar el contrato en lockstep. Hoy: Micelia idm.*, dominios vital.*.
    """
    assert EVENT_CHANNELS, "EVENT_CHANNELS vacío"
    assert all(ch.startswith("idm.") for ch in EVENT_CHANNELS.values()), (
        f"algún canal de Micelia dejó de usar el prefijo `idm.`: {EVENT_CHANNELS}"
    )
    # el mismatch con auto-mat-ion (vital.*) es la esencia de DP-7: hoy NINGÚN canal idm.*
    # coincide con lo que auto-mat-ion publica (vital.*), por eso el pub/sub no se consume.
    assert not any(ch.startswith("vital.") for ch in EVENT_CHANNELS.values()), (
        "Micelia empezó a usar canales `vital.*` → o se resolvió DP-7 (alinea con los SDK y "
        "actualiza este pin) o hay una regresión de prefijo."
    )
