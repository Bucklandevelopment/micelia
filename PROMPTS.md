# PROMPTS.md alias dispatcher

## Objetivo

Definir el sistema de prompts de `Micelia` como un "Prompt OS" persistente, jerarquico y humano.

La idea central es simple:

- una persona puede escribir rapido
- el sistema entiende y clasifica
- solo despues decide si eso es nota, tarea, rutina, skill, servidor MCP o conocimiento

## Principios

1. capturar primero, ordenar despues
2. no perder contexto humano
3. permitir etiquetado manual, automatico o hibrido
4. ejecutar solo lo que es claramente accionable
5. promover a markdown lo que merece persistir
6. permitir que skills y MCP se carguen dinamicamente como capas del prompt

## Capas De Contexto

Todo prompt ejecutado debe construirse desde capas.

### Capa 0. Identidad

- quien es el usuario
- objetivos vitales
- tono
- restricciones
- presupuesto

### Capa 1. Dominio

- rutina diaria
- trabajo
- corto plazo
- proyectos
- personal

### Capa 2. Contexto Temporal

- hora actual
- calendario
- eventos proximos
- energia del sistema

### Capa 3. Contexto Operativo

- skills activas
- servidores MCP activos
- herramientas disponibles
- proveedores permitidos

### Capa 4. Contexto Vivo

- nota rapida actual
- prompts relacionados
- correlacion con items previos
- archivos markdown relevantes

## Tipos De Artefactos

### Quick Note

Captura inmediata. Todavia no se ejecuta por defecto.

Uso:

- ideas
- ordenes cortas
- recordatorios
- pensamiento en bruto

### Prompt Candidate

Nota ya clasificada y lista para decidir si se ejecuta.

### Executable Prompt

Prompt con categoria, prioridad, workflow, politica de proveedor y contexto minimo resuelto.

### Prompt List

Archivo markdown persistente con items reutilizables y contexto comun.

Ejemplos:

- `rutina-diaria`
- `laboral`
- `plan-corto-plazo`
- `proyectos`

### Routine Pack

Lista con horario o recurrencia clara.

### Skill Adapter

Plantilla o modulo que reescribe o enriquece el prompt.

### MCP Adapter

Conjunto de herramientas que el prompt puede invocar.

## Maquina De Estados

Estados propuestos para el nuevo sistema:

```text
captured
-> classified
-> staged
-> queued
-> processing
-> reviewed
-> completed
-> archived
```

Estados alternativos:

```text
captured
-> needs-human-tagging
-> staged
```

```text
captured
-> promoted-to-list
```

```text
captured
-> promoted-to-skill
```

```text
captured
-> promoted-to-mcp
```

## Flujo Principal

### Paso 1. Captura

La persona escribe en la UI inferior:

- una linea
- varias lineas
- hashtags opcionales
- una fecha opcional
- una orden opcional como "ejecuta ya"

Se guarda en DB con:

- `source=note`
- `status=captured`
- `raw_text`
- `manual_tags`
- `capture_channel`

### Paso 2. Clasificacion

El clasificador decide:

- categoria
- tags sugeridas
- prioridad
- si requiere agenda
- si conviene ejecucion inmediata
- si conviene archivado en un markdown

Modo de etiquetado:

- `manual`
- `auto`
- `hybrid`

### Paso 3. Staging

La nota ya clasificada aparece en una bandeja de staging.

Desde ahi se puede:

- ejecutar
- convertir en item de lista
- convertir en rutina
- guardar como nota de conocimiento
- proponer skill
- proponer MCP

### Paso 4. Ejecucion

Si el item es ejecutable:

- entra en cola
- el priorizador corre cada 5s
- el router elige workflow
- Frangels elige proveedor
- skills y MCP enriquecen el contexto

### Paso 5. Revision

Para categorias sensibles:

- `work`
- `plan`
- `project`
- `identity`

el output debe pasar por reviewer y critic.

### Paso 6. Promocion

Si el output es reusable:

- se escribe en markdown
- se agrega a una prompt list
- se convierte en skill
- se usa como base de servidor MCP

## Especificacion De Prompt Lists Markdown

Cada archivo markdown de lista debe tener frontmatter.

```yaml
---
name: Rutina Diaria
slug: rutina-diaria
kind: routine
category: routine
description: Automatizaciones y prompts diarios
is_active: true
autotag_mode: hybrid
default_workflow: reviewed_execute
provider_policy: free-first
schedule:
  timezone: Europe/Madrid
  windows:
    - "06:00"
    - "12:00"
    - "18:00"
skills:
  - daily-planner
mcp_servers:
  - calendar-assistant
---
```

## Estructura De Carpetas Recomendada

```text
data/
  prompt-inbox/
    2026/
      03/
        2026-03-13.md
  prompt-lists/
    rutina-diaria.md
    laboral.md
    plan-corto-plazo.md
    proyectos.md
  prompt-archives/
    2026/
  skills/
  mcp-servers/
```

## Sincronizacion DB y Markdown

La DB es la fuente operativa.

Markdown es la fuente humana y reusable.

Regla:

- `captured`, `queued`, `processing` y `reviewed` viven primero en DB
- `completed` y `promoted` pueden reflejarse en markdown
- las listas markdown se cargan al iniciar y se resync cada cierto intervalo

## Politicas De Etiquetado

### Manual

El usuario decide categoria y tags antes de ejecutar.

### Auto

El sistema:

- detecta hashtags
- infiere categoria
- sugiere destino markdown
- propone workflow

### Hybrid

El sistema clasifica, pero el usuario puede corregir antes de promocionar.

## Enriquecimiento Con SKILLS Y MCP

Un prompt no debe cargar todo. Solo lo necesario.

Regla de ensamblado:

1. identificar categoria
2. buscar lista activa relevante
3. buscar skill matching
4. buscar MCP requerido
5. construir prompt final

Ejemplo:

```text
Quick note: "prepara el plan del lunes y revisa reuniones"

Capas aplicadas:
- rutina diaria
- laboral
- calendario de hoy
- skill de priorizacion laboral
- MCP de calendar
```

## Workflows Recomendados

### quick_execute

Para notas simples, respuestas rapidas y baja criticidad.

### reviewed_execute

Para trabajo, planificacion y decisiones de prioridad.

### full_pipeline

Para prompts sensibles, complejos o que modifican artefactos importantes.

### propose_skill

Workflow especial:

- detectar patron repetido
- resumirlo
- producir template
- guardarlo como skill candidata

### propose_mcp

Workflow especial:

- detectar necesidad de herramienta
- extraer operaciones
- generar spec inicial
- mandar a fabrica MCP

## Agentes Del Prompt OS

### 1. Ingest Agent

Normaliza la captura.

### 2. Taxonomy Agent

Clasifica y etiqueta.

### 3. Prioritizer Agent

Escanea cada 5s y ordena.

### 4. Planner Agent

Define estrategia o subtareas.

### 5. Executor Agent

Resuelve el prompt.

### 6. Reviewer Agent

Valida calidad.

### 7. Critic Agent

Busca inconsistencias o alucinaciones.

### 8. Archivist Agent

Mueve conocimiento a markdown y listas.

### 9. Builder Agent

Propone skills o MCP cuando detecta patrones repetidos.

## Reglas De Promocion

### Nota -> Lista

Promover cuando:

- se repite
- tiene valor recurrente
- pertenece a una rutina o proyecto

### Nota -> Skill

Promover cuando:

- reescribe prompts de forma consistente
- tiene gatillos claros
- reduce carga cognitiva

### Nota -> MCP

Promover cuando:

- necesita operaciones externas
- seria mejor como herramienta que como texto

## UI Recomendada

La pagina `/prompts` debe evolucionar a cinco paneles claros:

1. `Inbox`
2. `Staging`
3. `Active Queue`
4. `Results`
5. `Lists and Routines`

Acciones rapidas por item:

- ejecutar ahora
- etiquetar
- agendar
- mover a lista
- archivar
- convertir en skill
- convertir en MCP

## Primera Implementacion Recomendada

Orden de construccion:

1. añadir estados `captured`, `classified`, `staged`, `archived`
2. crear endpoints de promocion y archivado
3. separar quick notes de prompts ejecutables
4. crear sync `prompt-inbox/*.md`
5. añadir vista `Staging`
6. conectar `skills` y `mcp` al ensamblado final del prompt

## Resultado Esperado

El usuario deja de "mandar prompts aislados" y pasa a vivir dentro de un sistema:

- piensa en voz alta
- el sistema recoge
- el sistema organiza
- el sistema ejecuta
- el sistema aprende
- el sistema propone nuevas habilidades y herramientas

---

## Estado De Implementacion (Actualizado 2026-03-13)

### Implementado

- Quick Note con #hashtags: `POST /api/v1/prompts/notes` con auto-detect y auto-category
- Prompt Lists MD con frontmatter: 4 archivos seed (rutina-diaria, laboral, plan-corto-plazo, proyectos) + CRUD API
- Maquina de estados: `pending -> queued -> processing -> completed/failed -> reviewed`
- Priorizador cada 5s: `PromptPrioritizationAgent` como background asyncio task
- Workflows: `quick_execute`, `reviewed_execute`, `full_pipeline` en `WorkflowEngine`
- Agentes: Planner, Executor, Reviewer, Critic, Patcher definidos en `agent_definitions.py`
- Frangels multi-proveedor: free tier (18 providers) + paid (OpenAI, Anthropic) con `prefer_paid`
- Skills dinamicas: `SkillsManager` con CRUD, toggle, test y trigger por regex
- Servidores MCP: `MCPGenerator` genera Python y TypeScript desde descripcion
- Google Calendar: OAuth2, sync bidireccional, scheduler cada 60s
- UI chat-like: `QuickNoteInput` sticky bottom, Enter para enviar, Shift+Enter nueva linea
- Categorias: routine, work, plan, project, personal, health, learning
- Pipeline visual: Monitor page con flujo Ingestion -> Queue -> Router -> Executor -> Store
- 17 endpoints API de prompts + 7 endpoints de skills + 8 endpoints MCP + 8 endpoints calendar

### Pendiente

- Estados intermedios: `captured`, `classified`, `staged`, `archived` (el doc los define pero el codigo usa simplificados)
- Staging bandeja visual: no existe panel de staging separado en la UI
- Taxonomy Agent dedicado: la clasificacion la hace el priorizador de forma parcial
- Ingest Agent: no existe como agente separado
- Archivist Agent: no existe (mover resultados valiosos a MD)
- Builder Agent: no existe (detectar patrones y proponer skills/MCP)
- Capas de contexto 0-4: el executor no ensambla prompt desde capas jerarquicas
- Sync DB a Markdown: los archivos MD se crearon manual, no hay sync automatico bidireccional
- Prompt Inbox diario: `data/prompt-inbox/YYYY/MM/fecha.md` no existe
- Politicas de etiquetado configurables: solo hay auto-tag por hashtags
- Endpoints de promocion: nota a lista, nota a skill, nota a MCP
- UI 5 paneles: solo hay queue + filters, no inbox/staging/results separados
- Workflows `propose_skill` y `propose_mcp`

