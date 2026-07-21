# DP Ledger — registro autoritativo de Decisiones Pendientes

> **Fuente de verdad** del estado de cada DP (Decisión Pendiente) del `ITERATION_LOG.md`.
> Creado en C116 (consolidación) porque el estado estaba **derivando**: cada ciclo re-listaba
> las DP en su sección "DECISIÓN PENDIENTE" y algunas cerradas/decididas seguían apareciendo
> como pendientes (drift, patrón C81-84). A partir de aquí: **este fichero manda**; los ciclos
> lo ACTUALIZAN en vez de re-derivar la lista de memoria.
>
> Verificado contra el código en C116 (`make verify` verde, 1717 passed — los contratos
> pineados de las cerradas se sostienen).

## Leyenda de estado

- **CERRADA** — resuelta (fix + guard), sin acción del dueño pendiente.
- **DECIDIDA** — el dueño YA decidió; nada pendiente salvo una condición de reapertura explícita
  o un paso de ejecución (humano/infra), no una decisión.
- **ABIERTA** — requiere una decisión del dueño (o de un repo hermano) aún no tomada.

## Registro

| DP | Tema | Estado | Nota (verificado C116) |
|----|------|--------|------------------------|
| DP-1 | Estrategia de hosting del funnel | **DECIDIDA** (runbook 2026-07-17) | Hosting propio local (M1). Ejecución = pasos ⏳HUMANO (no decisión). |
| DP-2 | Subdominios del funnel | **DECIDIDA** | `micelia.idmmortality.com` host único; `register.`/`login.` = landings viejas. |
| DP-3 | Secretos del funnel | **DECIDIDA** | `deploy/.env` (chmod 600, fuera de git). |
| DP-4 | Postgres de producción | **DECIDIDA** | La del compose local (`idm-postgres`). |
| DP-5 | Rebrand env-var URL orquestador | **ABIERTA** (parte decisión) / CERRADA (bug, C82) | El compose inyecta **ambos** `VITAL_*`+`IDM_*` (alias, verificado C116). Decisión abierta: dejar-ambos (hoy) / retirar `IDM_*` / migrar a `MICELIA_URL`. Hermano gemelo de DP-7. |
| DP-6 | Propagación de identidad al dominio (pipeline) | **CERRADA** (C119) | El SSO (Micelia IdP + auto-provisión por email) resuelve el hueco: biohack materializa al usuario del funnel por su email. **ideacursi queda FUERA de SSO** por decisión del dueño (mantiene su OAuth propio) → no hay identidad de Micelia que propagarle. Ver `SSO_IDENTITY_C119.md`. |
| DP-7 | Namespace de canales Redis (`idm.*`/`vital.*`/`micelia.*`) | **DECIDIDA** (C80: documentar, NO migrar) | ⚠️ **corrección de drift C116**: ciclos recientes (incl. C108/C114/C115) la re-listaban como "pendiente"; NO lo es. El dueño decidió no migrar. Guardada (C108, `test_automation_ingest_path`). **Reabre SOLO** si se quiere cablear consumo pub/sub cruzado → migrar los 6 repos coordinadamente a `micelia.*`. |
| DP-8 | `/health` de canela sin `version` | **CERRADA** (C79) | Micelia maneja `version:null`; pineado cross-repo. Acción futura opcional (canela añade version) — no bloquea. |
| DP-9 | Campo `total` global del panel | **CERRADA** (descartada, C71) | Era fabricación; descartada. No re-listar. |
| DP-10 | Blindaje request+response del panel | **CERRADA** (C78) | Guards de contrato del panel. |
| DP-11 | Coherencia de puertos cross-repo (Dockerfiles) | **CERRADA** (C77) | La suite lee los Dockerfiles hermanos: puerto ruteado por el gateway == puerto que el dominio EXPONE. |
| DP-12 | Mapa de puertos triplicado del ecosistema | **CERRADA** (C76) | `scripts/ecosystem-ports.json` fuente única + pins. |
| DP-13 | Sonda load-bearing del gateway en compose | **CERRADA** (C75) | Pineada (`test_deploy_contract`). |
| DP-14 | Dominios fantasma vs invisibles en el registry | **CERRADA** (C84) | Auditada: `testlab`=auto-mat-ion (contrato vivo); solo `devtools`/ollama-code era fantasma → desactivado. |
| DP-15 | Hint del registry sugería `docker-full` | **CERRADA** (C85) | El hint deduce la topología (nativo → `run-ecosystem.sh start`). |
| DP-16 | Venvs huérfanos por bumps de brew | **CERRADA** (C97) | El `doctor` de `run-ecosystem.sh` los caza temprano. |
| DP-17 | biohack no compila en python 3.14 | **CERRADA** (C117) | Resuelta con **python 3.11** (no 3.13: su `setup.py` lo fija y avisa contra 3.13; deps pinneadas solo tienen wheel cp311/cp312). `run-ecosystem.sh setup` usa python3.11 para biohack; venv creado, deps instaladas, boot **verificado live** (`/api/v1/service-health` healthy). **Nota:** biohack exige **postgres al arrancar** (DATABASE_URL required, sin degradación) — infra, no deps; se le da con `docker-infra`. |
| DP-18 | auto-mat-ion sin `node_modules` | **CERRADA** (C102) | `run-ecosystem.sh setup` → `npm install`. |
| DP-19 | ideacursi `node_modules` incompleto | **CERRADA** (C102) | `setup` completó el árbol (`reflect-metadata`). |
| DP-20 | ideacursi exige redis-stack en :6380 | **CERRADA** (C104) | El compose expone `:6380` (RediSearch para el vector). |
| DP-21 | Colisión dev/prod de `container_name` | **CERRADA** (C106) | Infra dev de micelia renombrada a `micelia-*`. |
| C84-minor | Eliminar el slot `devtools`/`ollama_code_*` | **CERRADA** (C118) | El dueño confirmó que `ollama-code` no es proyecto planificado. Borrado de config (`ollama_code_url`/`_enabled`), `settings.services` y el registry → **5 slots** (health/research/education/security/testlab). Pin de eliminación en `test_registry_domains`. |

## Lo genuinamente PENDIENTE del dueño (resumen)

- **Decisiones del dueño:** DP-5 (rebrand env-vars). *(DP-6 cerrada C119 — SSO Micelia→biohack; ideacursi fuera de SSO por decisión, mantiene su OAuth. DP-17 cerrada C117 — biohack en python 3.11; C84-minor cerrada C118 — slot devtools borrado.)*
- **Pasos humanos de ejecución (no decisión):** DP-1..DP-4 → panel IONOS (A-record + API key DDNS), port-forward TP-Link 80/443, `pmset`. Verificables con `scripts/funnel-preflight.sh` (C115).
- **Decidida, no re-listar como pendiente:** DP-7 (documentar, no migrar).

Todo lo demás: **CERRADA**.
