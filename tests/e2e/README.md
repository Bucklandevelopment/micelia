# Tests E2E — Micelia

## Propósito

Esta carpeta contiene la batería de tests end-to-end de la API de Micelia
(antes `vital-core` / `idm-core`). A diferencia de los tests unitarios bajo
`tests/`, aquí se ejercita la aplicación FastAPI completa a través de un
cliente ASGI real, y las dependencias externas se interceptan con `respx`
(para `httpx`) y `pytest-httpx`, sin levantar procesos ni contenedores.

El objetivo es validar contratos completos (auth -> health -> bio-savant ->
recomendaciones, ciclo de eventos, gateway proxy, SDK Python, etc.) sin
depender de servicios reales.

## Cómo ejecutar

Desde la raíz del repo, con el `.venv` activado:

```bash
pytest tests/e2e/
```

Subconjuntos:

```bash
pytest tests/e2e/ -k "happy_path"
pytest tests/e2e/ -m "not slow"
```

Cobertura solo de E2E:

```bash
pytest tests/e2e/ --cov=app --cov-report=term-missing
```

## Estructura

```
tests/e2e/
├── README.md          # este documento
├── __init__.py
├── conftest.py        # fixtures globales del paquete E2E
├── mocks/             # mock servers in-process (respx) por dominio
│   └── __init__.py
└── fixtures/          # datos sintéticos y factories Pydantic
    └── __init__.py
```

- `mocks/` agrupa los mocks de servicios upstream (por ejemplo
  `mocks/biohack.py` con el mock del contrato Micelia <-> biohack-app).
- `fixtures/` contiene factories y datos sintéticos reutilizables
  (usuarios, biomarkers, recomendaciones, eventos, etc.).

## Convenciones

- **HTTP upstream**: siempre `respx` (o `pytest-httpx` para casos puntuales).
  Nunca llamadas reales a servicios externos desde un test E2E.
- **API Micelia**: cliente ASGI sobre la app FastAPI
  (`httpx.AsyncClient(transport=ASGITransport(app=app))`), no `TestClient`
  síncrono.
- **Async por defecto**: el `conftest.py` aplica `pytest.mark.asyncio` a
  todos los tests; no hace falta marcarlos individualmente.
- **Aislamiento**: cada test debe ser independiente y no asumir estado
  global. Usar fixtures de scope `function` para mocks y datos.
- **Naming**: `test_<area>_<comportamiento>.py`
  (p. ej. `test_auth_login_happy_path.py`, `test_gateway_proxy_errors.py`).
- **Marcadores**: usar `@pytest.mark.slow` para tests que tarden > 1s.

## Mocks

La fixture `biohack_mock` está disponible globalmente (re-exportada en
`conftest.py`). Intercepta vía `respx` todas las llamadas HTTP que Micelia
hace hacia `settings.health_service_url` y devuelve payloads conformes al
contrato definido en `tests/e2e/mocks/contracts.py` (T2.1).

```python
async def test_health_pass_through(biohack_mock, client):
    biohack_mock.set_mode("healthy")
    resp = await client.get("/api/v1/health/detailed")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
```

Modos soportados:

- `"healthy"` — todos los endpoints responden 200 con datos válidos.
- `"degraded"` — `/health` reporta `"degraded"` y un subconjunto de servicios
  aparece `healthy=false` (p. ej. `database`, `research`).
- `"down"` — todos los endpoints responden 503.
- `"slow"` — respuestas tardan `slow_delay_seconds` (default 2s) y luego
  responden como en `"healthy"`. Útil para tests de timeout.

Para suites cuyos tests comparten el mismo modo y no se beneficien de
aislamiento por test, usar `biohack_mock_module` (scope `module`).

## Datos sintéticos

`tests/e2e/fixtures/data.py` (T2.3) provee factories deterministas para
los datos que consumen el mock server (T2.2), los happy paths (T3.1), los
tests de eventos (T3.4) y el frontend con backend mock (T4.1).

### Perfiles

Tres perfiles curados a mano en `PROFILES`:

- `u_young_healthy` — Alex, 24, F. Atleta amateur, sin patología.
- `u_adult_medium`  — Sam, 42, M. Sedentarismo leve, estrés moderado.
- `u_senior_comorbid` — Pat, 68, F. Diabetes T2 + hipertensión.

### Uso típico

```python
from tests.e2e.fixtures.data import (
    PROFILES,
    biomarker_series,
    bio_savant_response,
    ml_prediction,
    make_event,
    random_event_batch,
)

# Series temporales reproducibles (último punto = 2026-05-01 08:00 UTC).
series = biomarker_series("u_young_healthy", "hrv", days=90)
assert series.unit == "ms"
assert len(series.points) == 90

# Respuesta plausible de Bio-Savant a partir de keywords del mensaje.
chat = bio_savant_response("u_adult_medium", "How do I improve my VO2max?")
assert chat.sources  # citas placeholder a PubMed.

# Predicción determinista de un modelo de juguete.
pred = ml_prediction("energy_model", {"hrv": 90, "sleep_h": 8, "steps": 10000})
assert 0.6 <= pred.confidence <= 0.95
assert pred.model_version.endswith("-mock")

# EventCreate con defaults razonables.
event = make_event(source="biohack", category="health", payload={"k": 1})

# Lote pseudo-aleatorio pero determinista por seed.
batch = random_event_batch(20, seed=42)
```

### Garantías

- **Determinismo absoluto**: misma entrada → misma salida (también entre
  procesos). Las semillas se derivan de hashes estables de los argumentos.
- **Sin estado global**: cada factory usa su propio `random.Random`.
- **Fecha base fija**: `BASE_DATE = 2026-05-01T08:00:00Z`. Las series
  retroceden desde ahí; nada depende de `datetime.utcnow()`.
- **Validación Pydantic**: todas las factories devuelven instancias de
  los modelos de `tests/e2e/mocks/contracts.py`, así que un drift de
  contrato hace fallar la construcción del fixture, no el test final.
