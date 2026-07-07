"""
Configuración de logging con Loguru.
"""

import sys

from loguru import logger

from .config import settings


def setup_logging():
    """Configura el sistema de logging"""

    # Remover handler por defecto
    logger.remove()

    # Formato de log
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Loguru exige niveles en MAYÚSCULAS (DEBUG/INFO/WARNING/ERROR/CRITICAL).
    # Uvicorn los acepta en minúsculas; normalizamos aquí para que el mismo
    # env LOG_LEVEL pueda servir a ambos (e.g. `LOG_LEVEL=warning make dev`).
    level = settings.log_level.upper()

    # Console handler
    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=True,
    )

    # File handler (solo en producción)
    if settings.is_production:
        logger.add(
            "logs/micelia.log",
            format=log_format,
            level="INFO",
            rotation="1 day",
            retention="30 days",
            compression="gz",
        )

    return logger


# Logger global
log = setup_logging()
