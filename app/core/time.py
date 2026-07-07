"""
Helpers de tiempo para Micelia.

El schema actual usa columnas SQLAlchemy `DateTime` (sin `timezone=True`), que
Postgres mapea a `TIMESTAMP WITHOUT TIME ZONE`. asyncpg rechaza valores
tz-aware contra esas columnas con un error tipo:

    asyncpg.exceptions.DataError: can't subtract offset-naive and offset-aware datetimes

Hasta migrar las columnas a `TIMESTAMP WITH TIME ZONE` (decisión diferida a
v0.2 porque implica migración Alembic), usar siempre `utcnow_naive()` en lugar
de `datetime.now(timezone.utc)` cuando el valor vaya a una columna de modelo.
La intención sigue siendo UTC, simplemente sin el tag `tzinfo`.
"""

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Devuelve la hora UTC actual SIN tzinfo.

    Equivalente semántico a `datetime.utcnow()` (deprecated en Python 3.12+)
    pero implementado con la API moderna `datetime.now(timezone.utc)` y luego
    descartando el tag de timezone.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utcnow_aware() -> datetime:
    """Devuelve la hora UTC actual CON tzinfo=UTC.

    Úsalo para lógica de aplicación (cálculos, comparaciones, serialización a
    ISO 8601 con sufijo Z). NO lo pases directamente a columnas SQLAlchemy
    `DateTime` sin `timezone=True` — usa `utcnow_naive()` para eso.
    """
    return datetime.now(timezone.utc)
