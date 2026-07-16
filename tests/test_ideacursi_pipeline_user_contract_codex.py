"""
Tripwire cross-repo de la semántica de `user_id` del pipeline research-to-course
(DP-6, escalada en Ciclo 81).

DP-6 (C39): el pipeline `/gateway/pipeline/research-to-course` no tiene contexto de
usuario autenticado de ideacursi, así que el `userId` OBLIGATORIO del CreateCourseDto
se rellena con un default fijo `"micelia-pipeline"`.

AUDITORÍA C81 — la severidad que C39 anotó es INEXACTA. C39 dijo: "si no existe tal
usuario en la BD de ideacursi, el curso se sincroniza con user_id sin resolver (o falla
la activación)". Lo que hace el código REAL de ideacursi hoy (leído, no asumido):

  1. `createCourseIndexWithActivation` (courses.service.js) llama a `createCourseIndex`
     → el curso SÍ se genera y se guarda en FILESYSTEM. Nada falla aquí.
  2. Después resuelve username→UUID con `SELECT id FROM users WHERE username = $1`.
     Con 0 filas, `userUuid` se queda como el STRING LITERAL "micelia-pipeline"
     (esta ruta NO auto-crea el usuario; ver la asimetría del test de abajo).
  3. `UPDATE courses SET is_active=false WHERE user_id = 'micelia-pipeline'` contra una
     columna UUID → PostgreSQL lanza `invalid input syntax for type uuid`.
  4. Ese throw lo TRAGA el `catch` del propio `createCourseIndexWithActivation`
     ("Don't fail course creation if DB sync fails") → solo se loguea.

  → Consecuencia REAL: la activación NUNCA "falla" de cara a Micelia; el pipeline recibe
    **200 con un curso**, pero ese curso NO llega a la BD de ideacursi ni se activa.
    El modo de fallo es SILENCIOSO, no ruidoso — que es peor y por eso vale pinearlo.

POR QUÉ NO SE ARREGLA AQUÍ (decisión escalada, patrón de C80):
  - Opción (a) "seed de un usuario de servicio `micelia-pipeline` en ideacursi" toca el
    repo hermano, que ADEMÁS tiene WIP sin commitear (auth, main.js, database.module…)
    → guardarraíl "no tocar WIP de otros repos".
  - Opción (b) "propagar el user_id real del caller autenticado" NO está disponible tal
    como C39 la formuló: `verify_auth` (app/core/security.py:479) devuelve identidades
    `"apikey:<nombre>"` / `"jwt:<sub>"`, y el UserStore de Micelia está indexado por
    EMAIL (no tiene `username`) → no existe hoy una clave compartida que mapear contra
    `users.username` de ideacursi. Elegir esa clave es decisión de producto del dueño.

Este fichero es el cierre Micelia-side: convierte la auditoría en contrato EJECUTABLE.
Valor de tripwire: el día que ideacursi auto-cree el usuario en la ruta de activación
(o seedee el usuario de servicio, o deje de tragarse el error), estos tests fallan →
señal de que DP-6 se puede cerrar de verdad. Si ideacursi no está en el checkout, SKIP.

Solo lectura del código de ideacursi (mismo árbol de proyectos, cero secretos) + lectura
de la firma del endpoint de Micelia. Test-only; no modifica `app/`, ni ideacursi.
"""

import inspect
import re
from pathlib import Path

import pytest

_PROJECTS = Path(__file__).resolve().parents[2]
_IDEACURSI_COURSES_SERVICE = (
    _PROJECTS / "ideacursi-tool" / "backend" / "src" / "courses" / "courses.service.js"
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _js_method_body(name: str) -> str | None:
    """Cuerpo de un método `async <name>(...) { … }` de courses.service.js.

    Devuelve None si el fichero no está o el método no se puede parsear con confianza
    (→ el test hace SKIP en vez de fallar en falso).

    Nota de parsing: se cuentan llaves desde la de apertura. Las llaves que aparecen
    dentro del cuerpo (regex `{8}`/`{12}`, interpolaciones `${…}`) están BALANCEADAS,
    así que el conteo no se desincroniza.
    """
    if not _IDEACURSI_COURSES_SERVICE.is_file():
        return None
    text = _IDEACURSI_COURSES_SERVICE.read_text(encoding="utf-8")
    m = re.search(rf"\basync\s+{re.escape(name)}\s*\(", text)
    if not m:
        return None
    open_brace = text.find("{", m.end())
    if open_brace == -1:
        return None
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace : i + 1]
    return None


def _require_body(name: str) -> str:
    body = _js_method_body(name)
    if body is None:
        pytest.skip(
            f"ideacursi-tool/backend/src/courses/courses.service.js no presente o "
            f"`{name}` no parseable; check cross-repo omitido (esperado en checkout "
            f"aislado de Micelia)."
        )
    return body


# --------------------------------------------------------------------------- #
# Lado MICELIA (siempre ejecutable): el default que dispara toda la cadena.
# --------------------------------------------------------------------------- #
def test_pipeline_user_id_default_is_the_non_uuid_service_literal():
    """El pipeline envía un `userId` fijo NO-UUID → obliga a ideacursi a entrar en la
    rama de resolución username→UUID (que es donde vive DP-6).

    Si algún día el default pasa a ser un UUID real (o se propaga el del caller), esta
    aserción cae: DP-6 habrá cambiado de naturaleza y hay que releer este fichero."""
    from app.api.v1 import gateway

    default = inspect.signature(gateway.research_to_course_pipeline).parameters[
        "user_id"
    ].default

    assert default == "micelia-pipeline", (
        f"el default de user_id del pipeline cambió a {default!r}. DP-6 se anotó sobre "
        f"'micelia-pipeline'; revisa el contrato con ideacursi antes de actualizar el pin."
    )
    assert not _UUID_RE.match(default), (
        "el default de user_id ya es un UUID → ideacursi se saltaría el lookup por "
        "username y DP-6 quedaría obsoleta. Actualiza este fichero y cierra DP-6."
    )


# --------------------------------------------------------------------------- #
# Lado IDEACURSI (cross-repo, SKIP si ausente): pin del estado auditado en C81.
# --------------------------------------------------------------------------- #
def test_activation_path_resolves_username_but_does_not_autocreate():
    """
    Pin del paso 2 de la auditoría: la ruta de activación busca el usuario por username
    y NO lo auto-crea → con 'micelia-pipeline' el `userUuid` queda como string literal.

    Mutación (la deseable): ideacursi añade `INSERT INTO users … ON CONFLICT` a esta
    ruta (como ya hace `getUserCoursesFromDB`) → este test falla, y DP-6 se cierra sola:
    el usuario de servicio pasaría a existir en el primer curso del pipeline.
    """
    body = _require_body("createCourseIndexWithActivation")

    # Anti-vacío: el parser encontró la ruta reconocible que la auditoría describe.
    assert "SELECT id FROM users WHERE username = $1" in body, (
        "la ruta de activación de ideacursi ya no resuelve username→UUID con el lookup "
        "auditado; el parser o el contrato cambiaron. Revisa antes de confiar en el pin."
    )
    assert "INSERT INTO users" not in body, (
        "createCourseIndexWithActivation AHORA auto-crea el usuario. DP-6 puede CERRARSE: "
        "el 'micelia-pipeline' del pipeline se materializaría en la BD de ideacursi y el "
        "curso se sincronizaría/activaría. Verifica y actualiza este pin."
    )


def test_course_metadata_sync_also_lacks_autocreate():
    """Pin del mismo gap en `syncCourseMetadataToDB`, que es quien INSERTA el curso con
    `user_id = $2`: sin auto-create, ese $2 es el literal 'micelia-pipeline' contra una
    columna UUID → error de tipo en Postgres."""
    body = _require_body("syncCourseMetadataToDB")

    assert "SELECT id FROM users WHERE username = $1" in body, (
        "syncCourseMetadataToDB ya no resuelve username→UUID como se auditó; revisa el "
        "parser/contrato antes de confiar en el pin."
    )
    assert "INSERT INTO courses" in body, (
        "syncCourseMetadataToDB ya no inserta en `courses`; la cadena de DP-6 cambió."
    )
    assert "INSERT INTO users" not in body, (
        "syncCourseMetadataToDB AHORA auto-crea el usuario → DP-6 puede CERRARSE. "
        "Verifica el flujo real y actualiza este pin."
    )


def test_db_sync_failure_is_swallowed_so_micelia_sees_a_200():
    """
    Pin del paso 4 — el corazón de por qué DP-6 es SILENCIOSA: el fallo de sync/activación
    se captura y NO se relanza, así que Micelia recibe 200 con curso aunque el curso no
    haya llegado nunca a la BD de ideacursi.

    Mutación: si ideacursi empieza a propagar el error (relanza en el catch), el pipeline
    de Micelia pasaría a ver 5xx → DP-6 dejaría de ser silenciosa y Micelia tendría que
    manejar el fallo explícitamente. Este test avisa de ese cambio de contrato.
    """
    body = _require_body("createCourseIndexWithActivation")

    # El catch existe y su cuerpo solo loguea (no relanza).
    m = re.search(r"catch\s*\(\s*error\s*\)\s*\{(.*?)\n    \}", body, re.DOTALL)
    assert m is not None, (
        "no se encontró el catch de createCourseIndexWithActivation; el parser o el "
        "contrato cambiaron. Revisa antes de confiar en el pin."
    )
    catch_body = m.group(1)
    assert "Failed to sync course to database" in catch_body, (
        f"el catch auditado cambió de forma (cuerpo: {catch_body!r}); revisa el pin."
    )
    assert "throw" not in catch_body, (
        "createCourseIndexWithActivation AHORA relanza el fallo de sync a DB. El pipeline "
        "de Micelia recibirá 5xx cuando el usuario de servicio no exista, en vez de un 200 "
        "silencioso → DP-6 se vuelve RUIDOSA y hay que manejarla en gateway.py. Actúa."
    )


def test_autocreate_asymmetry_is_real_and_documented():
    """
    Pin de la ASIMETRÍA que la auditoría C81 destapó: `getUserCoursesFromDB` SÍ auto-crea
    el usuario, mientras la ruta de activación no. No es un bug de Micelia, pero explica
    por qué DP-6 podría "curarse sola" de forma ordenada-dependiente: si alguna vez se
    llamara a esa ruta con 'micelia-pipeline' ANTES de crear un curso, el usuario pasaría
    a existir y el sync posterior funcionaría.

    Valor: si ideacursi unifica el criterio (en cualquiera de los dos sentidos), este test
    lo detecta y DP-6 debe reevaluarse.
    """
    body = _require_body("getUserCoursesFromDB")

    assert "INSERT INTO users" in body, (
        "getUserCoursesFromDB ya NO auto-crea el usuario → ideacursi unificó el criterio "
        "hacia 'no auto-crear'. DP-6 sigue viva y ya no puede curarse por orden de "
        "llamadas: la opción (a) (seed del usuario de servicio) gana peso. Actualiza el pin."
    )
    assert "ON CONFLICT (username)" in body, (
        "el auto-create de getUserCoursesFromDB cambió de forma; revisa el pin de la asimetría."
    )
