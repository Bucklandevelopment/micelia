# Revisión Independiente — Micelia v0.1

**Auditor**: independent-review-agent (T5.2)
**Modo**: READ-ONLY
**Fecha**: 2026-05-24

---

## Veredicto

**Listo para release v0.1 con reservas menores** — apto para pitch a Marc Vidal y publicación pública, pero quedan 3 hallazgos (1 crítico + 2 mayores) que recomiendo cerrar antes de un pitch que vaya a someter el repo a escrutinio externo.

## Resumen

El rebrand está sólidamente ejecutado en código (grep limpio en `app/`, `sdk/`, `tests/`, `frontend/src/`, `configs/`) y los aliases retrocompat funcionan. La estrategia de licencia de 5 capas es coherente, narrativamente alineada con el Nodo 1, y honestamente argumentada (incluyendo las opciones rechazadas). La suite E2E es de calidad inusualmente alta: contratos Pydantic con `extra="forbid"`, 4 modos de mock (healthy/degraded/down/slow), datos sintéticos deterministas. El Makefile es day-1 onboarding-ready. Sin embargo: hay **una contradicción explícita** entre el doc canónico (`Micelia_Nodo1_Impacto_Socioeconomico.md` Anexo A línea 209) y la decisión T1.4 implementada; **inconsistencia en el rename del SDK** (sigue como `idm-sdk` en el pyproject); **el alias `IdmClient = MiceliaClient` no emite DeprecationWarning al instanciarse**; y **fragilidad en el test de normalización legacy** (depende de capturar una excepción de BD).

## Calificaciones por área

| Área | Calificación |
|---|---|
| 1. Rebrand vital-core → Micelia | 4/5 |
| 2. Decisión T1.4 (source-id en eventos) | 3/5 |
| 3. Suite E2E | 4.5/5 |
| 4. Estrategia de licencia | 4.5/5 |
| 5. Coherencia documental | 3.5/5 |
| 6. Makefile y operación dev | 4.5/5 |
| 7. CLA y gobernanza cooperativa | 3.5/5 |

## Hallazgos críticos (bloquean release público)

1. **Contradicción doc Nodo 1 vs decisión T1.4 sobre source-id**.
   - `Micelia_Nodo1_Impacto_Socioeconomico.md` Anexo A línea 209: *"el identificador interno `"biohack"` se convierte en `"micelia"` con alias de compatibilidad deprecated"*.
   - `docs/REBRAND_MICELIA.md` §C línea 164: *"Estos son los 5 dominios del ecosistema. NUNCA renombrar a `micelia`"*.
   - `docs/PLAN_MICELIA_v0.md` §1.6: *"Los 5 source-id de dominio (biohack, canela, ideacursi, cybertools, auto-mat-ion) NO se tocan"*.
   - El código sigue la segunda decisión. El doc canónico está obsoleto.
   - **Acción**: actualizar `Micelia_Nodo1_Impacto_Socioeconomico.md` Anexo A líneas 208-209 antes de cualquier envío externo.

## Hallazgos mayores (recomendable arreglar antes de pitch público)

1. **SDK package name no renombrado**: `sdk/python/pyproject.toml:6` aún dice `name = "idm-sdk"`. Documentar como decisión diferida en REBRAND_MICELIA.md §D, o renombrar a `micelia-sdk` con alias retrocompat.

2. **Alias `IdmClient` no emite DeprecationWarning al instanciar**: el alias es transparente; el verification report afirma "deprecated" pero el runtime no lo refleja. O implementar warning real, o corregir el verification report.

3. **Tests de normalización legacy frágiles**: `except Exception: pass` enmascara el orden de operaciones. Mockear sesión y validar que el campo `source` final es `"micelia"`.

4. **`api/v1/events.py` acepta cualquier source string**: documentar en OpenAPI que sólo 6 sources son canónicos, aunque no se enforce; o añadir Literal y normalizar fuera de la lista.

5. **AI_SOVEREIGNTY_POLICY enforcement no implementado**: ni `--no-proprietary` ni `make sovereignty-audit` existen. Documentar como "policy publicada, enforcement v0.2" en lugar de presentar como vinculante hoy.

6. **CLA cláusula B puede ser inenforceable en España sin review legal**: añadir nota "pendiente review por abogado de propiedad intelectual cooperativa" antes del pitch público o conseguir review real (€500-1500).

7. **CLA contradicción interna**: `irrevocable` (§2) vs `deemed transferred` (§5). Resolver con redacción que aclare que la reversión es una sublicencia transferida, no la grant original.

8. **No hay PR template implementando el checkbox del CLA §8**: añadir `.github/PULL_REQUEST_TEMPLATE.md` o ajustar §8.

9. **Copyright holder hoy no documentado**: si la Asociación está "in formation", ¿quién es el holder legal durante esa formación? Necesita un párrafo en NOTICE o LICENSING_STRATEGY.md.

## Hallazgos menores / nice-to-have

1. `app/events/store.py:25` clase `IdmEventModel` y docstring "Panel IDM" — cosmético.
2. `tests/test_idm_sdk.py` filename — renombrar a `test_micelia_sdk.py`.
3. `make rebrand-verify` pasa por coincidencia (no incluye `*.md` y `Micelia_Nodo1_Impacto_Socioeconomico.md` no tiene `*.py`). Documentar el alcance del check explícitamente.
4. Banner Makefile menciona container names `idm-*` — añadir nota inline sobre D.4.
5. `make docker-logs` con fallback `micelia-core` → `idm-core` — limpiar cuando D.4 se ejecute.
6. `PROPUESTA_MARC_VIDAL.md` afirma "Suite E2E ~3.4k LOC" — el conteo real es 3066. Ajustar.
7. Tests E2E inicializan `READONLY_API_KEY` a nivel de módulo — posible flakiness con xdist.
8. `LICENSE.fsl` line 9: fecha de "comienzo de cómputo" para la ventana FSL de 2 años no está clara.
9. Dominio `micelia.org` no documentado como adquirido.
10. T0.1 (inspección biohack-app) sigue pending: el contrato es 100% INFERRED. Honestamente documentado, pero significa que la suite valida la hipótesis del equipo, no el contrato real.

## Coherencia documental — contradicciones detectadas

1. **CRÍTICO**: doc Nodo 1 Anexo A línea 209 ⇄ REBRAND_MICELIA §C línea 164 ⇄ PLAN §1.6 (source-id).
2. **MAYOR**: REBRAND_VERIFICATION_REPORT línea 65 afirma "IdmClient... deprecated", pero el alias real no emite warning.
3. **MAYOR**: REBRAND_MICELIA §B.3 no menciona que `name = "idm-sdk"` del SDK pyproject NO se renombra. Estado mixto sin documentar.
4. **MENOR**: PROPUESTA_MARC_VIDAL "Suite E2E ~3.4k LOC" vs real 3066.
5. **MENOR**: ningún documento explicita quién es copyright holder durante "in formation".
6. **MENOR**: ningún documento aclara fecha de comienzo de la ventana FSL de 2 años.

## Recomendaciones para release v0.1 (priorizadas)

1. **Actualizar `Micelia_Nodo1_Impacto_Socioeconomico.md` Anexo A** (líneas 208-209) para reflejar T1.4 corregida.
2. **Decisión explícita sobre el SDK**: o renombrar `idm-sdk → micelia-sdk` con compat shim, o documentar como D.x diferido.
3. **Corregir el alias `IdmClient`** para que emita DeprecationWarning al instanciar (3-5 líneas en `sdk/python/idm_sdk/__init__.py`).
4. **Endurecer los tests de normalización legacy** para validar el campo `source` final (no sólo el warning).
5. **Documentar el copyright holder actual** (probablemente Jessicache personalmente) y compromiso público de transferencia a la Asociación. Añadir a NOTICE.
6. **Marcar AI_SOVEREIGNTY_POLICY como "v1.0 — enforcement v0.2"** o implementar al menos `make sovereignty-audit`.
7. **Marcar CLA como "v1.0 — pendiente review legal cooperativa"** y resolver inconsistencia §2 vs §5.
8. **Crear `.github/PULL_REQUEST_TEMPLATE.md`** con el checkbox del CLA.
9. **Documentar en OpenAPI** que los 6 sources son los canónicos.
10. **Conseguir review legal del CLA** antes del pitch a MV (€500-1500).

## Recomendaciones para v0.2

1. T0.1: inspeccionar biohack-app real y reconciliar campos INFERRED.
2. D.1: renombrar el directorio del repo `vital-core/` → `micelia/` (ya hecho informalmente, falta limpiar referencias).
3. D.2: migración Alembic `idm_core` → `micelia`.
4. D.3: alias `MICELIA_URL` env vars.
5. D.4: container names docker.
6. D.5: tokens Tailwind `idm-*`.
7. D.7: directorio `panel-idm/`.
8. T4.1-T4.3: QA frontend asistido.
9. Eliminar aliases retrocompat tras un release de gracia.
10. Migrar Asociación → Cooperativa formal con 3+ contribuidores activos.
11. Implementación real de `--no-proprietary` y `make sovereignty-audit`.
12. Spec MFP (Micelia Federation Protocol) v0.1.

## Lo que destaca positivamente

1. **Cohesión narrativa excepcional**: doc Nodo 1 + LICENSING_STRATEGY + PROPUESTA_MARC_VIDAL + ETHICAL_USE + AI_SOVEREIGNTY forman un argumento coherente. La frase canónica ("no te paga por existir, te cubre por contribuir") sintetiza la tesis en 8 palabras.
2. **Suite E2E de calidad inusual para v0.1**: contratos strict, mocks parametrizables, datos sintéticos deterministas, fixtures con restauración limpia, `pytest.skip` honesto. Mejor que muchas suites en producción.
3. **Estrategia de licencia honestamente argumentada**: no caer en SSPL es la decisión técnicamente sólida. La sección de rechazos justificados es ejemplar.
4. **`DEPENDENCIES_AUDIT.md` ejecutado antes del release**: pocos proyectos lo hacen.
5. **Makefile day-1 onboarding**: `make setup` + `make dev` con banner + `make help` agrupado es UX consciente. `_check-venv` muestra cuidado por el dev experience.
6. **Rebrand textual ejecutado limpiamente**: grep en código limpio salvo legítimos.
7. **Honestidad documental**: las decisiones diferidas (D.1-D.7), "INFERRED" en contratos, "in formation" en NOTICE — todo está marcado. No hay vaporware.
8. **Política Ethical Use separada del LICENSE**: la decisión correcta. Madurez legal.

---

## Archivos críticos a modificar para cerrar los hallazgos

- `Micelia_Nodo1_Impacto_Socioeconomico.md` (líneas 208-216: corregir Anexo A para reflejar T1.4)
- `sdk/python/idm_sdk/__init__.py` (líneas 7-16: implementar DeprecationWarning real)
- `sdk/python/pyproject.toml` (línea 6: decisión sobre rename o documentar como D.x)
- `docs/CLA.md` (§2 vs §5 + cláusula fallback "in formation" + revisión legal)
- `docs/AI_SOVEREIGNTY_POLICY.md` (§2.2, §5.3: cambiar tono a "policy publicada, enforcement v0.2" o implementar)
- `tests/e2e/test_source_id.py` (líneas 145-167: endurecer test de normalización legacy)
- `NOTICE` (añadir párrafo sobre copyright holder durante "in formation")
- `.github/PULL_REQUEST_TEMPLATE.md` (nuevo — implementar checkbox CLA §8)
