# Contrato Micelia ↔ biohack-app (T2.1)

> Documento de contrato observado desde `vital-core` (ahora Micelia). biohack-app
> NO está montado en esta sesión; las shapes documentadas son las que el código
> de Micelia **produce o consume** sobre la red. T0.1 re-validará contra el
> repo real biohack-app y publicará diffs.

## Resumen

| # | Dirección | Método | Path | Modelo Pydantic | Status |
|---|-----------|--------|------|-----------------|--------|
| 1 | Micelia → biohack | GET    | `/api/v1/health`              | `HealthStatus`           | observado |
| 2 | Micelia → biohack | GET    | `/api/v1/health/live`         | `HealthStatus`           | observado |
| 3 | Micelia → biohack | GET    | `/api/v1/health/ready`        | `HealthReady`            | observado |
| 4 | Micelia → biohack | GET    | `/api/v1/health/detailed`     | `HealthDetailed`         | INFERRED (forma derivada de cómo Micelia la consume en `app/cli.py`) |
| 5 | Micelia → biohack | GET    | `/api/v1/health/services`     | `HealthServicesResponse` | INFERRED (idem) |
| 6 | Micelia → biohack | POST   | `/api/v1/bio-savant/chat`     | `BioSavantChatRequest` / `BioSavantChatResponse` | observado parcialmente (request schema viene de `app/api/v1/ai.py:255`) |
| 7 | Micelia → biohack | POST   | `/api/v1/ml-production/predict` | `MLPredictionRequest` / `MLPredictionResponse` | observado parcialmente (`app/api/v1/ai.py:265`) |
| 8 | Micelia → biohack | GET    | `/api/v1/biomarkers/series`   | `BiomarkerSeries`        | INFERRED (no llamado por Micelia hoy; T2.3 lo necesita para sintéticos) |
| 9 | biohack → Micelia | POST   | `/api/v1/events`              | `EventCreate` / `EventCreated` | observado (`app/api/v1/events.py`, `app/sdk/client.py`) |
| 10 | biohack → Micelia | GET   | `/api/v1/auth/me`             | `ApiKeyValidation`       | observado (header `X-API-Key`; no `Bearer`) |
| 11 | biohack → Micelia | GET   | `/api/v1/health/services`     | `ServiceRegistryResponse` | observado (no hay `/system/registry/{service}` per-service; el registry vive bajo `health/services`) |

> **Divergencias respecto al brief de T2.1**: documentadas en "Decisiones de diseño" al pie. En todos los casos se prioriza la shape del código sobre la del brief para evitar drift entre mock y servidor real.

---

## Dirección Micelia → biohack-app (biohack-app actúa como servidor)

### 1. `GET /api/v1/health`

- **Descripción**: Health check público para load balancers.
- **Auth**: ninguna.
- **Request**: sin body.
- **Response 200** (`HealthStatus`):
  ```json
  {
    "status": "ok",
    "timestamp": "2026-05-21T10:00:00+00:00",
    "service": "biohack-app",
    "version": "0.1.0"
  }
  ```
  Campos `service` y `version` están marcados INFERRED (Micelia espera estos campos en su propio `/api/v1/health` y se asume simetría; pendiente T0.1).
- **Errores típicos**: 503 cuando biohack-app está cayendo (mock debe poder forzarlo).

### 2. `GET /api/v1/health/live`

- **Descripción**: Liveness probe (proceso vivo).
- **Auth**: ninguna.
- **Response 200** (`HealthStatus` con `status: "alive"`):
  ```json
  {"status": "alive", "timestamp": "2026-05-21T10:00:00+00:00"}
  ```
- **Errores**: 500/503 cuando el proceso no puede contestar.

### 3. `GET /api/v1/health/ready`

- **Descripción**: Readiness probe (dependencias listas).
- **Auth**: ninguna.
- **Response 200** (`HealthReady`):
  ```json
  {"status": "ready", "timestamp": "2026-05-21T10:00:00+00:00"}
  ```
  o, si no está listo:
  ```json
  {"status": "not_ready", "reason": "ml-models loading"}
  ```
- **Errores**: 503 si el agente upstream lo prefiere a la respuesta "not_ready".

### 4. `GET /api/v1/health/detailed`

- **Descripción**: Estado detallado de servicios y recursos. Usado por `app/cli.py:63` que indexa `data["status"]`, `data["uptime_seconds"]`, `data["services"]` (dict `name → {healthy, latency_ms, url}`) y `data["resources"]` (cpu_percent, memory, disk).
- **Auth**: ninguna (mismo patrón que Micelia).
- **Response 200** (`HealthDetailed`):
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-05-21T10:00:00+00:00",
    "uptime_seconds": 1234.5,
    "services": {
      "database": {"name": "postgres", "url": "postgres://...", "enabled": true, "healthy": true, "latency_ms": 1.2, "error": null},
      "ml_models": {"name": "onnx", "url": "local://models", "enabled": true, "healthy": true, "latency_ms": null, "error": null}
    },
    "resources": {
      "cpu_percent": 12.3,
      "memory": {"total_gb": 16.0, "available_gb": 9.4, "percent": 41.0},
      "disk":   {"total_gb": 500.0, "free_gb": 200.5, "percent": 60.0}
    }
  }
  ```
- **Errores**: 500 si la propia agregación falla.
- **Notas**: shape derivada de `app/api/v1/health.py` (`SystemHealth`/`ServiceStatus`) porque biohack-app sigue la convención SDK del propio Micelia. Estable para los mocks; T0.1 verifica.

### 5. `GET /api/v1/health/services`

- **Descripción**: Estado de los microservicios conectados (Micelia consume este endpoint en `app/cli.py:123`).
- **Auth**: ninguna.
- **Response 200** (`HealthServicesResponse`):
  ```json
  {
    "services": {
      "database":  {"name": "postgres", "url": "...", "enabled": true, "healthy": true, "latency_ms": 1.2, "error": null},
      "ml_models": {"name": "onnx",     "url": "...", "enabled": true, "healthy": true, "latency_ms": null, "error": null}
    }
  }
  ```
- **Errores**: 500/503.

### 6. `POST /api/v1/bio-savant/chat`

- **Descripción**: Chat con Bio-Savant (RAG sobre biomarkers + literatura). Llamado desde `app/api/v1/ai.py:255` (`analyze_health` con `question`).
- **Auth**: X-API-Key (forwarded por el gateway).
- **Request** (`BioSavantChatRequest`):
  ```json
  {
    "message": "¿Mi VO2max está bajando este mes?",
    "health_context": {"vo2max_p95": 48.3, "hrv_p95": 78.0},
    "user_id": "u_42",
    "context_window": 10
  }
  ```
  Campos `user_id` y `context_window` están INFERRED — el código actual de Micelia sólo envía `message` y `health_context`. Los marcamos opcionales para que el mock no rompa contra clientes que sí los manden.
- **Response 200** (`BioSavantChatResponse`):
  ```json
  {
    "answer": "Tu VO2max ha caído 3.1 puntos en 14 días...",
    "sources": [
      {"title": "Heart Rate Variability...", "url": "https://pubmed/...", "confidence": 0.87}
    ],
    "reasoning_trace": ["Filtered to last 30 days...", "..."]
  }
  ```
  `reasoning_trace` opcional. Shape INFERRED por T0.1.
- **Errores**: 400 (payload inválido), 401 (API key), 422 (validación), 502 (LLM downstream), 504 (timeout).

### 7. `POST /api/v1/ml-production/predict`

- **Descripción**: Predicción ONNX. Llamado desde `app/api/v1/ai.py:265` cuando `analyze_health` NO trae `question`. Hoy Micelia envía sólo `{"metrics": ...}`, pero T2.3 quiere modelar `model_name` + `features` como el brief lo describe.
- **Auth**: X-API-Key.
- **Request** (`MLPredictionRequest`):
  ```json
  {
    "model_name": "energy_model",
    "features":   {"hrv": 78.0, "sleep_hours": 7.2, "steps": 8400},
    "metrics":    {"hrv_p95": 78.0}
  }
  ```
  `metrics` es alias retrocompat (lo que Micelia envía hoy en `ai.py:265`). `model_name`/`features` INFERRED — T0.1 confirma si biohack-app los acepta o si Micelia debe migrar a `metrics` puro.
- **Response 200** (`MLPredictionResponse`):
  ```json
  {"prediction": 0.71, "confidence": 0.84, "model_version": "energy@1.2.0"}
  ```
- **Errores**: 400, 404 (model_name desconocido), 422, 500.

### 8. `GET /api/v1/biomarkers/series?user_id=...&metric=...&from=...&to=...`

- **Descripción**: INFERRED. Inexistente en código de Micelia hoy, pero los datos sintéticos de T2.3 los necesitan para alimentar el E2E happy path (T3.1). El mock provee este endpoint para que las pruebas E2E recuperen series temporales.
- **Auth**: X-API-Key.
- **Query params**: `user_id` (str, requerido), `metric` (str, requerido, p.ej. `hrv`, `vo2max`, `weight`), `from`/`to` ISO8601 opcionales.
- **Response 200** (`BiomarkerSeries`):
  ```json
  {
    "user_id": "u_42",
    "metric": "hrv",
    "unit": "ms",
    "points": [
      {"timestamp": "2026-05-14T08:00:00+00:00", "value": 78.1},
      {"timestamp": "2026-05-15T08:00:00+00:00", "value": 76.4}
    ]
  }
  ```
- **Errores**: 400 (params inválidos), 404 (usuario/métrica desconocida), 422.

---

## Dirección biohack-app → Micelia (Micelia actúa como servidor)

### 9. `POST /api/v1/events`

- **Descripción**: Persistencia de eventos en el Event Store de Micelia. Definido en `app/api/v1/events.py`; consumido por `app/sdk/client.py` (que es lo que biohack-app importa como `idm_sdk`).
- **Auth**: X-API-Key (requerida por `verify_auth`).
- **Request** (`EventCreate`):
  ```json
  {
    "category":    "health",
    "subcategory": "vitals",
    "source":      "biohack",
    "action":      "create",
    "event_type":  "biomarker.recorded",
    "payload":     {"metric": "hrv", "value": 78.1},
    "metadata":    {"sdk_version": "1.0.0"},
    "tags":        ["healthkit", "auto"]
  }
  ```
  Campos `payload`, `metadata`, `tags`, `subcategory` son opcionales (defaults en código). `source` DEBE pertenecer a `ALLOWED_SOURCES`.
- **Response 200/201** (`EventCreated`):
  ```json
  {
    "event_id":  "0bdb6c0b-3b30-4f51-a4d4-9a4f7d3a3c11",
    "status":    "created",
    "timestamp": "2026-05-21T10:00:00+00:00"
  }
  ```
  > Nota: el brief especificaba `"status": "accepted"`; el código real devuelve `"status": "created"`. Honramos el código.
- **Errores**: 401 (sin API key), 422 (campos faltantes/inválidos), 503 (`Event store not available`).

### 10. `GET /api/v1/auth/me`

- **Descripción**: Validación de credenciales del cliente (lo que el brief llamaba `/api/v1/auth/validate`). Definido en `app/api/v1/auth.py:get_current_user`. Acepta `X-API-Key` o `Bearer JWT` vía `verify_auth`.
- **Auth**: X-API-Key (preferido para servicio-a-servicio) **o** Bearer JWT.
- **Response 200** (`ApiKeyValidation`):
  ```json
  {
    "username":      "biohack-app",
    "auth_method":   "apikey",
    "auth_identity": "biohack-app"
  }
  ```
  > Nota: el brief pedía `{valid, permissions, rate_limit}`. Esos campos NO existen en `/api/v1/auth/me`. Los exponemos como **opcionales en el modelo Pydantic** para que el mock pueda extender la respuesta cuando se añada un endpoint dedicado `/auth/validate`; mientras tanto el endpoint real devuelve sólo los tres primeros.
- **Errores**: 401 si el API key es inválido o falta.

### 11. `GET /api/v1/health/services`

- **Descripción**: Service registry. No existe `/system/registry/{service}` separado; el endpoint real listo es `app/api/v1/health.py:services_status` que devuelve **todos** los servicios. biohack-app lo consulta a través de `IdmServiceClient` para descubrir peers.
- **Auth**: ninguna.
- **Response 200** (`ServiceRegistryResponse`):
  ```json
  {
    "services": {
      "health":    {"name": "biohack-app",     "url": "http://biohack:8000",  "enabled": true,  "healthy": true,  "latency_ms": 1.4, "error": null},
      "research":  {"name": "canela-molida",   "url": "http://canela:8001",   "enabled": true,  "healthy": false, "latency_ms": null, "error": "timeout"},
      "education": {"name": "ideacursi-tool",  "url": "http://ideacursi:8002","enabled": true,  "healthy": true,  "latency_ms": 2.1, "error": null},
      "security":  {"name": "cybertools",      "url": "http://cybertools:8003","enabled": true, "healthy": true,  "latency_ms": 1.8, "error": null}
    }
  }
  ```
- **Errores**: 500.

---

## Notas

- **Estado de validación**: las shapes marcadas INFERRED están pendientes de T0.1 (cuando biohack-app se monte como repo hermano). En código de Micelia se observa cómo se serializa la salida que va al gateway o cómo se consume la entrada en `app/cli.py`/`app/api/v1/ai.py`, pero no se ha contrastado con el servidor real.
- **Estricto**: `contracts.py` usa `model_config = ConfigDict(extra="forbid")` en todos los modelos. Cualquier campo extra en los mocks rompe el test intencionadamente — es la red de seguridad contra drift entre el contrato documentado y la realidad que el mock simula.
- **Auth uniforme**: Micelia (y por tanto los mocks) usan `X-API-Key`, no `Authorization: Bearer`, para servicio-a-servicio. JWT Bearer está reservado al dashboard. El modelo `ApiKeyValidation` deja `auth_method` libre para reflejar cualquiera de los dos.
- **`ALLOWED_SOURCES`** = 5 dominios funcionales + el propio orquestador: `("biohack", "canela", "ideacursi", "cybertools", "auto-mat-ion", "micelia")`. Está alineado con la decisión de T1.4 (añadir `"micelia"` como 6º source para eventos internos del orquestador). `contracts.py` lo exporta como tupla; T2.2 importará y usará la tupla tanto para validar `EventCreate.source` (via `Literal`) como para fixtures.

### Divergencias brief ↔ código (resueltas a favor del código)

1. `EventCreate`: `subcategory/action/metadata/tags` en vez de `context/occurred_at`.
2. `EventCreated.status` = `"created"` (no `"accepted"`).
3. `BioSavantChatRequest`: `message`/`health_context` reales; añadimos `user_id`/`context_window` opcionales para el escenario T2.3.
4. `MLPredictionRequest`: `metrics` real + alias opcional `model_name`/`features`.
5. `/auth/me` en lugar de `/auth/validate`; campos extra opcionales.
6. `/health/services` reemplaza a `/system/registry/{service}` (no hay endpoint per-service en el código actual).
