# Cobertura de tests — roadmap

**Versión**: v0.1
**Última medición**: 2026-07-07 — **29.37%** sobre 6.765 statements en `app/` (1.987 cubiertos, 4.778 sin cubrir). Gate `make cov` = **28%**. Medición previa: 24.09% (2026-05-24) → 25.28% (Ciclo 1) → 29.37% (Ciclo 2)

---

## Decisión

El gate de `make cov` en v0.1 es **25%** (baseline conservador justo por encima de la medición actual). Esto es intencionalmente bajo y honestamente reconocido.

**Por qué NO forzamos 70% en v0.1**:

- Subir de 24% → 70% requiere ejercitar ~4.700 statements adicionales con tests
- Eso es trabajo de 1-2 semanas dedicadas a escribir tests por encima de una superficie de código que aún está evolucionando
- Forzar el threshold ahora produciría dos malos resultados: (a) bloquear la release indefinidamente, o (b) inflar la cobertura con tests "de paso" sin valor real
- El estado real del proyecto se describe mejor publicando un baseline bajo y un compromiso explícito de subida progresiva

**Por qué 25% y no menos**:

- Asegura que la cobertura no retroceda accidentalmente respecto a lo que ya existe
- Es 0.91 puntos por encima de la medición actual (24.09%) — pasa hoy con margen pero detecta regresiones futuras

---

## Estado actual por módulo (orden de prioridad para subir cobertura)

Módulos críticos del orquestador identificados con baja cobertura. Cada uno representa una oportunidad de progreso medible hacia el objetivo v0.2.

### Alta prioridad (core funcional, alta superficie sin tests)

| Módulo | Razón | Plan v0.2 |
|---|---|---|
| `app/services/agents/` | Sistema multi-agente. Crítico operativamente, suite E2E no lo toca | ✅ crew_manager + agent_definitions + workflows (Ciclo 1), workflow_engine 80% (Ciclo 2). Pendiente: prompt_os_agents |
| `app/services/frangels/` | Orquestación de providers IA. Crítico para AI sovereignty | ✅ policy_engine 100%, quota_manager 96%, angels 97% (Ciclo 2). Pendiente: orchestrator (17%), provider_store (33%) con mocks de providers |
| `app/services/prompt_*` | Pipeline completo de prompts (store, agent, executor, scheduler) | Tests de happy path por cada etapa del pipeline |
| `app/api/v1/ai.py` | Endpoint integración modelos. Tocado tangencialmente por T3.1 | Tests directos de cada endpoint con mocks de proveedor |
| `app/api/v1/prompts.py` | API de prompts. No cubierta por E2E | Tests CRUD básicos |

### Media prioridad

| Módulo | Razón | Plan v0.2 |
|---|---|---|
| `app/api/v1/skills.py`, `mcp.py`, `agents.py` | APIs especializadas | Tests de contrato con mocks |
| `app/services/skills_manager.py` | Gestión dinámica de skills | Tests CRUD + activación |
| `app/services/google_calendar.py` | Integración externa | Tests con mock de Google API |
| `app/services/tunnel.py` | ngrok wrapper | Tests con mock pyngrok |
| `app/core/security.py` | API key + rate limiting | Tests del rate limiter aún saltados en E2E (T3.2) |

### Baja prioridad (cobertura indirecta o intencionalmente no testeada)

| Módulo | Razón |
|---|---|
| `app/cli.py` | CLI; sólo se ejercita en startup via `micelia start`. Tests requerirían subprocess + colaboración con uvicorn |
| `app/services/osascript.py` | macOS-specific, no portable a CI Linux |
| `app/main.py` lifespan | Ya cubierto por arranque de la suite E2E vía `_build_test_app` |

---

## Hoja de ruta cuantitativa

| Release | Threshold | Plan |
|---|---|---|
| **v0.1** | **25%** | Baseline honesto. Garantiza no regresión. (HOY) |
| **v0.2** | **45%** | Tests alta prioridad: agents/, frangels/, prompt_* |
| **v0.3** | **60%** | Tests media prioridad: APIs v1 + skills + integraciones externas con mocks |
| **v0.4** | **70%** | Subir prioridad baja + eliminar gaps residuales |
| **v1.0** | **80%** | Auditoría completa antes de release marca registrada |

Cada salto exige unos 5-10 PRs de tests específicos. El roadmap es honesto: 70% en v0.1 era objetivo aspiracional; 70% en v0.4 (con plan medible) es objetivo realista.

---

## Cómo contribuir tests para subir el baseline

1. Elegir un módulo de la sección "Alta prioridad" sin asignar
2. Abrir issue con el módulo elegido para evitar duplicidad de trabajo
3. Escribir tests que mockeen las fronteras externas (BD, HTTP, providers IA)
4. PR con un commit de tests + un commit que suba el `--cov-fail-under` del Makefile en el delta alcanzado
5. Revisión sigue el patrón de `docs/CLA.md` + `.github/PULL_REQUEST_TEMPLATE.md`

---

## Métricas de seguimiento

Cada PR debe reportar el delta de cobertura. Cuando se llegue a uno de los hitos del roadmap, actualizar este documento y el threshold del Makefile en el mismo PR.

Comando para medir local:

```bash
make cov     # corre con threshold actual
make cov --cov-fail-under=0   # corre sin gate (info-only)
```

Reporte HTML granular en `htmlcov/index.html` tras cualquier ejecución de `make cov`.
