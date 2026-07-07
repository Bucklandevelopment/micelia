"""
API para el Sistema de Energía Inteligente.

Monitorea:
- Estado de batería
- Producción solar (si disponible)
- Estado de red
- Decisiones de cómputo basadas en energía
"""

import asyncio
import re
import subprocess
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, Depends, Request, WebSocket
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import log
from app.core.security import verify_auth

router = APIRouter(prefix="/energy", dependencies=[Depends(verify_auth)])


class EnergyState(str, Enum):
    ABUNDANT = "abundant"
    NORMAL = "normal"
    CONSERVING = "conserving"
    CRITICAL = "critical"
    SURVIVAL = "survival"


class EnergyStatus(BaseModel):
    state: EnergyState
    battery_level: int
    is_charging: bool
    time_remaining_minutes: int
    solar_available: bool
    solar_watts: float
    is_online: bool
    power_source: str
    recommendations: list[str]


class ComputeRecommendation(BaseModel):
    prefer_local: bool
    prefer_cloud: bool
    max_concurrent_tasks: int
    allow_heavy_compute: bool
    reasoning: list[str]


def get_battery_status() -> dict:
    """Lee estado de batería via pmset (macOS)"""
    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=5
        )

        output = result.stdout

        # Parsear porcentaje
        level_match = re.search(r'(\d+)%', output)
        level = int(level_match.group(1)) if level_match else 100

        # Parsear estado de carga
        is_charging = "AC Power" in output or "charging" in output

        # Parsear tiempo restante
        time_match = re.search(r'(\d+):(\d+) remaining', output)
        if time_match:
            hours, mins = int(time_match.group(1)), int(time_match.group(2))
            time_remaining = hours * 60 + mins
        else:
            time_remaining = -1

        # Determinar fuente de energía
        if "AC Power" in output:
            power_source = "ac"
        elif "Battery Power" in output:
            power_source = "battery"
        else:
            power_source = "unknown"

        return {
            "level": level,
            "is_charging": is_charging,
            "time_remaining": time_remaining,
            "power_source": power_source
        }
    except Exception as e:
        log.error(f"Error reading battery: {e}")
        return {
            "level": 100,
            "is_charging": True,
            "time_remaining": -1,
            "power_source": "unknown"
        }


def calculate_state(battery: dict, solar_watts: float, is_online: bool) -> EnergyState:
    """Calcula el estado de energía basado en condiciones"""
    level = battery["level"]
    charging = battery["is_charging"]

    # SURVIVAL: Sin internet y batería muy baja
    if not is_online and level < 5:
        return EnergyState.SURVIVAL

    # CRITICAL: Batería muy baja
    if level < 20 and not charging:
        return EnergyState.CRITICAL

    # CONSERVING: Batería baja
    if level < 50 and not charging:
        return EnergyState.CONSERVING

    # ABUNDANT: Solar activo y batería alta
    if solar_watts > 50 and level > 80:
        return EnergyState.ABUNDANT

    # NORMAL: Caso por defecto
    return EnergyState.NORMAL


def get_recommendations(state: EnergyState, battery: dict) -> list[str]:
    """Genera recomendaciones basadas en el estado"""
    recs = []

    if state == EnergyState.ABUNDANT:
        recs.append("Aprovechar energía solar para tareas pesadas")
        recs.append("Ejecutar entrenamiento de modelos ML")
        recs.append("Sincronización agresiva habilitada")

    elif state == EnergyState.NORMAL:
        recs.append("Operación normal")
        recs.append("Balance entre local y cloud")

    elif state == EnergyState.CONSERVING:
        recs.append("Preferir cloud sobre cómputo local")
        recs.append("Reducir frecuencia de sincronización")
        recs.append("Diferir tareas no críticas")

    elif state == EnergyState.CRITICAL:
        recs.append("ALERTA: Batería crítica")
        recs.append("Solo operaciones esenciales")
        recs.append("Cloud obligatorio para cómputo")

    elif state == EnergyState.SURVIVAL:
        recs.append("MODO SUPERVIVENCIA")
        recs.append("Solo operaciones locales esenciales")
        recs.append("Guardar estado para hibernación")

    return recs


@router.get("/status", response_model=EnergyStatus)
async def get_energy_status():
    """Estado actual del sistema de energía"""

    battery = get_battery_status()

    # Solar (placeholder - requiere integración real)
    solar_available = settings.solar_api_url is not None
    solar_watts = 0.0  # TODO: Leer de API solar si disponible

    # Verificar conectividad
    is_online = True  # TODO: Verificar realmente

    state = calculate_state(battery, solar_watts, is_online)
    recommendations = get_recommendations(state, battery)

    return EnergyStatus(
        state=state,
        battery_level=battery["level"],
        is_charging=battery["is_charging"],
        time_remaining_minutes=battery["time_remaining"],
        solar_available=solar_available,
        solar_watts=solar_watts,
        is_online=is_online,
        power_source=battery["power_source"],
        recommendations=recommendations
    )


@router.get("/compute-recommendation", response_model=ComputeRecommendation)
async def get_compute_recommendation():
    """Recomendación de cómputo basada en energía"""

    battery = get_battery_status()
    solar_watts = 0.0  # TODO: Leer de API solar
    is_online = True

    state = calculate_state(battery, solar_watts, is_online)

    if state == EnergyState.ABUNDANT:
        return ComputeRecommendation(
            prefer_local=True,
            prefer_cloud=False,
            max_concurrent_tasks=10,
            allow_heavy_compute=True,
            reasoning=[
                "Energía solar disponible",
                "Batería alta",
                "Aprovechar recursos locales"
            ]
        )

    elif state == EnergyState.NORMAL:
        return ComputeRecommendation(
            prefer_local=True,
            prefer_cloud=True,
            max_concurrent_tasks=5,
            allow_heavy_compute=True,
            reasoning=["Operación normal", "Balance local/cloud"]
        )

    elif state == EnergyState.CONSERVING:
        return ComputeRecommendation(
            prefer_local=False,
            prefer_cloud=True,
            max_concurrent_tasks=2,
            allow_heavy_compute=False,
            reasoning=[
                f"Batería al {battery['level']}%",
                "Conservar energía local",
                "Preferir cloud"
            ]
        )

    elif state == EnergyState.CRITICAL:
        return ComputeRecommendation(
            prefer_local=False,
            prefer_cloud=True,
            max_concurrent_tasks=1,
            allow_heavy_compute=False,
            reasoning=[
                f"CRÍTICO: Batería al {battery['level']}%",
                "Solo operaciones esenciales",
                "Cloud obligatorio"
            ]
        )

    else:  # SURVIVAL
        return ComputeRecommendation(
            prefer_local=True,
            prefer_cloud=False,
            max_concurrent_tasks=1,
            allow_heavy_compute=False,
            reasoning=[
                "MODO SUPERVIVENCIA",
                "Sin conectividad",
                "Solo local esencial"
            ]
        )


@router.websocket("/ws")
async def energy_websocket(websocket: WebSocket):
    """WebSocket para updates en tiempo real del estado de energía"""
    await websocket.accept()

    try:
        while True:
            battery = get_battery_status()
            state = calculate_state(battery, 0.0, True)

            await websocket.send_json({
                "type": "energy_update",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "state": state.value,
                    "battery_level": battery["level"],
                    "is_charging": battery["is_charging"],
                    "power_source": battery["power_source"]
                }
            })

            await asyncio.sleep(settings.energy_check_interval)

    except Exception as e:
        log.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()


@router.get("/history")
async def get_energy_history(request: Request, hours: int = 24):
    """Historial de estados de energía"""
    event_store = request.app.state.event_store

    if not event_store:
        return {"events": [], "message": "Event store not available"}

    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    events = await event_store.query_events(
        category="system",
        subcategory="energy",
        since=since,
        limit=500
    )

    return {
        "hours": hours,
        "events": events
    }
