# MicelIA — Puesta en marcha local + rutina móvil (2026-06-09)

## Resumen

El gateway Micelia corre en local en tu Mac (`http://127.0.0.1:8888`, PID en `logs/micelia-gateway.pid`) y tu Google Calendar (`bucklandevelopment@gmail.com`) tiene la rutina diaria completa como 10 series recurrentes con notificación push en el minuto 0. Tu móvil queda guiado por la rutina de sueño, alimentación y aprendizaje a partir de esta misma noche (primer evento: Dormir, hoy 22:30).

## Análisis del ecosistema

Micelia es el orquestador FastAPI del ecosistema UTOP.IA: 18 routers (gateway, events, ai, energy, routine, calendar, system/osascript, dashboard…), event sourcing en PostgreSQL, bus Redis, compute router Ollama/CodKing/Claude y frontend Next.js en :3001. El sistema de rutinas vive en `data/prompt-lists/rutina-diaria.md` y se publica vía `GET /api/v1/routine/today` y `POST /api/v1/routine/sync` (Google Calendar) o vía osascript a Calendar.app (`/api/v1/system/calendar/*`).

Servicios conectados, veredicto de arrancabilidad hoy: biohack-app (salud, :8080) arrancable, expone nutrición/HealthKit/biomarcadores que la rutina referencia; cybertools (:8000) y codking arrancables; auto-mat-ion arrancable; canela-molida y ideacursi-tool existen solo como `.zip` en `projects/` y requieren descompresión antes de integrarse al perfil `full`.

## Cambios realizados en el repo

1. `app/api/v1/routine.py` — corregido bug de timezone: `Europe/Madrid` no estaba en `_TZ_OFFSETS` y caía silenciosamente a `-06:00` (CDMX), desplazando toda la rutina 8 horas. Nueva función `_tz_offset_for()` calcula el offset con `zoneinfo`, DST-aware (verificado: `+02:00` en junio, `+01:00` en diciembre).
2. `app/main.py` — degradación elegante real: `EventStore` y `PromptStore` (PostgreSQL) crasheaban el arranque con `ConnectionRefused` si no había DB. Ahora capturan la excepción, loguean warning y el gateway arranca sin event sourcing/prompts. Cuando levantes Postgres, vuelven a activarse solos al reiniciar.
3. `data/prompt-lists/rutina-diaria.md` — añadidos los 3 bloques de sueño que faltaban (Despertar 06:15, Wind-down 22:00, Dormir 22:30 → ~7h45 de oportunidad de sueño) y completada la descripción truncada de "Lectura: papers". Total: 10 actividades.
4. `scripts/run-local.sh` — nuevo: `start|stop|status|logs` sin Docker, usando el `.venv` (Python 3.13.12) incluido en el repo.

## Operación del gateway

Arrancar/parar/estado: `bash scripts/run-local.sh start|stop|status` desde la raíz del repo. Log en `logs/micelia-gateway.log`. Docs interactivas en `http://127.0.0.1:8888/docs`. Los endpoints protegidos usan header `X-API-Key` (valor en `SYSTEM_API_KEY` de tu `.env`). Postgres/Redis/Ollama son opcionales; con `make docker-infra` (o podman, ver `migrate-to-podman.sh`) recuperas event store, prompts y IA local.

## Rutina en el móvil

Diez eventos recurrentes diarios (RRULE:FREQ=DAILY), zona Europe/Madrid, recordatorio popup al inicio de cada bloque, codificados por color: azul=sueño, naranja=cuerpo, verde=alimentación, morado=aprendizaje.

| Hora | Bloque | Pilar |
|---|---|---|
| 06:15 | Despertar (luz + hidratación + HRV) | Sueño |
| 06:30 | Ducha de contraste | Cuerpo |
| 07:00 | Ejercicio (varía por día de semana) | Cuerpo |
| 07:45 | Desayuno | Alimentación |
| 13:30 | Comida 50-25-25 + caminata digestiva | Alimentación |
| 17:00 | Aprendizaje: longevidad (deep work) | Aprendizaje |
| 19:00 | Lectura: papers de longevidad | Aprendizaje |
| 20:30 | Cena ligera | Alimentación |
| 22:00 | Wind-down | Sueño |
| 22:30 | Dormir (luces fuera 22:45) | Sueño |

Cada evento lleva en su descripción el protocolo completo (el "qué" y el "cómo"), de modo que la notificación convierte el móvil en terminal de la rutina sin abrir nada más.

## Próximos pasos sugeridos

1. Para que micelia sincronice por sí solo días puntuales (`POST /api/v1/routine/sync`), configura su OAuth propio: credenciales en Google Cloud Console → `GET /api/v1/calendar/auth` → token en `data/google_token.json`. Ojo: la serie recurrente ya cubre todos los días; usa el sync de micelia solo para días excepcionales o tras editar el `.md`, o generarás duplicados.
2. `make docker-infra` para Postgres+Redis+Ollama → event sourcing y AI local completos.
3. Arrancar biohack-app (:8080) para cerrar el bucle: HRV/sueño medidos alimentando la revisión semanal del bloque de Aprendizaje.
4. Descomprimir `canela-molida.zip` e `ideacursi-tool.zip` cuando quieras el pipeline research-to-course.
