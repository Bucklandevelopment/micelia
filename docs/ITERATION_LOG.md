# ITERATION_LOG — Daily Micelia Full Planning

> Memoria persistente de la tarea diaria. Cada ejecución añade una entrada NUEVA
> arriba del todo. No editar entradas anteriores.

## Formato de entrada

```
## YYYY-MM-DD
- Hecho: (commits + resumen de 1 línea cada uno)
- Verify: (verde/rojo + cobertura %)
- Bloqueado/pendiente: (qué y por qué)
- DECISIÓN PENDIENTE: (si aplica, para Jessicache)
- Mañana: (siguiente paso concreto recomendado)
```

---

## 2026-07-11 — Ciclo 12 (entire_session 0→100% · cobertura 59.90→61.05% · gate 57→59)

**Contexto:** Ciclo 11 dejó `make verify` 100% verde (740 pass, cov 59.90%, gate 57%) con
las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la
tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 11. `entire_session.py` (79 stmts, 0%) era el mayor gap **limpio**
restante: el wrapper del CLI `entire` (trazabilidad de sesiones de agente), con **dos
fronteras externas bien acotadas** — `shutil.which("entire")` (detección de binario) y
`asyncio.create_subprocess_exec` (dentro de `_run_entire`) → 100% aislable sin red/DB/
subprocesos reales. Los otros gaps son peores candidatos: `osascript.py` (24%, macOS-specific,
poco portable a CI Linux), `workflow_engine.py` (81%, solo ~40 líneas), `user_store.py` (88%,
8 líneas). Un commit de test + un ratchet de gate + log, verify-verde, reversible. No se tocó
ninguna DECISIÓN PENDIENTE ni infra; nada arrancado.

- **Hecho:**
  - `test(cov)`: `tests/test_entire_session_codex.py` (28 tests) para `EntireSessionService`.
    Aislamiento: fixture autouse resetea el singleton del módulo (`es._entire_service = None`)
    para independencia de orden; helper `_svc(available=...)` fuerza el cache
    `_entire_available` sin llamar a `shutil.which` (o se parchea `es.shutil.which` para
    ejercitar la rama de detección real); `_FakeProc` con `communicate` `AsyncMock`
    `(stdout, stderr)` y `returncode` scriptables + `_patch_subprocess` que sustituye
    `es.asyncio.create_subprocess_exec` por una factory que captura el argv (o lanza), de modo
    que `_run_entire` corre happy/error sin spawnear procesos. Cubre: `is_available`
    (detecta presente/ausente + cache tras la 1ª sonda), `start_session` (unavailable→solo
    in-memory sin spawnear / available happy→setea `entire_session_id` desde stdout.strip +
    argv `idm-<prompt[:8]>` / `_run_entire` lanza→`except` tragado, sesión igual creada /
    metadata custom preservada / `_trim_sessions` con cap bajado a 2), `checkpoint`
    (session_id inexistente→no-op / sin `entire_session_id`→solo append / con id+available→
    llama entire con `--message agent:action` / fallo→tragado, append igual / trunca
    `output_summary[:500]` / None), `end_session` (inexistente→no-op / happy sin id / status
    default `completed` / con id→llama `session end` / fallo→tragado), getters (`get_sessions`
    orden desc + limit/offset, `get_session` present/absent, `get_sessions_for_prompt` filtra
    + ordena, `get_status` cuenta active/total + `entire_available`), `_run_entire` (rc 0→
    stdout / rc≠0→`RuntimeError` con stderr), `_trim_sessions` (evicta las más antiguas por
    `started_at` / bajo cap→no-op) y el singleton `get_entire_service`. Módulo: **0% → 100%**
    (79 stmts, 0 sin cubrir).
  - `chore(cov)`: ratchet gate `make cov` **57% → 59%** (medido 61.05%, margen ~2.1 pt;
    suite determinista sin red/DB/subprocesos reales). Actualizado comentario+nota del target
    en `Makefile` y cabecera+histórico+tabla de módulos de `docs/COVERAGE_ROADMAP.md`
    (59.90→61.05%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**768 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**61.05%** ≥ gate 59%, era 59.90%/gate 57). +1.15 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.
  Nota: Pyright (IDE) marca args sin uso en fakes y un subscript de `get_session` (Optional)
  en el test — **no afecta al gate**: `make typecheck` es `mypy app/` (no toca `tests/`) y
  `make lint` (ruff E/F/I/N/W) no audita args sin uso. Patrón heredado de tests `_codex`
  previos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Mayores gaps de cobertura restantes, cada vez menos "limpios": `osascript.py`
  (24%, 318 stmts, macOS-specific — poco portable a CI Linux), `workflow_engine.py`
  (81%, ~40 líneas sin cubrir, ya con andamiaje de tests existente), `user_store.py` (88%,
  8 líneas), `prompt_store.py` (95%, solo `initialize` DB-setup). El ratchet de mypy hacia
  `strict=true` (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: cerrar los ~40 huecos
  de `workflow_engine.py` (81%→~100%) — es ahora el mayor gap **limpio** restante y ya tiene
  andamiaje de tests (`test_workflow_engine_codex.py`); alternativa menor `user_store.py`
  (88%→100%, 8 líneas). (c) arrancar el ratchet mypy activando `disallow_untyped_defs` en
  `app/services/frangels/` (ya al ~99% de cobertura).

---

## 2026-07-11 — Ciclo 11 (mcp_generator 0→100% · cobertura 57.31→59.90% · gate 55→57)

**Contexto:** Ciclo 10 dejó `make verify` 100% verde (701 pass, cov 57.31%, gate 55%) con
las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la
tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 10. `mcp_generator.py` (179 stmts, 0%) era el mayor gap **limpio**
restante: el generador de servidores MCP (Python/FastMCP + TypeScript/@modelcontextprotocol),
con dos fronteras externas bien acotadas — file I/O (`output_dir` relativo a cwd) y
subprocess/signals (`Popen`/`os.killpg`) → 100% aislable sin red/DB. Un commit de test + un
ratchet de gate + log, verify-verde, reversible. No se tocó ninguna DECISIÓN PENDIENTE ni
infra; nada arrancado.

- **Hecho:**
  - `test(cov)` (`a5b5e70`): `tests/test_mcp_generator_codex.py` (39 tests) para
    `MCPGenerator`. Aislamiento: `_gen(tmp_path, monkeypatch)` hace `monkeypatch.chdir(tmp_path)`
    **antes** de construir, así el `mkdir` de `__init__` (`data/mcp-servers` relativo a cwd) y
    todas las escrituras caen en el sandbox de pytest (file I/O real, aserciones con
    `Path.read_text()`); `_FakeProc` sustituye a `subprocess.Popen` con `poll`/`wait`
    scriptables (lista de retornos + `wait` que lanza `TimeoutExpired` una vez); `_patch_popen`
    reemplaza `mg.subprocess.Popen` por una factory que captura `cmd`/`kwargs` (o lanza una
    excepción); `_patch_signals` parchea `os.getpgid`/`os.killpg` para registrar señales sin
    tocar procesos reales. Cubre: `generate` python (crea server.py/pyproject/README/metadata,
    type-map string→str/integer→int/boolean→bool, default con `repr`, tipo desconocido→str,
    claves de tool ausentes→`unnamed_tool`/`arg`/`No description`) y typescript (server.ts/
    package.json, zod-map + `.describe`, `json.loads` del package), `generate` unsupported→
    `ValueError`, metadata.json completo; `list_servers` (dir ausente→[] / sin servers→[] /
    lee metadata+running / ignora no-dirs / dir sin metadata→skip / metadata ilegible→
    fallback+warning); `get_server` (not-found→`FileNotFoundError` / metadata+source+files /
    running=True / lee server.ts en ts / sin metadata→dict mínimo); `delete_server` (ok /
    not-found / corriendo→`RuntimeError`); `start_server` (spawn+track python cmd / ts→npx /
    not-found / ya corriendo (poll None)→error / proceso muerto (poll 0)→cleanup+restart /
    sin metadata→python / `Popen` lanza→`RuntimeError` + no queda en `_running_processes`);
    `stop_server` (not-running→error / ya muerto (poll≠None)→`already_stopped` / SIGTERM
    grácil / `TimeoutExpired`→escalada SIGKILL con 2 waits / `ProcessLookupError` tragado);
    y el singleton `get_mcp_generator`. Módulo: **0% → 100%** (179 stmts, 0 sin cubrir).
  - `chore(cov)` (`57e5713`): ratchet gate `make cov` **55% → 57%** (medido 59.90%, margen
    ~2.9 pt; suite determinista sin red/DB/subprocesos reales). Actualizado comentario+nota del
    target en `Makefile` y cabecera+histórico de `docs/COVERAGE_ROADMAP.md` (57.31→59.90%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**740 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**59.90%** ≥ gate 57%, era 57.31%/gate 55). +2.59 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.
  Nota: Pyright (IDE) marca `_FakeProc` no asignable a `Popen` en el test — **no afecta al
  gate**: `make typecheck` es `mypy app/` (no toca `tests/`) y `make lint` (ruff E/F/I/N/W) no
  audita args sin uso. Patrón heredado de tests previos que asignan `MagicMock` (tipo `Any`).

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Mayores gaps de cobertura restantes, todos aún limpios/mockeables: `entire_session.py`
  (0%, 79 stmts), `osascript.py` (24%, 318 stmts, macOS-specific — poco portable a CI Linux),
  `workflow_engine.py` (81%, 40 líneas sin cubrir). El ratchet de mypy hacia `strict=true`
  (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: `entire_session.py`
  (0%, 79 stmts) — es ahora el mayor gap **limpio** restante; alternativa cerrar los 40
  huecos de `workflow_engine.py` (81%→~100%, ya con andamiaje de tests existente). (c) arrancar
  el ratchet mypy activando `disallow_untyped_defs` en `app/services/frangels/` (ya al ~99%).

---

## 2026-07-11 — Ciclo 10 (markdown_sync 0→100% · cobertura 53.31→57.31% · gate 51→55)

**Contexto:** Ciclo 9 dejó `make verify` 100% verde (668 pass, cov 53.31%, gate 51%) con
las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la
tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 9. `markdown_sync.py` (276 stmts, 0%) era el mayor gap **limpio**
restante: el sync bidireccional DB↔Markdown del orquestador, con una **única frontera
externa** (`PromptStore`) + file I/O → 100% aislable sin red/DB (los dirs son atributos
string públicos, redirigibles a `tmp_path`; `utcnow_naive` parcheable). Un commit de test +
un ratchet de gate + log, verify-verde, reversible. No se tocó ninguna DECISIÓN PENDIENTE ni
infra; nada arrancado.

- **Hecho:**
  - `test(cov)` (`0296e69`): `tests/test_markdown_sync_codex.py` (33 tests) para
    `MarkdownSyncService`. Aislamiento: `_store(**overrides)` arma un `MagicMock` con los 6
    métodos usados como `AsyncMock` (`list_all_lists`, `get_captured_prompts`,
    `get_archived_prompts`→`{"prompts":[...]}`, `get_list`, `update_list`, `create_list`);
    `_svc(tmp_path, store)` construye el servicio y **redirige** `lists_dir/inbox_dir/
    archive_dir` a subdirs de `tmp_path` (file I/O real contra el sandbox, aserciones con
    `Path.read_text()`); `utcnow_naive` parcheado a `datetime(2026,7,11,9,30)` para rutas
    `YYYY/MM/YYYY-MM-DD` deterministas. `_run_loop` se ejercita **directo** (no vía la task
    de fondo) parcheando `asyncio.sleep` para cortar el bucle. Cubre: `start`
    (crea dirs + task; no re-arranca si task viva), `stop` (cancel + swallow; sin task
    no-op), `_run_loop` (happy / `CancelledError`→break / `Exception`→log+sleep),
    `sync_lists_to_md` (escribe nuevo con frontmatter / skip sin slug / skip si file existe→MD
    gana), `sync_inbox_to_md` (vacío / ninguno de hoy / escribe hoy con formato time+tags+
    priority, con y sin `T` y sin tags), `sync_archives_to_md` (vacío / agrupa por `YYYY-MM`
    con fallback `archived_at`/`created_at` / bucket `unknown`→skip / `year_month`
    malformado→skip), `sync_md_to_lists` (dir inexistente→0 / ignora no-`.md` y vacíos /
    crea nuevo con slug+name desde filename / actualiza existente con campos opcionales +
    `is_active` / read-error→warning+continue), `full_sync` (agrega los 4 contadores +
    `sync_count`+`last_sync`; cada sub-sync que lanza→capturada en `errors` sin abortar),
    `_parse_frontmatter` (sin `---` / sin 2º marcador / bool yes-no-true-false / listas / quotes
    / comentarios y líneas sin `:`), `_build_frontmatter` (bool/list/None/str + roundtrip),
    `_parse_bool`, `_ensure_dirs`, `_write_file`/`_read_file` (crea dirs intermedios),
    `get_status`, `get_today_inbox_md` (presente/ausente). Módulo: **0% → 100%** (276 stmts,
    0 sin cubrir).
  - `chore(cov)` (`c22d7ec`): ratchet gate `make cov` **51% → 55%** (medido 57.31%, margen
    ~2.3 pt; suite determinista sin red/DB/tiempo). Actualizado comentario+nota del target en
    `Makefile` y cabecera+histórico de `docs/COVERAGE_ROADMAP.md` (53.31→57.31%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**701 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**57.31%** ≥ gate 55%, era 53.31%/gate 51). +4.00 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Mayores gaps de cobertura restantes, todos aún limpios/mockeables: `mcp_generator.py`
  (0%, 554 líneas, codegen — puro string/template, sin fronteras externas), `entire_session.py`
  (0%, 164 líneas), `osascript.py` (24%, 318 stmts, macOS-specific — poco portable a CI
  Linux). El ratchet de mypy hacia `strict=true` (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: `mcp_generator.py`
  (0%, 554 líneas) — es el mayor gap **limpio** restante (generación de código, puro
  string/template sin red/DB, 100% determinista); alternativa más pequeña `entire_session.py`
  (0%, 164 líneas). (c) arrancar el ratchet mypy activando `disallow_untyped_defs` en
  `app/services/frangels/` (ya al ~99% de cobertura).

---

## 2026-07-11 — Ciclo 9 (event_bus 0→100% · cobertura 51.93→53.31% · gate 49→51)

**Contexto:** Ciclo 8 dejó `make verify` 100% verde (644 pass, cov 51.93%, gate 49%) con
las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha desde Ciclo 3 y ambos unblocks pendientes, la
tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 8. `event_bus.py` (96 stmts, 0%) era el mayor gap **limpio** restante:
el bus Redis Pub/Sub del orquestador, con una única frontera externa (`redis.asyncio`) →
100% aislable sin red/DB. Un commit de test + un ratchet de gate + log, verify-verde,
reversible. No se tocó ninguna DECISIÓN PENDIENTE ni infra; nada arrancado.

- **Hecho:**
  - `test(cov)` (`6b3908c`): `tests/test_event_bus_codex.py` (24 tests) para `EventBus`.
    Aislamiento: helper `_make_client()` arma un cliente `MagicMock` con `AsyncMock`
    ping/publish/close y `pubsub()` → PubSub mock (subscribe/unsubscribe/close `AsyncMock`,
    `listen` scriptable); `_connected_bus()` parchea `event_bus.redis.from_url` y corre
    `connect`. `_listen` se ejercita **directo** (no vía la task de fondo) apuntando
    `pubsub.listen()` a un async generator (`_aiter`/`_araise`) de mensajes escritos, así
    el `async for` termina determinista sin bucle real. Cubre: `connect` (happy + ping
    falla→not connected), `disconnect` (con task viva cancel+CancelledError tragada +
    pubsub/redis close; y todo-None no-op), `publish` (desconectado→descarta / happy con
    metadata timestamp+channel+data / except tragado), `subscribe` (canal nuevo suscribe +
    arranca listener / canal existente añade sin re-suscribir / task viva no se re-arranca),
    `unsubscribe` (callback específico mantiene otros / último→del+unsubscribe / todos
    (`callback=None`) / canal desconocido no-op), `_listen` (JSON válido→callbacks async y
    sync vía `iscoroutinefunction`, JSON inválido→`{"raw":...}`, tipo != message ignorado,
    callback que lanza→logueado y sigue, `CancelledError`→salida limpia, excepción
    genérica→logueada), los 4 publishers de conveniencia (health/education/security/system
    delegan en `publish` con `CHANNELS[...]` y mezclan `{"type",**data}`), y forma de
    `CHANNELS`. Módulo: **0% → 100%** (96 stmts, 0 sin cubrir).
  - `chore(cov)` (`b5ada8b`): ratchet gate `make cov` **49% → 51%** (medido 53.31%, margen
    ~2.3 pt; suite determinista sin red/DB/tiempo). Actualizado comentario+nota del target
    en `Makefile` y cabecera+histórico de `docs/COVERAGE_ROADMAP.md` (51.93→53.31%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**668 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**53.31%** ≥ gate 51%, era 51.93%/gate 49). +1.38 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
  Mayores gaps de cobertura restantes, todos aún limpios/mockeables: `markdown_sync.py`
  (0%, 276 stmts, file I/O + parsing), `mcp_generator.py` (0%, 179 stmts, codegen),
  `entire_session.py` (0%, 79 stmts), `osascript.py` (24%, 318 stmts, macOS-specific —
  poco portable a CI Linux). El ratchet de mypy hacia `strict=true`
  (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: `markdown_sync.py`
  (0%, 276 stmts) — es el mayor gap **limpio** restante (file I/O + parsing de markdown,
  aislable con `tmp_path` + mocks del store, patrón ya probado en google_calendar). (c)
  arrancar el ratchet mypy activando `disallow_untyped_defs` en `app/services/frangels/`
  (ya al ~99% de cobertura).

---

## 2026-07-10 — Ciclo 8 (google_calendar 13→98% · cobertura 48.99→51.93% · gate 47→49)

**Contexto:** Ciclo 7 dejó `make verify` 100% verde (599 pass, cov 48.99%, gate 47%)
con las dos DECISIONES PENDIENTES de siempre, **ambas bloqueadas para trabajo autónomo**:
(1) bug bcrypt del funnel (tocar `uv.lock` = riesgo de arrastre, requiere aprobación),
(2) frontend `/register` (feature nueva + QA humano, no verificable por `make verify`).
Con la prioridad #1 (rojo→verde) satisfecha y ambos unblocks pendientes, la tarea de
máximo valor autónomo-segura es la prioridad #3 (cobertura) — y era el "Mañana (b)"
explícito de Ciclo 7. `google_calendar.py` (240 stmts, 13%) era el mayor gap restante:
frontera externa doble pero 100% aislable — las libs de Google (`Flow`/`Credentials`/
`build`) importadas bajo `try/except`+flag, `TOKEN_PATH` (file I/O) y `PromptStore`
(import lazy en los sync). Un commit de test + un ratchet de gate + log, verify-verde,
reversible. No se tocó ninguna DECISIÓN PENDIENTE ni infra.

- **Hecho:**
  - `test(cov)`: `tests/test_google_calendar_codex.py` (45 tests) para
    `GoogleCalendarService`. Aislamiento: fixture autouse redirige `gc.TOKEN_PATH` a
    `tmp_path` y resetea el singleton `gc._google_calendar` (order-independence); helper
    `_svc(...)` arma un `MagicMock` con las cadenas `calendarList()/events().list()/
    insert().execute` preconfiguradas (`asyncio.to_thread(fn)` ejecuta el mock y devuelve
    su valor); `_FakeCreds` para los happy-paths de auth (con sentinel `_UNSET` para poder
    testear el fallback `scopes → SCOPES`); `_patched_store()` parchea
    `app.services.prompt_store.PromptStore` con métodos `AsyncMock`. Cubre: `authenticate`
    (guard libs-off/creds-missing/happy/except), `handle_callback` (libs-off/happy con
    escritura de token+build/expiry None y set/except), `is_connected` (creds cacheadas/
    sin file/file→_load/_load raises→False), `_load_credentials` (libs-off/no-file/happy/
    rama refresh — google-auth SÍ está instalado en el venv, `Request` real/error→reset),
    `_save_credentials` (no-creds/happy/write-error), `_ensure_service`, `list_calendars`,
    `get_events` (ventana default/explícita, `dateTime` vs `date`, except), `create_event`
    (validaciones/happy/except), `sync_prompts_from_calendar` (crea/skip-sin-tag/
    skip-ya-synced/content-vacío→description/parse scheduled_at ok+malo/except+close),
    `sync_results_to_calendar` (crea+marca/skip sin output+ya-synced+sin completed_at/
    completed_at malo→now/except+close), `disconnect` (con/sin file/unlink-error),
    `get_status`, singleton. Módulo: **13% → 98%** (240 stmts; única franja sin cubrir:
    24-28, el `except ImportError` de import de las libs de Google — inalcanzable con las
    libs instaladas, sin valor mockear).
  - `chore(cov)`: ratchet gate `make cov` **47% → 49%** (medido 51.93%, margen ~2.9 pt;
    suite determinista sin red/DB/tiempo). Actualizado comentario+nota del target en
    `Makefile` y cabecera+histórico+fila `google_calendar` de `docs/COVERAGE_ROADMAP.md`
    (48.99→51.93%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**644 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**51.93%** ≥ gate 49%, era 48.99%/gate 47). +2.94 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7
  rebrand). Mayores gaps de cobertura restantes: `osascript.py` (24%, 318 stmts,
  macOS-specific — poco portable a CI Linux), `event_bus.py` (0%, 96 stmts, requiere
  mock de Redis pub/sub), `markdown_sync.py` / `mcp_generator.py` (0%, file I/O + gen de
  código). El ratchet de mypy hacia `strict=true` (`disallow_untyped_defs`) sigue vivo.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura: `event_bus.py`
  (0%, 96 stmts) con mock de Redis (`redis.asyncio` stubbeado) — salto limpio y de valor
  operativo (es el bus de eventos del orquestador). (c) arrancar el ratchet mypy activando
  `disallow_untyped_defs` en `app/services/frangels/` (ya al ~99% de cobertura).

---

## 2026-07-10 — Ciclo 7 (frangels/orchestrator 17→100% · cobertura 45.51→48.99% · gate 44→47)

**Contexto:** Ciclo 6 dejó `make verify` 100% verde (537 pass en tests/, cov 45.51%,
hito v0.2=45% alcanzado en medición real) con dos DECISIONES PENDIENTES para Jessicache,
**ambas bloqueadas para trabajo autónomo**: (1) bug bcrypt del funnel (tocar `uv.lock` =
riesgo de arrastre, requiere aprobación), (2) frontend `/register` (feature nueva + QA
humano, no verificable por `make verify`). Con la prioridad #1 (rojo→verde) satisfecha y
ambos unblocks pendientes, la tarea de máximo valor autónomo-segura es la prioridad #3
(cobertura) — y era el "Mañana (b)" explícito de Ciclo 6. `frangels/orchestrator.py`
(289 stmts, 17%) era el mayor gap restante en frangels/ y uno de los dos mayores del
proyecto; frontera externa **única** (`httpx.AsyncClient`), colaboradores
(`provider_store`, `quota_manager`) inyectables → 100% mockeable sin red/DB. Se descartó
`google_calendar.py` (13%) por depender de las librerías cliente de Google (frontera más
frágil). Un commit de test + un ratchet de gate, verify-verde, reversible. No se tocó
ninguna DECISIÓN PENDIENTE ni infra.

- **Hecho:**
  - `test(cov)`: `tests/test_frangels_orchestrator_codex.py` (62 tests) para
    `FrangelsOrchestrator`. Aislamiento: `_make_orch()` sustituye `provider_store` y
    `quota_manager` por `MagicMock`; `_get_client` parcheado con `AsyncMock` que devuelve
    un cliente falso cuyos `get/post/head` son `AsyncMock` → `_FakeResponse(status_code,
    json())`. `select_angel` (núcleo de lógica pura) se ejercita contra un `ANGEL_REGISTRY`
    reducido y determinista (`_patch_registry`) para aseverar filtros
    categoría/key/cuota/privacidad/vision/tools/min_context, orden tier→salud→latencia,
    `reasoning` y `fallbacks[1:4]` sin depender del registro real. Rutas HTTP
    (`test_provider` + `_test_*`, `chat` + `_chat_*`, paid providers openai/anthropic con
    split de system-message y cálculo de coste, singleton) con los ids reales
    (groq/gemini/deepseek/cohere/mistral/openrouter + genérico huggingface). Fixture
    autouse resetea el singleton del módulo y restaura `angel.health` del registro real
    (que `test_provider` muta) → tests order-independent. Módulo: **17% → 100%**
    (289 stmts, 0 sin cubrir).
  - `chore(cov)`: ratchet gate `make cov` **44% → 47%** (medido 48.99%, margen ~2 pt;
    suite determinista sin red/DB/tiempo). Actualizado comentario+nota del target en
    `Makefile` y cabecera+histórico+fila `frangels/` de `docs/COVERAGE_ROADMAP.md`
    (45.51→48.99%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ (ruff app/ sdk/ tests/) · typecheck ✓
  (mypy app/, 0 errores) · test ✓ (**599 pass** + 2 skip; incluye sdk/python/tests/) ·
  cov ✓ (**48.99%** ≥ gate 47%, era 45.51%/gate 44). +3.48 pts. No se arrancó nada (ni
  gateway ni infra); sin procesos residuales; árbol para 3 commits atómicos.

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login darían 500 en runtime). Recomendación intacta: fijar
  `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin aprobación (lockfile).
  (2) **frontend del funnel** (`/register` inexistente en `micelia/frontend`). Feature
  nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** dir legacy `vital-core/docs/` sigue en el árbol (DoD §7
  rebrand). Mayores gaps de cobertura restantes: `google_calendar.py` (13%, 240 stmts),
  `osascript.py` (24%, macOS-specific), `frangels/orchestrator` ya cerrado. El ratchet de
  mypy hacia `strict=true` sigue vivo (mejora, no bloquea).

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login. (b) cobertura del mayor gap
  restante: `google_calendar.py` (13%) con mock de la Google API (googleapiclient /
  flujo OAuth stubbeado) — 208 stmts sin cubrir, el mayor salto disponible. (c) arrancar
  el ratchet mypy activando `disallow_untyped_defs` en un subpaquete pequeño (p.ej.
  `app/services/frangels/`, ya al ~99% de cobertura).

---

## 2026-07-10 — Ciclo 6 (prompt_store 63→95% · cobertura 44.60→45.51% · **hito v0.2 = 45% ALCANZADO en medición real** · gate 43→44)

**Contexto:** Ciclo 5 dejó `make verify` 100% verde (512 pass, cov 44.60%) con dos
DECISIONES PENDIENTES para Jessicache, **ambas bloqueadas para trabajo autónomo**: (1)
bug bcrypt del funnel (tocar `uv.lock` = cambio con riesgo de arrastre, requiere
aprobación), (2) frontend `/register` (feature nueva + QA humano, no verificable por
`make verify`). Con la prioridad #1 (rojo→verde) ya satisfecha y ambos unblocks
pendientes, la tarea de máximo valor autónomo-segura es la prioridad #3 (cobertura) —
además es el "Mañana" explícito de Ciclo 5: cerrar `app/services/prompt_store.py` (63%,
~72 stmts sin cubrir) para cruzar el hito v0.2 = 45.00% **en medición real** (Ciclo 5
lo alcanzó sólo en display, medido 44.60%). Reconocimiento confirmó el hueco: el
`test_prompt_store_codex.py` existente (714 líneas) cubría prompts CRUD/notes/list/stats/
lifecycle/serialización pero NO los métodos de prompt-lists, promoción ni inbox — todos
CRUD puro con el mismo patrón mock-session ya probado. Un solo commit de test,
verify-verde, reversible. No se tocó ninguna DECISIÓN PENDIENTE ni infra.

- **Hecho:**
  - `test(cov)` (`e564043`): +25 tests en `tests/test_prompt_store_codex.py` para los
    métodos sin cubrir de `prompt_store.py`, reutilizando helpers/fixtures existentes
    (`_make_prompt_model`, `_make_list_model` —antes sin uso—, `_mock_session_ctx`,
    `store`/`mock_session`). Clases nuevas: `TestScheduledPrompts` (get_scheduled_prompts),
    `TestPromptLists` (create/get/update/delete/list_all_lists + `_list_to_dict` con y sin
    `updated_at`), `TestPromote` (promote_to_list happy + ramas prompt/list ausentes;
    promote_to_skill happy + prompt ausente; promote_to_mcp — los promote encadenan
    llamadas internas stubbeadas con AsyncMock para aislar ramas), `TestApproveStaged`,
    `TestInboxQueries` (captured/staged/archived con forma `{prompts,total,limit,offset}`)
    y `TestClose` (dispose + rama engine=None). Módulo: **63% → 95%** (única franja sin
    cubrir: `initialize()` 39-59, setup real de engine DB — omitido por brittleness, no
    aporta valor con mocks).
  - `chore(cov)` (`56ec0b6`): ratchet gate `make cov` **43% → 44%** (medido 45.51%,
    margen 1.51 pt; suites deterministas sin red/DB/tiempo). Actualizado comentario+nota
    del target en `Makefile` y cabecera+histórico+fila `prompt_*` de
    `docs/COVERAGE_ROADMAP.md` (44.60→45.51%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ · typecheck ✓ (0 errores) · test ✓
  (**537 pass** + 2 skip; eran 512) · cov ✓ (**45.51%** ≥ gate 44%, era 44.60%/gate 43).
  +0.91 pts. **Hito v0.2 = 45% alcanzado en medición real** (no sólo display). No se
  arrancó nada (ni gateway ni infra); sin procesos residuales; árbol limpio (3 commits
  atómicos).

- **DECISIÓN PENDIENTE (Jessicache) — sin cambios, ambas siguen abiertas:**
  (1) **bug bcrypt del funnel** (bcrypt 5.0.0 + passlib 1.7.4 incompatibles →
  `POST /auth/register` y login de usuario registrado darían 500 en runtime). Recomendación
  intacta: fijar `bcrypt<5` (p.ej. `bcrypt==4.0.1`) + `uv lock`. No se aborda sin
  aprobación (cambio de lockfile). (2) **frontend del funnel** (`/register` inexistente en
  `micelia/frontend`). Feature nueva + QA humano → fuera de alcance autónomo.

- **Bloqueado/pendiente:** el ratchet de mypy hacia `strict=true` sigue vivo (mejora, no
  bloquea). Dir legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand). Mayor gap
  restante de cobertura: `frangels/orchestrator.py` (17%, 289 stmts) y
  `google_calendar.py` (13%, 240 stmts).

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` +
  `uv lock`) + test de integración real register/login que ejercite `pwd_context` de
  verdad (cierra el funnel de punta a punta); (b) alternativa de cobertura de máximo gap:
  empezar `frangels/orchestrator.py` (17%) con mocks httpx de providers — es el mayor
  hueco restante en frangels/; o `google_calendar.py` con mock de la Google API. (c)
  arrancar el ratchet mypy activando `disallow_untyped_defs` en un subpaquete.

---

## 2026-07-10 — Ciclo 5 (funnel register→login testeado · auth.py 0→100% · cobertura 43.11→44.60% · gate 41→43)

**Contexto:** Ciclo 4 dejó `make verify` 100% verde con siguiente paso subir cobertura
hacia el hito v0.2 = 45%. La tarea reitera el objetivo #5 (funnel **register → login →
micelia**, subdominios de idmmortality.com, para la iteración inicial de marketing).
Reconocimiento encontró una convergencia fuerte entre prioridad #3 (cobertura) y ese
objetivo: el **backend del funnel está completo** (`POST /auth/register`, `/login`,
`/refresh`, `/me`, `/setup` en `app/api/v1/auth.py`; `UserModel`; `UserStore`) pero el
router del funnel tenía **cero tests de endpoint** — el `test_app` compartido en
`tests/conftest.py` ni siquiera monta `auth.router` ni fija `app.state.user_store`, y
`tests/test_auth.py` sólo cubre la auth por API-key de endpoints protegidos, no el
funnel. Testear ese router sube cobertura Y verifica el camino register→login del que
depende el marketing. Un solo commit de test, verify-verde, reversible. El hueco del
**frontend** (no hay página `/register`) queda como DECISIÓN PENDIENTE (fuera de alcance
autónomo seguro: feature nueva, QA humano, no verificable por `make verify`).

- **Hecho:**
  - `test(cov)`: `tests/test_auth_endpoints_codex.py` (17 tests) para el router funnel
    `app/api/v1/auth.py`. App mínima aislada que monta sólo `auth.router` e inyecta un
    `user_store` fake (AsyncMock); `httpx.AsyncClient` + `ASGITransport`. Cubre TODAS las
    ramas: register (201 auto-login, 409 duplicado, 503 sin store, 422 validadores
    email/password, normalización email), login (usuario registrado OK + `touch_last_login`,
    403 cuenta inactiva, fallback admin `.env`, 401 inválido, rama sin store), refresh
    (par válido, 401 tipo incorrecto, 401 JWTError), `/me` (parseo identidad con/sin `:`),
    `/setup` (403 ya configurado, 200 primera vez + mutación de settings). `jwt_auth`
    (jose) corre real; `audit_logger` no-op (event_store=None). Frontera cripto
    (`pwd_context.hash/verify`) stubbeada de forma determinista — obligatorio, ver
    DECISIÓN PENDIENTE bcrypt. Módulo: **0% → 100%** (91 statements, 0 sin cubrir).
  - `chore(cov)`: ratchet gate `make cov` **41% → 43%** (medido 44.60%, margen 1.60 pt;
    suites deterministas sin red/DB/tiempo). Actualizado el comentario+nota del target en
    `Makefile` y la cabecera+histórico de `docs/COVERAGE_ROADMAP.md` (43.11→44.60%).

- **Verify:** **`make verify` 100% VERDE** — lint ✓ · typecheck ✓ (0 errores) · test ✓
  (**512 pass** + 2 skip; eran 495) · cov ✓ (**44.60%** ≥ gate 43%, era 43.11%/gate 41).
  +1.49 pts. Hito v0.2 = 45% alcanzado en display (medido 44.60%, redondea a 45%). No se
  arrancó nada (ni gateway ni infra); sin procesos residuales; árbol limpio (2 commits
  atómicos).

- **DECISIÓN PENDIENTE (Jessicache) — bug real del funnel (bcrypt):** el venv actual trae
  **bcrypt 5.0.0 con passlib 1.7.4**, incompatibles: `pwd_context.hash()/verify()` lanzan
  `ValueError: password cannot be longer than 72 bytes` en la primera llamada (la sonda
  `detect_wrap_bug` de passlib peta con bcrypt ≥5). Consecuencia: **`POST /auth/register` y
  el login de usuario registrado darían 500 en runtime** en este entorno — el funnel de
  registro está roto. Ningún test lo ejercía antes, por eso pasó inadvertido. No lo arreglo
  autónomamente (bajar dependencia = cambio de `uv.lock` con riesgo de arrastre, sin
  supervisión). Recomendación: fijar `bcrypt<5` (p.ej. `bcrypt==4.0.1`, compatible con
  passlib 1.7.4) o migrar a `bcrypt` directo. Los tests de este ciclo stubbean la frontera
  cripto para probar la lógica del endpoint con independencia de este bug.

- **DECISIÓN PENDIENTE (Jessicache) — frontend del funnel:** backend del funnel completo,
  pero el frontend Next.js (`micelia/frontend`) NO tiene página `/register` ni método
  `authApi.register` (`src/lib/api.ts`); el formulario de login usa **username** mientras el
  modelo indexa por **email** (elección de contrato UX); `/register` habría que añadirlo a
  `PUBLIC_PATHS` en `src/middleware.ts`. Es feature nueva, con QA humano y no verificable por
  `make verify` → no se construye autónomamente; se decide cuándo abordarla.

- **Bloqueado/pendiente:** viva aún el ratchet de mypy (rearmar flags relajados uno a uno
  hacia `strict=true`; no bloquea, es mejora). Dir legacy `vital-core/docs/` sigue en el
  árbol (DoD §7 rebrand). Cobertura a 0.40 pts del 45.00% literal.

- **Mañana:** (a) si Jessicache aprueba, arreglar el bug bcrypt (fijar `bcrypt<5` + `uv lock`)
  y añadir un test de integración real de register/login que ejercite `pwd_context` de
  verdad — cierra el funnel de punta a punta; (b) alternativa de cobertura: `prompt_store.py`
  (63%, ~72 stmts sin cubrir, patrón CRUD ya probado) para pasar el 45.00% literal, o empezar
  `frangels/orchestrator.py` (17%, 289 stmts) con mocks httpx.

---

## 2026-07-10 — Ciclo 4 (cobertura 39% → 43% · dos módulos puros a ~100% · gate 37→41)

**Contexto:** Ciclo 3 dejó `make verify` 100% verde y como siguiente paso subir
cobertura hacia el objetivo v0.2 = 45%. Al orientarme encontré un test SIN commitear
en el árbol (`tests/test_prompt_os_agents_codex.py`, 23 tests) que cubría justo el
pendiente `prompt_os_agents` del COVERAGE_ROADMAP para `agents/`. Se validó (pasa,
0%→98%) y se commiteó. Prioridad #1 (rojo→verde) ya satisfecha; la tarea de máximo
valor desbloqueada es la #3 (cobertura). Reconocimiento eligió el siguiente módulo
más puro sin cubrir: `frangels/provider_store.py` (33%, misma frontera JSON/tmp_path
que quota_manager ya testeado). No se tocó ninguna decisión pendiente ni infra.

- **Hecho:**
  - `test(cov)` (`0ecd270`): `tests/test_prompt_os_agents_codex.py` (23 tests) —
    valida y committea el test que estaba en el working tree para
    `app/services/agents/prompt_os_agents.py`. Cubre los 4 agentes de Prompt OS
    (ingest/taxonomy/archivist/builder) + `_extract_json`; única frontera =
    `FrangelsOrchestrator` inyectado como `AsyncMock`. Módulo: **0% → 98%**.
  - `test(cov)` (`5f7a8a8`): `tests/test_provider_store_codex.py` (30 tests) para
    `app/services/frangels/provider_store.py`. Frontera = fichero encriptado
    `providers.enc` bajo `tmp_path` con Fernet real (round-trip genuino, no mock de
    cripto). Cubre `ProviderCredential.__post_init__`, `_load` (missing/round-trip/
    corrupt), rama de excepción de `_save` (write_bytes → OSError tragado),
    get/get_api_key, set (create+update), delete/enable/disable/mark_used
    (present+absent), list_configured/get_all_status, export_to_env y sync_from_env
    (ANGEL_REGISTRY real: groq + kaggle con extra_key) y el singleton.
    Módulo: **33% → 100%**.
  - `chore(cov)` (`73f6a57`): ratchet gate `make cov` **37% → 41%** (medido 43.11%,
    ~2 pts de margen, mismo criterio que Ciclo 3). Actualizada la nota del target,
    la cabecera de COVERAGE_ROADMAP.md (29.37%→43.11%) y la tabla de módulos:
    `agents/` cubierto, `frangels/provider_store` hecho; queda `frangels/orchestrator`
    (17%) como pendiente.

- **Verify:** **`make verify` VERDE COMPLETO** — lint ✓ · typecheck ✓ (0 errores) ·
  test ✓ (**495 pass** + 2 skip; eran 465) · cov ✓ (**43.11%** ≥ gate 41%, era
  39.06%/gate 37). +4.05 pts de cobertura. Nada arrancado (ni gateway ni infra);
  sin procesos residuales; árbol limpio (3 commits atómicos).

- **DECISIÓN PENDIENTE:** ninguna nueva. Sigue viva la del ratchet mypy (re-endurecer
  flags relajados de uno en uno hacia `strict=true`) — no bloquea nada, es mejora.

- **Bloqueado/pendiente:** falta ~1.9 pts para el objetivo v0.2 = 45%. Siguiente mejor
  objetivo por pureza/tamaño: `frangels/orchestrator.py` (17%, 289 stmts — el mayor
  gap restante en frangels/, pero requiere mockear providers httpx) o
  `prompt_store.py` (63%, 72 stmts sin cubrir, patrón CRUD ya conocido). Directorio
  legacy `vital-core/docs/` sigue en el árbol (DoD §7 rebrand, sin resolver).

- **Mañana:** cerrar el objetivo v0.2 = 45% con `prompt_store.py` (patrón CRUD ya
  probado en skills_manager/quota_manager, sube ~1 pt limpio) y/o empezar
  `frangels/orchestrator.py` con mocks de providers. Alternativa de igual valor:
  arrancar el ratchet mypy activando `disallow_untyped_defs` en un subpaquete.

---

## 2026-07-07 — Ciclo 3 (verify 100% VERDE por primera vez · 3 decisiones desbloqueadas)

**Contexto:** Jessicache autorizó las 3 DECISIONES PENDIENTES ("adelante los tres").
Con ellas desbloqueadas, la tarea del día es la prioridad #1 del protocolo: rojo→verde
en `make verify`, que nunca había estado verde (paraba en typecheck). Se aplicó el
baseline mypy pragmático (ya presente en pyproject) y se resolvieron los 128 errores
restantes; se cableó `calendar_name`; el commit raíz ya existía (aecb0ea/fd1ba50).

- **Hecho:**
  - `fix(types)`: 128 errores mypy resueltos en 23 ficheros (5 agentes paralelos,
    verificados centralmente). Patrones: `param: T = None`→`Optional[T]`; atributos de
    recurso None-init anotados a tipo concreto + `# type: ignore[assignment]` (contrato
    "initialize()/connect() primero"); var-annotated explícitas. **Bugs reales
    corregidos:** `google_calendar` llamaba `prompt_store.get_prompt_store()` (no existe)
    → usa `PromptStore()` con `initialize()/close()`; `frangels` leía
    `InferenceResult.cached` (no hay cache) → `False`; dicts inferidos demasiado
    estrechos (ai/routine/tunnel/service_registry/markdown_sync/prompt_agent/cli) →
    `dict[str, Any]`. Sin bare ignores.
  - `fix(osascript)`: `get_today_events` ahora honra `calendar_name` (antes recorría
    TODOS los calendarios ignorando el parámetro) — bug latente #2 resuelto.
  - `style(lint)`: 14 residuales ruff (SQLAlchemy `.isnot()/.is_()`, E402 noqa
    justificado en imports seccionales, E741, F841); `[tool.ruff]`→`[tool.ruff.lint]`.
  - `fix(deps)` + `test(cov)` (ya commiteados en ciclos previos de hoy): `coverage[toml]`
    para desbloquear `make cov`; `conftest` inserta `sdk/python` en sys.path (idm_sdk sin
    editable install); `tests/test_agents_crew.py` (agent_definitions/workflows/crew_manager).
  - `test(cov)`: `tests/test_service_registry_codex.py` (17 tests, httpx mockeado con
    AsyncMock — sin red ni infra) para `app/services/service_registry.py`. Cubre
    `_check_health` (200+versión, non-200, JSON inválido, timeout, connect-error, excepción
    genérica, servicio desconocido, recuperación), `_log_failure` (3 ramas de nivel),
    `check_service` (found/not-found), getters, `discover_services` (registro + hint) y
    `_continuous_monitoring` (un ciclo + cancelación, sleep monkeypatcheado). Módulo:
    **0% → 97%**.
  - `test(cov)`: `tests/test_context_assembler_codex.py` (21 tests) para
    `app/services/context_assembler.py` — deps inyectadas (prompt_store/skills_manager
    mockeadas), capas de filesystem con `tmp_path` + settings/cwd monkeypatcheados, capa
    temporal con datetime fijado (5 franjas horarias). Cubre `assemble` (todas/subset/vacío),
    las 5 capas y sus ramas de error, y el singleton. Módulo: **0% → 97%**.
  - `test(cov)`: `tests/test_prompt_agent_codex.py` (29 tests) para
    `app/services/prompt_agent.py` — helpers puros `_calculate_priority` (boosts de
    categoría/tags/programación/antigüedad + clamp) y `_find_group` (correlación/tags
    compartidos) probados directamente; pipeline async (`_classify_captured`,
    `_process_pending`, `_run_loop`, start/stop) con store/event_bus/taxonomy-runner
    mockeados y sleep monkeypatcheado. Módulo: **0% → 98%**.
  - `test(cov)`: `tests/test_scheduler_codex.py` (14 tests) para
    `app/services/scheduler.py` — `_process_scheduled` (sin store, vacío, mueve+publica,
    error de evento/store tragado), `_sync_calendar` (deshabilitado, conectado+sync, no
    conectado, error tragado; `get_google_calendar` parcheado), `get_status`, singleton,
    start/stop y `_run_loop` (ciclo + cancelación + rama de error). Módulo: **0% → 99%**.
  - `test(cov)`: `tests/test_prompt_executor_codex.py` (17 tests) para
    `app/services/prompt_executor.py` — `_reset_daily_counters`, `_call_model` (sin
    orchestrator, auto-upgrade paid en work/plan, excepción), `_review_output` (parse+clamp,
    número inválido, excepción), `_execute_prompt` (happy path + eventos, review en work,
    fallo de modelo, excepción→failed, errores de evento tragados), start/stop y `_run_loop`.
    Módulo: **0% → 100%**.
  - `chore(cov)`: gate de cobertura **28% → 37%** en `make cov` (ratchet; medido 39%).

- **Verify:** **`make verify` VERDE COMPLETO por primera vez** — lint ✓ · typecheck ✓
  (66 ficheros, 0 errores; eran 671) · test ✓ (413 pass + 20 SDK, 2 skip) · cov ✓
  (**39.06%** ≥ gate 37%, era 29.82%/gate 28). Nada arrancado (ni gateway ni infra); sin
  procesos residuales.

- **DECISIÓN PENDIENTE:** ninguna nueva. Las 3 de Ciclo 1 quedan **RESUELTAS**
  (autorizadas por Jessicache). Ratchet mypy: re-endurecer los flags relajados de uno en
  uno (`disallow_untyped_defs` → `disallow_untyped_calls` → `disallow_any_generics` → …)
  hacia `strict=true`.
- **Pendiente menor:** `app/models/user.py`, `app/services/user_store.py`,
  `tests/test_user_store_codex.py` (feature UserStore en curso de Jessicache) quedan SIN
  commitear en este ciclo (no son trabajo de la tarea diaria). Directorio legacy
  `vital-core/docs/` sigue en el árbol (DoD §7 rebrand).
- **Mañana:** arrancar el ratchet mypy (activar `disallow_untyped_defs` en un subpaquete
  y anotarlo) o subir cobertura hacia el objetivo v0.2 = 45%.

---

## 2026-07-07 — Ciclo 2 (cobertura +4.1 pts con módulos puros)

**Contexto:** las prioridades #1 (rojo→verde en verify) y #2 (roadmap) siguen
bloqueadas por decisiones humanas — typecheck mypy `strict=true` (671 errores) es
DECISIÓN PENDIENTE #1, y el commit raíz es DECISIÓN PENDIENTE #3. Con ellas
bloqueadas, la tarea de máximo valor **desbloqueada** es la prioridad #3: subir
cobertura (`docs/COVERAGE_ROADMAP.md`, objetivo v0.2 = 45%). Segura, reversible, no
toca ninguna decisión pendiente. Reconocimiento (Explore) eligió los dos módulos
sin cubrir más grandes y más puros (deps inyectadas → mockeables sin infra).

- **Hecho** (working tree, sin commitear — ver DECISIÓN PENDIENTE #3):
  - `test(cov)`: nuevo `tests/test_workflow_engine_codex.py` (24 tests) para
    `app/services/agents/workflow_engine.py`. Cubre helpers puros (`_reviewer_passed`,
    `_critic_requires_patch`, `_find_step_index`, `_update_context`, `get_runs/get_run`)
    y `execute_workflow` async con `AsyncMock` (workflow desconocido, prompt-not-found,
    happy path objeto+dict, retry reviewer-falla→pasa, excepción del orchestrator,
    ciclo de auditoría `entire_service` + tolerancia a fallo de `start_session`).
    Módulo: 0% → **80%**.
  - `test(cov)`: nuevo `tests/test_quota_manager_codex.py` (21 tests) para
    `app/services/frangels/quota_manager.py` usando `tmp_path` (única frontera = JSON)
    y el `ANGEL_REGISTRY` real. Cubre `record_usage`/`_check_reset` (reset diario/minuto
    + persistencia), `can_use` (4 ramas de límite + paid special-case + desconocido),
    `get_quota_status` (4 ramas + cap de % + is_exhausted + None), `get_usage_stats`
    (agregación hoy/mes robusta a fecha), `get_best_provider` (filtros capacidad +
    exclusión por cuota + orden por tier + fallback categoría), `_load/_save` round-trip
    y singleton cacheado. Módulo: 0% → **96%** (angels.py de paso a 97%).
  - `chore(cov)`: gate `make cov` `--cov-fail-under` 25 → **28** (Makefile:230) +
    textos del target actualizados. Roadmap actualizado: medición 29.37%, tabla de
    prioridades marca agents/ y frangels/ como cubiertos, historial de deltas.

- **Verify:** `make lint` VERDE · `make test` VERDE (305 pass + 20 SDK) ·
  `make cov` VERDE (**29.37%** ≥ 28%, era 25.28%) · `make typecheck` **ROJO**
  (mismos 671 errores; los tests NO se type-checkean → 0 errores nuevos, NO es
  regresión). `make verify` sigue parando en typecheck (etapa 2), igual que Ciclo 1.
  Cobertura +4.09 pts (25.28% → 29.37%). Nada arrancado (ni gateway ni infra);
  sin procesos residuales.

- **Bloqueado/pendiente:** verify 100% verde sigue bloqueado SOLO por typecheck
  (DECISIÓN PENDIENTE #1). Las 3 DECISIONES PENDIENTES de Ciclo 1 siguen abiertas
  sin cambios (no se tocaron hoy por guardarraíles).

- **Mañana:** seguir subiendo cobertura por el ranking del reconocimiento — siguiente
  mejor objetivo puro: `app/services/context_assembler.py` (0%, deps inyectables) o
  `app/services/skills_manager.py` (helpers puros + patrón CRUD de prompt_store).
  Recordar a Jessicache las 3 DECISIONES PENDIENTES: sin (1) no hay verify 100% verde;
  sin (3) la historia atómica no arranca (2 ciclos ya acumulados en working tree).

---

## 2026-07-07 — Ciclo 1 (rojo → verde en verify: 3 de 4 etapas)

**Contexto:** primera ejecución real del protocolo. Descubierto que `make verify`
**nunca había estado en verde** (repo en `master` con 0 commits) y estaba rojo en 3
de sus 4 etapas. Prioridad #1 del protocolo (rojo→verde) aplicada.

- **Hecho** (cambios en working tree — ver DECISIÓN PENDIENTE 3 sobre commits):
  - `fix(deps)`: añadido `coverage[toml]>=7.5` a extras `dev` en `pyproject.toml` +
    `uv lock`/`uv sync`. Además, la dep `coverage` estaba **rota** en el venv
    (dist-info presente, paquete ausente) → `uv pip install --reinstall coverage`.
    El `uv sync` reconcilió el venv a `uv.lock` (estaba drifteado: redis 5→7,
    starlette/uvicorn/sqlalchemy realineados, torch eliminado — ya declarado fuera).
  - `fix(cov)`: `make cov` tenía 2 bugs además de la dep: (a) `ModuleNotFoundError`
    de coverage; (b) corría `tests/ sdk/python/tests/` en una pasada y el import
    `idm_sdk` reventaba (la suite dependía de un editable install que `uv sync`
    quitó). Solución reproducible: `tests/conftest.py` inserta `sdk/python` en
    `sys.path`. Con eso la pasada combinada funciona (importlib evita la colisión).
  - `test`: nuevo `tests/test_agents_crew.py` (26 tests) para módulos puros sin infra
    (`agent_definitions`, `workflows`, `CrewManager` con engine mockeado). Sube
    cobertura 23.97% → **25.28%**, cruzando el gate de 25% con tests de valor real
    (opción (a) del plan, no bajar el gate).
  - `style(lint)`: `ruff --fix` (151 auto) + 14 residuales a mano. Destacado: los
    `!= None`/`== True` en `prompt_store.py`/`skills_manager.py` eran filtros
    SQLAlchemy → corregidos a `.isnot(None)`/`.is_(True)` (preservan el SQL, no
    `is`). E402 en `security.py` (imports seccionales) con `# noqa` justificado.
    Movida config ruff a `[tool.ruff.lint]` (quita warning de deprecación).
  - `chore(gitignore)`: endurecido antes de cualquier commit — `*token*.json`,
    `*credential*.json`, `secrets/`, `*.pid`, `data/frangels/`, `data/credentials/`.
    Auditoría `git status`: ningún fichero sensible quedaría stageado (`.env`,
    `data/frangels`, `google_token.json`, pids ya ignorados). Los `frangels/*.py`
    que matchean el grep son CÓDIGO fuente, no secretos → se trackean.

- **Verify:** `make lint` VERDE · `make test` VERDE (260 pass, 2 skip) ·
  `make cov` VERDE (**25.28%** ≥ 25%) · `make typecheck` **ROJO** (mypy `strict=true`,
  671 errores). `make verify` para en typecheck (2ª etapa). Progreso: 3/4 etapas
  rojas→verdes. Nada arrancado (ni gateway ni infra); sin procesos residuales.

- **Bloqueado/pendiente:** typecheck no puede ir a verde sin decidir política de tipado.

- **DECISIÓN PENDIENTE (Jessicache):**
  1. **mypy `strict=true` → 671 errores** (pyproject.toml:113). ~518 son completitud
     de anotaciones (no-untyped-def/type-arg/no-untyped-call), ~120 categorías de bug
     real. Recomendado: baseline pragmático + ratchet (aflojar completitud, mantener
     detección de bugs, arreglar los ~120, documentar re-endurecimiento). Alternativa:
     anotar incremental (semanas). Sin esto, verify no llega a 100% verde.
  2. **Bug latente encontrado**: `osascript.py` construía `calendar_filter` desde
     `calendar_name` pero NUNCA lo interpolaba en el AppleScript (el filtro por
     calendario no funcionaba). Eliminé el código muerto para el lint; **el filtrado
     por calendario sigue sin implementarse** — decidir si se cablea o se retira el
     parámetro `calendar_name` de la API.
  3. **Primer commit del repo (0 commits).** Los cambios de hoy están en el working
     tree SIN commitear: crear el commit raíz del orquestador (qué incluir: docs
     legales, dir legacy `vital-core/`, `.github/`, estrategia de atomicidad) es una
     decisión fundacional/irreversible → no la tomo autónomamente. Todo listo para
     commitear cuando se decida el alcance del baseline.

- **Mañana:** si Jessicache aprueba (1) baseline mypy pragmático → aplicarlo, arreglar
  los ~120 errores de bug real hasta typecheck verde → primer `make verify` 100% verde.
  En paralelo, decidir (3) el commit raíz para empezar a acumular historia atómica.

---

## 2026-07-07 — Baseline (entrada inicial, escrita por Claude al crear el protocolo)

- Estado: gateway arranca en local vía `scripts/run-local.sh` (:8888, Python 3.13,
  degradación elegante sin Postgres). Frontend Next.js en :3001.
- Verify: cobertura ~24% con gate en 25% (`docs/COVERAGE_ROADMAP.md`; objetivo v0.2 = 70%).
- Pendiente heredado de `docs/DEPLOY_LOCAL_2026-06-09.md`: OAuth propio de calendar
  (`data/google_token.json`), `make docker-infra` para event sourcing + AI local,
  arrancar biohack-app (:8080) para cerrar bucle HRV/sueño, integrar canela-molida e
  ideacursi-tool (ya descomprimidos como carpetas hermanas) al perfil `full`.
- Roadmap: continuar por la siguiente fase pendiente de `docs/PLAN_MICELIA_v0.md`.
- Mañana: ejecutar el ciclo del protocolo `DAILY_MICELIA_PLANNING.md` (raíz de projects/).
