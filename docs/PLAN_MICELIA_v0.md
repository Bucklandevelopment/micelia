# Plan de desarrollo — vital-core → MiceliA v0.1

> Plan operativo para renombrar `vital-core` (el orquestador central FastAPI)
> a **MiceliA** — el sistema socioeconómico donde cada persona es un nodo que
> contribuye al progreso colectivo con IA y recibe cobertura de necesidades básicas.
>
> **IMPORTANTE**: Micelia ES vital-core renombrado (el orquestador), NO biohack-app.
> `biohack-app` es un repo hermano que consume la API de Micelia como dominio de salud.
>
> Documento de referencia: [`Micelia_Nodo1_Impacto_Socioeconomico.md`](../../Micelia_Nodo1_Impacto_Socioeconomico.md)
>
> Fecha: 2026-05-21 · Owner técnico: Jessicache (Nodo 1)

---

## 0. Contexto verificado

| Pieza | Estado actual | Implicación |
|---|---|---|
| `vital-core` (FastAPI) | `app/` con API v1 ya cableada (auth, gateway, ai, events, prompts, skills…). Banner "IDM-CORE". | **Este ES Micelia.** El rebrand es textual, no estructural. vital-core → Micelia. |
| Tests | `tests/` con 8 archivos, ~2.5k líneas. `conftest.py` ya monta una app FastAPI con mocks (`AsyncMock`/`MagicMock`). | Reutilizamos el patrón existente; añadimos sólo `respx` para mockear el upstream HTTP. |
| Frontend (Next.js 14) | `frontend/` en port 3001, scripts `dev/build/start/lint/type-check`. | QA UI se hace manualmente con el usuario (no Chrome agent). |
| `biohack-app` | Repo hermano (`../biohack-app/backend`) referenciado desde `docker-compose.yml`. **Consumidor** de la API de Micelia para el dominio de salud. No se renombra. | T0.1 inspecciona su contrato con Micelia. Mantiene alias compat `"biohack"`. |
| Contrato biohack ↔ Micelia | Extraído de código actual: `/api/v1/health{,/live,/ready,/detailed,/services}`, `/api/v1/bio-savant/chat`, `/api/v1/ml-production/predict`. Source-id `"biohack"` representa el **dominio funcional salud** (junto a `canela`, `ideacursi`, `cybertools`, `auto-mat-ion`), NO el orquestador. | Base para los mocks (T2.x). Política source-id revisada en T1.4. |
| Sources válidos de eventos | `app/sdk/models.py:47` enumera: `biohack, canela, ideacursi, cybertools, auto-mat-ion` (5 dominios funcionales). | El rebrand del orquestador NO renombra ningún dominio. T1.4 evalúa AÑADIR `"micelia"` como 6º source para eventos internos del propio orquestador. |

### Aclaración de arquitectura

```
vital-core (orquestador) ──renombrado──→ MICELIA
    │
    ├── biohack-app (dominio salud, repo hermano, consume API de Micelia)
    ├── canela-molida (motor de conocimiento científico RAG)
    ├── ideacursi-tool (plataforma de formación + tareas)
    └── auto-mat-ion (red social de testing/validación de dispositivos)
```

## 1. Decisiones tomadas

1. **Micelia = vital-core renombrado** — el orquestador central. `biohack-app` es un dominio consumidor, no el origen.
2. **Cobertura E2E inicial** = `pytest + httpx + respx` (API/backend). El frontend va por QA manual asistido por el usuario.
3. **Rebrand fase 1** = solo strings, naming y copy. Sin identidad visual ni cambios de dominio.
4. **biohack-app** = inspeccionar el repo hermano primero (T0.1) para verificar contrato de consumo con Micelia; no se renombra.
5. **Modo navegador** = el usuario pega en el chat consola/network/screenshots. Sin Chrome MCP, sin computer use.
6. **Compatibilidad** = el rebrand del orquestador mantiene `idm` (CLI, package) como **alias retrocompat** de `micelia` durante una versión. Los 5 source-id de dominio (biohack, canela, ideacursi, cybertools, auto-mat-ion) NO se tocan — representan dominios funcionales distintos del orquestador.

## 2. Roadmap por fases

```
FASE 0  Discovery & bootstrap
  T0.1  Inspección biohack-app (cuando esté montado)        [Explore quick]
  T0.2  Bootstrap pytest + respx + tests/e2e/               [general-purpose]

FASE 1  Rebrand vital-core → MiceliA (solo strings)
  T1.1  Plan detallado de rebrand                           [Plan]
  T1.2  Docs y copy                          (worktree)     [general-purpose]
  T1.3  Strings de código (FastAPI title, CLI, logs)        [general-purpose]
  T1.4  Política source-id (añadir "micelia" como 6º source) [general-purpose]
  T1.5  Verificación post-rebrand                           [Explore thorough]

FASE 2  Mocks aislados del dominio salud (biohack-app como consumidor)
  T2.1  Contrato Pydantic (API Micelia ↔ biohack-app)      [Plan]
  T2.2  Mock server con respx                               [general-purpose]
  T2.3  Datos sintéticos (perfiles, biomarkers)             [general-purpose]

FASE 3  Batería E2E con pytest+httpx
  T3.1  Happy path                                          [general-purpose]
  T3.2  Error paths y resiliencia                           [general-purpose]
  T3.3  Gateway proxy /api/v1/health/*                      [general-purpose]
  T3.4  Ciclo de eventos                                    [general-purpose]
  T3.5  SDK Python                                          [general-purpose]

FASE 4  QA frontend asistido (humano + claude)
  T4.1  Dev server Next.js + backend mock                   [general-purpose]
  T4.2  Sesión manual: tú navegas, pegas errores            [colaborativo]
  T4.3  Fixes iterativos                                    [general-purpose]

FASE 5  Validación final
  T5.1  Cobertura ≥70%                                      [general-purpose]
  T5.2  Revisión independiente                              [Plan]
  T5.3  Release notes MiceliA v0.1                          [general-purpose]
```

## 3. Equipo de subagentes — convenciones

| Subagent type | Cuándo usarlo | Cómo invocarlo |
|---|---|---|
| **Plan** | T1.1, T2.1, T5.2 — planificación, contratos, auditoría. Sólo lectura. | Brief con archivos y la pregunta. Sin código. |
| **Explore** (quick / medium / thorough) | T0.1, T1.5 — búsquedas exhaustivas y mapeos. Sólo lectura. | Especificar amplitud según el alcance. |
| **general-purpose** | Toda la implementación. | Cada tarea de la lista TaskCreate ya tiene `subject` + `description` autocontenidos. |
| Isolation `worktree` | T1.2 y cualquier tarea con riesgo de churn grande en docs. | Permite descartar si no satisface y reintentar. |

**Reglas:**
- Antes de spawnnear un agente nuevo, revisar si hay uno reciente que se pueda continuar con `SendMessage` (resume con contexto completo).
- Cada agente recibe un brief autocontenido: rutas absolutas, líneas exactas, archivos a tocar/no tocar, criterio de éxito (test verde, grep limpio).
- Tras cada Task, ejecutar el bloque de **verificación** (último item de la descripción) antes de marcar `completed`.

## 4. Convención de mocks

- **Library**: `respx` (intercepta httpx in-process, sin servidor adicional).
- **Fixture central**: `micelia_mock` en `tests/e2e/conftest.py` con parámetro
  `mode: Literal["healthy", "degraded", "down", "slow"]`.
- **Contratos**: `tests/e2e/mocks/contracts.py` exporta los modelos Pydantic;
  cualquier desviación entre mock y respuesta real de biohack-app rompe los
  tests intencionadamente (T0.1 cierra el ciclo cuando inspeccionemos el repo).
- **Datos**: `tests/e2e/fixtures/data.py` con `random.Random(seed=42)` para
  reproducibilidad estricta.

## 5. Cómo lo orquestamos (loop operativo)

1. `TaskList` para ver qué hay `pending` sin dependencias bloqueantes.
2. Para cada tarea desbloqueada → `TaskUpdate status=in_progress` + spawnear
   subagente del tipo indicado con la descripción como brief.
3. Recibir resultado, **verificar** ejecutando lo que pide el criterio
   (pytest, grep, lint) directamente, no en confianza ciega.
4. `TaskUpdate status=completed` o devolverlo a `in_progress` con un comentario
   si falta algo.
5. Tras cerrar una fase, hacer una mini-retro: ¿algo descubierto que añade
   tareas? → `TaskCreate` adicional.

## 6. Riesgos conocidos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Confundir capas: renombrar el dominio `biohack` cuando lo que cambia es el orquestador. | Decisión explícita en T1.1 + T1.4 reescrita: los 5 dominios NO se renombran. Test que valida que los 5 sources siguen siendo válidos (T3.4). |
| Romper consumidores del SDK `IdmClient`. | Alias `IdmClient = MiceliaClient` con DeprecationWarning (T3.5). |
| Mock se desvía del contrato real de biohack-app. | T0.1 cuando se monte el repo + T5.2 revisión cruzada. |
| QA manual del frontend se vuelve interminable. | Acotar T4.2 a 4 flujos concretos (login, dashboard salud, bio-savant, eventos). |
| `pytest` lento por dependencia de Ollama/Postgres. | Tests E2E **nunca** tocan infra externa: todo va a través de mocks. |
| Doc `Micelia_Nodo1_Impacto_Socioeconomico.md` no accesible en sesión. | Bloquea sólo el último item del DoD. Pedir al usuario que lo monte cuando llegue T5.3. |
| Sobre-scope del rebrand. | Política explícita: fase 1 = strings y copy. Identidad visual y dominio quedan para v0.2. |

## 7. Definition of Done (MiceliA v0.1)

- [ ] `pytest -x` verde con 100% de los tests existentes + nuevos E2E.
- [ ] `pytest --cov=app --cov-fail-under=70` pasa.
- [ ] `grep -RE "IDM-CORE|IDMMORTALITY|vital.core" --include="*.{py,ts,tsx,md}"` no devuelve nada salvo en la sección "Legado" del README.
- [ ] Alias CLI/package `idm ↔ micelia` documentado y testeado.
- [ ] Los 5 dominios funcionales (`biohack`, `canela`, `ideacursi`, `cybertools`, `auto-mat-ion`) siguen siendo source-id válidos sin warnings.
- [ ] `"micelia"` añadido como 6º source para eventos internos del orquestador (si T1.1 lo aprueba).
- [ ] Frontend arranca contra mock backend y los 4 flujos críticos funcionan.
- [ ] `docs/RELEASE_NOTES_MICELIA_v0.1.md` publicado.
- [ ] Documento [`Micelia_Nodo1_Impacto_Socioeconomico.md`](../../Micelia_Nodo1_Impacto_Socioeconomico.md) actualizado con estado de la tarea T0.

---

> Siguiente acción: cuando me confirmes, arrancamos con **T0.2** (bootstrap) en
> paralelo con **T1.1** (plan de rebrand). T0.1 espera a que montes el repo
> hermano `biohack-app` en la sesión.
