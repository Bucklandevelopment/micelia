"""
Datos sintéticos deterministas para la batería E2E (T2.3).

Provee:

- 3 perfiles de usuario sintéticos (joven sano, adulto con estrés moderado,
  senior con comorbilidades).
- Factories de series temporales de biomarkers (90 días por defecto),
  reproducibles via semilla derivada del par ``(user_id, metric)``.
- Respuestas plausibles de Bio-Savant (regla simple sobre keywords).
- Predicciones plausibles de ML Production (mini-regresiones de juguete).
- Builders de `EventCreate` (singular y por lotes).

Reglas de oro
-------------

- **Determinismo absoluto.** Todo `random.Random` se siembra con un hash
  estable de los argumentos: la misma llamada produce siempre el mismo
  payload, también entre procesos.
- **Auto-contenido.** No se importa nada de ``app/``. Todas las
  dependencias vienen de la stdlib y de ``tests.e2e.mocks.contracts``.
- **Fecha base fija.** Las series usan ``BASE_DATE`` (2026-05-01 08:00 UTC)
  como ancla; nunca ``datetime.utcnow()``. Esto es lo que permite que un
  test escrito hoy y otro escrito en seis meses comparen el mismo JSON.

Rangos plausibles
-----------------

Los valores baseline y los desvíos típicos provienen de literatura
divulgativa y no constituyen referencia clínica. Ver tabla en
``_METRIC_SIGMA`` y ``_METRIC_DRIFT_PER_DAY``. Documentado más abajo,
junto a las constantes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from tests.e2e.mocks.contracts import (
    ALLOWED_SOURCES,
    BiomarkerPoint,
    BiomarkerSeries,
    BioSavantChatResponse,
    BioSavantSource,
    EventCreate,
    MLPredictionResponse,
)

# =============================================================================
# Constantes deterministas
# =============================================================================

#: Ancla temporal usada por las series. Cualquier punto i en un rango de
#: ``days`` se ubica en ``BASE_DATE - timedelta(days=days - 1 - i)``, de
#: modo que el último punto coincide siempre con BASE_DATE.
BASE_DATE: datetime = datetime(2026, 5, 1, 8, 0, 0, tzinfo=timezone.utc)


#: Unidad SI/clínica esperada por el contrato para cada métrica conocida.
#: Si una métrica desconocida se solicita, se asume ``"unit"`` genérica.
_METRIC_UNITS: dict[str, str] = {
    "hrv": "ms",                 # heart-rate variability (RMSSD)
    "vo2max": "ml/kg/min",       # consumo máximo de oxígeno
    "resting_hr": "bpm",         # frecuencia cardiaca en reposo
    "weight_kg": "kg",
    "sleep_h": "hours",          # horas de sueño nocturno
    "steps": "count",            # pasos diarios
    "glucose": "mg/dL",          # glucosa en ayunas
}


#: Desviación típica (gaussiana) aplicada alrededor del baseline.
#: Valores curados para reflejar variabilidad día-a-día razonable:
#: HRV ±5 ms es realista, peso ±0.3 kg es ruido de báscula, etc.
_METRIC_SIGMA: dict[str, float] = {
    "hrv": 5.0,
    "vo2max": 0.8,
    "resting_hr": 2.5,
    "weight_kg": 0.3,
    "sleep_h": 0.6,
    "steps": 1200.0,
    "glucose": 6.0,
}


#: Drifts lineales por día (con signo) por (user_id, metric).
#: Sirven para simular tendencias suaves (p.ej. pérdida de peso o
#: deterioro de HRV en el perfil senior). Se aplican como
#: ``value += drift * day_index`` donde ``day_index=0`` corresponde al
#: primer punto de la serie.
_METRIC_DRIFT_PER_DAY: dict[tuple[str, str], float] = {
    # adulto con estrés moderado pierde algo de peso a lo largo de 90 días
    ("u_adult_medium", "weight_kg"): -0.05,
    # senior tiende a empeorar HRV ligeramente
    ("u_senior_comorbid", "hrv"): -0.02,
    # joven sano gana pasos a medida que entrena
    ("u_young_healthy", "steps"): 30.0,
}


# =============================================================================
# Perfil de usuario
# =============================================================================


@dataclass(frozen=True)
class SyntheticProfile:
    """Perfil de usuario sintético, curado a mano.

    Se modela como dataclass (no Pydantic) porque los valores son fijos y
    no necesitamos validación en runtime: ya están hardcodeados en
    ``PROFILES`` y los tests los consumen tal cual.

    Attributes
    ----------
    user_id:
        Identificador estable, usable como llave en ``PROFILES`` y en URLs.
    name:
        Etiqueta humana ("Alex (24)") para mensajes y debugging.
    age:
        Edad en años cumplidos.
    sex:
        ``"F"`` o ``"M"``. Acotado deliberadamente; los tests no
        ejercitan otras categorías por ahora.
    baseline_metrics:
        Valores baseline por métrica. Estos son los que ``biomarker_series``
        usa como media para ruido gaussiano.
    condition:
        Etiqueta semántica del perfil (``"healthy"``, ``"moderate_stress"``,
        ``"comorbidities"``). No es una categoría médica formal, solo un
        hint para los tests.
    """

    user_id: str
    name: str
    age: int
    sex: str
    baseline_metrics: dict[str, float]
    condition: str
    notes: tuple[str, ...] = field(default_factory=tuple)


#: Catálogo de perfiles sintéticos.
#:
#: Rangos plausibles (referencia divulgativa, no clínica):
#: - HRV (RMSSD): 70-110 ms en jóvenes sanos, 40-70 adulto medio,
#:   20-40 senior con comorbilidades.
#: - VO2max: 45-55 mujer joven entrenada, 35-42 hombre adulto medio,
#:   18-25 senior sedentario.
#: - Resting HR: 50-60 atlético, 60-72 medio, 70-85 senior.
#: - Sleep horas: 7-9 ideal, 6-7 estrés crónico, 5-6.5 senior.
PROFILES: dict[str, SyntheticProfile] = {
    "u_young_healthy": SyntheticProfile(
        user_id="u_young_healthy",
        name="Alex (24)",
        age=24,
        sex="F",
        baseline_metrics={
            "hrv": 90.0,
            "vo2max": 52.0,
            "resting_hr": 55,
            "weight_kg": 60.0,
            "sleep_h": 7.8,
            "steps": 9500.0,
            "glucose": 88.0,
        },
        condition="healthy",
        notes=("Sin patología conocida. Entrena 4-5 días/semana.",),
    ),
    "u_adult_medium": SyntheticProfile(
        user_id="u_adult_medium",
        name="Sam (42)",
        age=42,
        sex="M",
        baseline_metrics={
            "hrv": 55.0,
            "vo2max": 38.0,
            "resting_hr": 65,
            "weight_kg": 82.0,
            "sleep_h": 6.5,
            "steps": 6000.0,
            "glucose": 96.0,
        },
        condition="moderate_stress",
        notes=("Trabajo de oficina. Carga laboral alta. Sedentarismo leve.",),
    ),
    "u_senior_comorbid": SyntheticProfile(
        user_id="u_senior_comorbid",
        name="Pat (68)",
        age=68,
        sex="F",
        baseline_metrics={
            "hrv": 28.0,
            "vo2max": 22.0,
            "resting_hr": 75,
            "weight_kg": 78.0,
            "sleep_h": 5.8,
            "steps": 3200.0,
            "glucose": 128.0,
        },
        condition="comorbidities",
        notes=(
            "Diabetes tipo 2 controlada con metformina.",
            "Hipertensión esencial, medicación estable.",
        ),
    ),
}


# =============================================================================
# 1. biomarker_series — series temporales reproducibles
# =============================================================================


def _seed_for(user_id: str, metric: str) -> int:
    """Semilla determinista, estable entre procesos."""

    return hash((user_id, metric)) & 0xFFFFFFFF


def biomarker_series(
    user_id: str,
    metric: str,
    days: int = 90,
) -> BiomarkerSeries:
    """Construye una `BiomarkerSeries` plausible y reproducible.

    Parameters
    ----------
    user_id:
        Debe existir en ``PROFILES``. Si no, lanza ``KeyError``.
    metric:
        Nombre de la métrica (p. ej. ``"hrv"``, ``"vo2max"``). Si la
        métrica no está en ``baseline_metrics`` del perfil, lanza
        ``KeyError``. Si no hay unidad conocida, se usa ``"unit"``.
    days:
        Nº de puntos diarios (uno por día a las 08:00 UTC). Default 90.

    Returns
    -------
    BiomarkerSeries
        El último punto cae sobre ``BASE_DATE``; el primero en
        ``BASE_DATE - timedelta(days=days - 1)``.

    Notes
    -----
    - El generador usa una instancia local de ``random.Random`` sembrada
      con ``_seed_for(user_id, metric)``. No toca el estado global de
      ``random``.
    - Se aplica un drift lineal opcional (ver ``_METRIC_DRIFT_PER_DAY``).
    - Los pasos (``steps``) se redondean a entero porque el campo en el
      contrato es ``float`` pero la unidad ``"count"`` no tolera decimales
      observables.
    """

    profile = PROFILES[user_id]
    baseline = float(profile.baseline_metrics[metric])
    sigma = _METRIC_SIGMA.get(metric, max(abs(baseline) * 0.05, 0.1))
    unit = _METRIC_UNITS.get(metric, "unit")
    drift = _METRIC_DRIFT_PER_DAY.get((user_id, metric), 0.0)

    rng = random.Random(_seed_for(user_id, metric))

    points: list[BiomarkerPoint] = []
    for i in range(days):
        ts = BASE_DATE - timedelta(days=days - 1 - i)
        noise = rng.gauss(0.0, sigma)
        value = baseline + drift * i + noise
        if metric == "steps":
            value = float(max(0, round(value)))
        else:
            # 2 decimales: limita ruido de coma flotante en assertions.
            value = round(value, 2)
        points.append(BiomarkerPoint(timestamp=ts, value=value))

    return BiomarkerSeries(
        user_id=user_id,
        metric=metric,
        unit=unit,
        points=points,
    )


# =============================================================================
# 2. bio_savant_response — respuestas curadas por keyword
# =============================================================================


_BIO_SAVANT_LIBRARY: tuple[tuple[tuple[str, ...], str, list[BioSavantSource], list[str]], ...] = (
    (
        ("vo2", "vo2max", "cardiorespiratory", "aerobic"),
        (
            "VO2max es el principal predictor de mortalidad por todas las "
            "causas en adultos. Un programa estructurado de 4x4 minutos "
            "(HIIT) 2-3 veces por semana puede aumentarlo un 10-15% en "
            "12 semanas en personas sedentarias."
        ),
        [
            BioSavantSource(
                title="Cardiorespiratory fitness and mortality (meta-analysis)",
                url="https://pubmed.ncbi.nlm.nih.gov/30418471/",
                confidence=0.88,
            ),
            BioSavantSource(
                title="HIIT vs MICT for VO2max improvements",
                url="https://pubmed.ncbi.nlm.nih.gov/24552376/",
                confidence=0.82,
            ),
        ],
        [
            "Detectado intent VO2max.",
            "Consultando literatura sobre cardiorespiratory fitness.",
            "Compongo respuesta con plan de ejercicio HIIT como anchor.",
        ],
    ),
    (
        ("hrv", "heart rate variability", "variabilidad"),
        (
            "La HRV (RMSSD) refleja el tono parasimpático. Cifras altas y "
            "estables se asocian con mejor recuperación. Mejorarla pasa "
            "por sueño consistente, respiración diafragmática lenta y "
            "limitar alcohol nocturno."
        ),
        [
            BioSavantSource(
                title="HRV as biomarker of autonomic recovery",
                url="https://pubmed.ncbi.nlm.nih.gov/28785220/",
                confidence=0.86,
            ),
            BioSavantSource(
                title="Slow breathing protocols and HRV",
                url="https://pubmed.ncbi.nlm.nih.gov/29034226/",
                confidence=0.79,
            ),
        ],
        [
            "Detectado intent HRV.",
            "Cruzo con health_context si existe baseline.",
            "Propongo intervenciones de bajo riesgo (respiración, sueño).",
        ],
    ),
    (
        ("sleep", "sueño", "insomnia", "circadian"),
        (
            "El sueño profundo (N3) y REM se acortan con la edad y el "
            "estrés. Higiene básica: mismo horario ±30 min, oscuridad "
            "total, temperatura 18-20ºC, sin pantallas 60 min antes."
        ),
        [
            BioSavantSource(
                title="Sleep, health, and aging",
                url="https://pubmed.ncbi.nlm.nih.gov/28579842/",
                confidence=0.84,
            ),
            BioSavantSource(
                title="Cognitive behavioral therapy for insomnia (CBT-I)",
                url="https://pubmed.ncbi.nlm.nih.gov/25622950/",
                confidence=0.80,
            ),
        ],
        [
            "Detectado intent sueño.",
            "Priorizo intervenciones conductuales antes que farmacológicas.",
        ],
    ),
    (
        ("glucose", "glucosa", "insulin", "diabetes"),
        (
            "La glucosa en ayunas >100 mg/dL sostenida sugiere "
            "prediabetes. Caminar 10-15 min tras las comidas reduce el "
            "pico postprandial entre un 12% y un 22% en estudios "
            "controlados."
        ),
        [
            BioSavantSource(
                title="Post-meal walking and glycemic control",
                url="https://pubmed.ncbi.nlm.nih.gov/35199255/",
                confidence=0.85,
            ),
            BioSavantSource(
                title="ADA Standards of Care 2024 — diagnosis",
                url="https://pubmed.ncbi.nlm.nih.gov/38078592/",
                confidence=0.90,
            ),
        ],
        [
            "Detectado intent glucosa.",
            "Compongo respuesta conservadora y derivable a clínico.",
        ],
    ),
)


_BIO_SAVANT_FALLBACK = (
    "No tengo un protocolo específico para esa consulta. Recomiendo "
    "compartirla con tu equipo clínico y, si es divulgativa, formularla "
    "en términos de un biomarker concreto (HRV, VO2max, sueño, glucosa) "
    "para que pueda apoyarme en literatura.",
    [
        BioSavantSource(
            title="Bio-Savant default knowledge index",
            url="https://pubmed.ncbi.nlm.nih.gov/?term=lifestyle+medicine",
            confidence=0.5,
        ),
    ],
    [
        "Sin match de keyword.",
        "Respondo con fallback conservador.",
    ],
)


def bio_savant_response(user_id: str, message: str) -> BioSavantChatResponse:
    """Respuesta plausible y determinista de Bio-Savant.

    El ``user_id`` se acepta para futura personalización (rangos por
    edad/sexo); hoy no altera la respuesta pero sí queda registrado en el
    ``reasoning_trace`` para que los tests puedan asegurar trazabilidad.
    """

    msg = (message or "").lower()
    for keywords, answer, sources, trace in _BIO_SAVANT_LIBRARY:
        if any(k in msg for k in keywords):
            return BioSavantChatResponse(
                answer=answer,
                sources=list(sources),
                reasoning_trace=[f"user_id={user_id}", *trace],
            )

    fallback_answer, fallback_sources, fallback_trace = _BIO_SAVANT_FALLBACK
    return BioSavantChatResponse(
        answer=fallback_answer,
        sources=list(fallback_sources),
        reasoning_trace=[f"user_id={user_id}", *fallback_trace],
    )


# =============================================================================
# 3. ml_prediction — predicciones de juguete deterministas
# =============================================================================


def _confidence_from(model_name: str, features: dict[str, Any]) -> float:
    """Confianza determinista en ``[0.6, 0.95]``.

    Usa una semilla derivada del modelo y de un fingerprint estable de las
    features (ordena keys para que ``{"a":1,"b":2}`` y ``{"b":2,"a":1}``
    den el mismo número).
    """

    fp = tuple(sorted((k, repr(v)) for k, v in features.items()))
    rng = random.Random(hash((model_name, fp)) & 0xFFFFFFFF)
    return round(rng.uniform(0.6, 0.95), 3)


def _energy_model(features: dict[str, Any]) -> float:
    """Regresión lineal de juguete para "energía subjetiva" (0-100).

    Combina HRV, horas de sueño y pasos. Coeficientes elegidos para que
    el output quede en un rango plausible (0-100) con perfiles normales.
    """

    hrv = float(features.get("hrv", 60.0))
    sleep_h = float(features.get("sleep_h", 7.0))
    steps = float(features.get("steps", 6000.0))
    raw = 0.35 * hrv + 6.0 * sleep_h + 0.0015 * steps
    return round(max(0.0, min(100.0, raw)), 2)


def _longevity_model(features: dict[str, Any]) -> float:
    """Score de "longevidad relativa" (años de esperanza ajustada).

    Heurística simple: VO2max alto suma años, la edad resta. NO es una
    estimación clínica.
    """

    vo2max = float(features.get("vo2max", 35.0))
    age = float(features.get("age", 40.0))
    base = 80.0
    delta = (vo2max - 35.0) * 0.4 - (age - 40.0) * 0.2
    return round(base + delta, 2)


def _stress_model(features: dict[str, Any]) -> float:
    """Score de estrés (0=relajado, 100=alarmante)."""

    hrv = float(features.get("hrv", 60.0))
    resting_hr = float(features.get("resting_hr", 65.0))
    sleep_h = float(features.get("sleep_h", 7.0))
    raw = 100.0 - 0.6 * hrv + 0.5 * (resting_hr - 60.0) - 5.0 * (sleep_h - 7.0)
    return round(max(0.0, min(100.0, raw)), 2)


_ML_MODELS: dict[str, Callable[[dict[str, Any]], float]] = {
    "energy_model": _energy_model,
    "longevity_model": _longevity_model,
    "stress_model": _stress_model,
}


def ml_prediction(
    model_name: str,
    features: dict[str, Any],
) -> MLPredictionResponse:
    """Predicción determinista para un modelo de juguete.

    Parameters
    ----------
    model_name:
        Debe estar en ``_ML_MODELS``. Si no, devuelve un valor "no_op"
        (``prediction=None``) con confianza baja, sin levantar excepción:
        los tests negativos pueden ejercitarlo sin try/except.
    features:
        Diccionario libre. Cada función documenta qué claves consume.

    Returns
    -------
    MLPredictionResponse
        ``model_version = f"{model_name}@1.0.0-mock"``. ``confidence``
        determinista en ``[0.6, 0.95]``; en el caso ``no_op`` baja a 0.1.
    """

    fn = _ML_MODELS.get(model_name)
    if fn is None:
        return MLPredictionResponse(
            prediction=None,
            confidence=0.1,
            model_version=f"{model_name}@1.0.0-mock",
        )

    prediction = fn(features)
    confidence = _confidence_from(model_name, features)
    return MLPredictionResponse(
        prediction=prediction,
        confidence=confidence,
        model_version=f"{model_name}@1.0.0-mock",
    )


# =============================================================================
# 4. EventCreate fixtures
# =============================================================================


def make_event(
    source: str = "biohack",
    category: str = "health",
    **overrides: Any,
) -> EventCreate:
    """Construye un `EventCreate` válido con defaults razonables.

    Defaults:

    - ``action="create"``
    - ``event_type=f"{source}.{category}.test"``
    - ``payload={}``, ``metadata={}``, ``tags=[]``

    Cualquier campo declarado en ``EventCreate`` puede sobreescribirse vía
    keyword en ``overrides``. La validación Pydantic se ejecuta al
    construir, así que pasar valores inválidos lanza ``ValidationError``,
    lo cual es el comportamiento deseado para tests negativos.
    """

    payload: dict[str, Any] = {
        "category": category,
        "source": source,
        "action": "create",
        "event_type": f"{source}.{category}.test",
    }
    payload.update(overrides)
    return EventCreate(**payload)


def random_event_batch(n: int, seed: int = 42) -> list[EventCreate]:
    """Devuelve `n` eventos con sources/categorías/actions pseudo-aleatorios.

    Determinismo: mismo ``(n, seed)`` produce siempre la misma lista (y
    el mismo orden). Útil para tests de filtrado y de carga ligera.

    La elección se hace sólo entre valores válidos del contrato:
    ``ALLOWED_SOURCES`` (6 sources), 6 categorías y 5 actions. Los
    ``event_type`` siguen el patrón ``"{source}.{category}.{action}"``
    seguido de un sufijo numérico que mantiene el contenido único.
    """

    if n < 0:
        raise ValueError("n must be non-negative")

    categories = ("health", "education", "research", "security", "system", "identity")
    actions = ("create", "update", "delete", "query", "analyze")

    rng = random.Random(seed)
    batch: list[EventCreate] = []
    for i in range(n):
        source = rng.choice(ALLOWED_SOURCES)
        category = rng.choice(categories)
        action = rng.choice(actions)
        batch.append(
            EventCreate(
                category=category,  # type: ignore[arg-type]
                source=source,  # type: ignore[arg-type]
                action=action,  # type: ignore[arg-type]
                event_type=f"{source}.{category}.{action}.{i:04d}",
                payload={"index": i, "seed": seed},
                tags=[f"seed:{seed}", f"i:{i}"],
            )
        )
    return batch


# =============================================================================
# Export público
# =============================================================================


__all__ = (
    "SyntheticProfile",
    "PROFILES",
    "BASE_DATE",
    "biomarker_series",
    "bio_savant_response",
    "ml_prediction",
    "make_event",
    "random_event_batch",
)
