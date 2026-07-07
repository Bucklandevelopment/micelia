# Micelia SaaS Blueprint

## North Star

Convertir `Micelia` (ex-`idm-core`) en un producto SaaS local-first que corre en un Mac Studio, se expone inicialmente por `ngrok`, y mas adelante por `idmmortality.com`.

El sistema debe sentirse humano, continuo y utilitario:

- una web siempre accesible
- una inbox viva de prompts y notas rapidas
- agentes que priorizan, ejecutan, revisan y archivan
- integracion con Google Calendar
- generacion de skills y servidores MCP desde la misma interfaz
- gestion unificada de proveedores free y paid mediante Frangels

## Lo Que Ya Existe

El repo ya contiene una base bastante buena:

- `FastAPI` con lifecycle y background services
- `PromptStore`, `PromptPrioritizationAgent`, `PromptExecutor`
- `PromptScheduler` con sincronizacion de Google Calendar
- `Frangels` para proveedores y cuotas
- generacion de `skills` dinamicas
- generacion de servidores `MCP`
- UI `Next.js` con vistas de prompts, calendario, skills, settings y agentes

## Lo Que Falta Para Ser Producto

Hoy las piezas existen, pero aun no forman un solo sistema operativo de trabajo:

- no hay una arquitectura explicita de "Prompt OS"
- las notas rapidas no tienen una segunda vida clara hacia archivos MD y listas persistentes
- la taxonomia de prompts, skills y MCP aun no esta unificada
- la UI no comunica bien el ciclo completo: capturar -> clasificar -> planificar -> ejecutar -> revisar -> archivar
- Frangels gestiona credenciales, pero no una politica de presupuesto por usuario, dominio o flujo
- ngrok esta pensado como capacidad tecnica, no como capa de producto publica

## Decision Arquitectonica Principal

No conviene meter un framework externo de orquestacion como primera pieza obligatoria.

La mejor ruta para `Micelia` es:

1. mantener el workflow engine propio como nucleo
2. convertirlo en un motor de estados mas riguroso
3. usar CrewAI/LangGraph solo si despues necesitamos mas expresividad o tooling
4. usar `entire` como capa de trazabilidad y auditoria para sesiones de agentes, no como la cola principal de prompts

Nota sobre `entire`:

- segun el README del repositorio `entireio/cli`, su foco es engancharse al flujo de Git para capturar sesiones de agentes, checkpoints y contexto de cambios
- eso lo hace valioso para auditoria, rewind y trazabilidad
- no sustituye la cola operativa de prompts 24/7 que `Micelia` necesita

## Arquitectura Objetivo

```text
Usuario
  ->
Prompt UI / Dashboard
  ->
Prompt OS API
  ->
Prompt Inbox + Prompt Queue + Prompt Memory
  ->
Prioritizer Agent (cada 5s)
  ->
Workflow Router
  ->
Subagentes: planner -> executor -> reviewer -> critic -> patcher
  ->
Resultado + archivado + sync MD + calendario + skills/MCP
```

## Capas Del Sistema

### 1. Appliance Layer

Instalacion plug and play para Mac Studio:

- Docker Compose para infraestructura
- backend FastAPI
- frontend Next.js
- proceso persistente tipo `launchd` o supervisor
- secretos locales
- almacenamiento local-first

### 2. Exposure Layer

Primera etapa:

- `ngrok` para exponer frontend y API
- dominio temporal y seguro
- acceso remoto personal

Segunda etapa:

- proxy formal para `idmmortality.com`
- TLS
- autenticacion de usuarios
- rate limiting y session controls

### 3. Prompt OS Layer

Es el corazon del producto:

- inbox de notas rapidas
- listas de prompts reutilizables
- colas de ejecucion
- motor de priorizacion
- clasificador de etiquetas
- scheduler y recurrentes
- sincronizacion con archivos markdown

### 4. Intelligence Layer

Motor multi-modelo y multi-agente:

- Frangels decide proveedor y presupuesto
- workflow engine decide pipeline
- reviewer y critic detectan inconsistencias
- patcher recompone outputs si hace falta

### 5. Capability Layer

Capacidades generadas o cargadas dinamicamente:

- `skills`
- servidores `MCP`
- adapters de calendario
- adapters de notas
- adapters de repositorios y monorepos

### 6. Memory and Audit Layer

Persistencia util:

- PostgreSQL para prompts, estados y runs
- Redis para eventos y señales cortas
- archivos MD como memoria editable por humanos
- `entire` para trazabilidad de sesiones de agentes ligadas al codigo

## Modelo Operativo De Producto

### Modo 1: Live Capture

El usuario escribe:

- una nota rapida
- una idea
- una tarea
- una duda
- una orden para un subagente

El sistema la guarda inmediatamente en la inbox.

### Modo 2: Continuous Triage

Cada 5 segundos el priorizador:

- escanea nuevas entradas
- detecta categoria
- asigna prioridad
- agrupa por correlacion
- decide si:
  - se ejecuta ya
  - se agenda
  - se archiva como conocimiento
  - se promueve a lista recurrente
  - se convierte en skill o propuesta MCP

### Modo 3: Managed Execution

Cuando un prompt es ejecutable:

- se selecciona workflow
- se escoge proveedor
- se aplican skills relevantes
- se adjuntan adapters MCP si procede
- se ejecuta
- se revisa
- se guarda el resultado

### Modo 4: Knowledge Promotion

Los resultados valiosos pasan a:

- markdown persistente
- listas de rutina
- listas de trabajo
- listas de proyectos
- skills nuevas
- plantillas MCP

## Frangels Como Modulo Paid and Free

Frangels debe evolucionar de "provider switcher" a "policy engine".

Politicas propuestas:

- `free-first`: usa gratis salvo que falle el SLA
- `paid-for-work`: prompts laborales y estrategicos pueden subir a paid
- `critical-reviewed`: fuerza executor + reviewer en proveedores distintos
- `privacy-high`: restringe a proveedores permitidos
- `budget-cap`: no superar techo diario o mensual

Nuevas entidades recomendadas:

- provider profile
- billing policy
- budget
- route policy
- fallback chain

## Google Calendar En El Producto

No debe ser un add-on aislado. Debe actuar como una fuente y destino de contexto:

- eventos entran como triggers de prompts
- bloques de tiempo ayudan a priorizar
- resultados pueden convertirse en eventos o resumentes
- rutinas diarias pueden dispararse por hora
- reuniones pueden crear prompts previos y posteriores

## Dashboard Humano

La UI principal debe girar alrededor de una sola experiencia:

- inbox
- cola activa
- agenda
- resultados
- skills
- MCP
- presupuesto

Pantallas recomendadas:

1. Home / Mission Control
2. Prompt Inbox
3. Prompt Lists
4. Runs y Review
5. Calendar
6. Skills y MCP Factory
7. Providers y Budget
8. Audit / Entire Sessions

## Roadmap Propuesto

### Fase 1. Prompt OS Basico

- unificar taxonomia
- definir estados reales del prompt
- separar inbox, queue, archive y recurring
- sync basico con archivos MD

### Fase 2. Dashboard Operativo

- crear una UX mas humana alrededor de inbox y ejecucion
- mostrar workflows, riesgo, coste y agenda
- mejorar estados de pipeline

### Fase 3. Frangels Policy Engine

- budgets
- paid/free routing
- reglas por categoria
- fallback inter-provider

### Fase 4. Skill and MCP Factory

- sugerir skills desde prompts recurrentes
- sugerir MCP desde patrones operativos
- crear adapters reutilizables

### Fase 5. Public Exposure

- endurecer auth
- ngrok estable
- preparacion para `idmmortality.com`
- observabilidad y alertas

## Cambios De Codigo Recomendados A Continuacion

Orden sugerido para la siguiente iteracion:

1. ampliar `PromptStatus` y `PromptModel` para reflejar inbox, staging, review y archive
2. crear una politica de sincronizacion `DB <-> Markdown`
3. añadir `Prompt OS` endpoints para clasificacion, promocion y archivado
4. rediseñar la pagina de prompts como inbox operativa
5. crear modulo de presupuesto y routing en Frangels
6. unir skills, MCP y prompt templates bajo una misma taxonomia

---

## Estado De Implementacion (Actualizado 2026-03-13)

### Por Capa

| Capa | Cobertura | Detalle |
|------|-----------|---------|
| Appliance Layer | ~80% | Docker Compose, FastAPI, Next.js, .env local. Falta launchd/supervisor |
| Exposure Layer | ~60% | ngrok service + API + indicador frontend. Falta TLS, auth publica, idmmortality.com |
| Prompt OS Layer | ~50% | PromptStore, Agent 5s, Executor 3 concurrent, Scheduler, Lists MD. Falta inbox/staging/archive/sync MD |
| Intelligence Layer | ~60% | Frangels multi-provider con paid, WorkflowEngine 3 workflows, reviewer. Falta policy engine y budgets |
| Capability Layer | ~70% | SkillsManager + MCPGenerator + Calendar adapter. Falta auto-suggest de skills y MCP |
| Memory and Audit | ~40% | PostgreSQL + Redis + MD files. Falta entire integration y audit trail |

### Gaps Criticos

- Frangels Policy Engine: solo hay `prefer_paid` boolean, no existe routing por politica (free-first, paid-for-work, critical-reviewed, privacy-high, budget-cap)
- Entidades de billing: provider profile, billing policy, budget, route policy, fallback chain no existen
- `entire` CLI: no integrado
- Knowledge Promotion: no hay flujo automatico de resultados valiosos a markdown persistente
- Mission Control: la home es dashboard de sistema, no de prompts
- Auth para acceso remoto: no implementado

### Implementado Desde El Blueprint

- FastAPI lifecycle con background services
- PromptStore + PromptPrioritizationAgent + PromptExecutor
- PromptScheduler con Google Calendar sync
- Frangels para proveedores free (18) y paid (OpenAI, Anthropic)
- Skills dinamicas con CRUD y trigger por regex
- Servidores MCP generados desde descripcion (Python/TypeScript)
- UI Next.js con paginas: prompts, monitor, lists, calendar, skills, agents
- ngrok tunnel con start/stop/status API
- Multi-Agent system: CrewManager + WorkflowEngine + 5 agent types
- 50+ endpoints API total

