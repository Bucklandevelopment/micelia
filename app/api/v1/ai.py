"""
API para el motor de IA unificado.

Expone:
- CodKing multi-core (salud, educación, ciberseguridad)
- Ollama (LLM local)
- Compute Router (local vs cloud)
"""

from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import log
from app.core.security import verify_auth

router = APIRouter(prefix="/ai", dependencies=[Depends(verify_auth)])


class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    core: Optional[str] = None  # salud, educacion, ciberseguridad


class EmbeddingRequest(BaseModel):
    texts: List[str]
    model: Optional[str] = None


class ThreatDetectionRequest(BaseModel):
    log_content: str
    source: Optional[str] = None


class HealthAnalysisRequest(BaseModel):
    metrics: Dict[str, Any]
    question: Optional[str] = None


@router.get("/status")
async def ai_status(request: Request):
    """Estado de los servicios de IA"""
    client: httpx.AsyncClient = request.app.state.http_client

    status: Dict[str, Any] = {
        "ollama": {"available": False, "models": []},
        "codking": {"available": settings.codking_enabled, "cores": []},
        "compute_router": {"enabled": settings.compute_router_enabled}
    }

    # Verificar Ollama
    try:
        response = await client.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status["ollama"]["available"] = True
            status["ollama"]["models"] = [m["name"] for m in data.get("models", [])]
    except Exception as e:
        log.debug(f"Ollama not available: {e}")

    # CodKing cores
    if settings.codking_enabled:
        status["codking"]["cores"] = ["salud", "educacion", "ciberseguridad"]

    return status


@router.post("/chat")
async def chat(request: Request, chat_request: ChatRequest):
    """
    Chat con el modelo de IA.

    Si se especifica un core (salud, educacion, ciberseguridad),
    usa CodKing. Si no, usa Ollama.
    """
    client: httpx.AsyncClient = request.app.state.http_client

    # Determinar qué modelo usar
    if chat_request.core and settings.codking_enabled:
        # Usar CodKing (via cybertools)
        return await _chat_codking(client, chat_request)
    else:
        # Usar Ollama
        return await _chat_ollama(client, chat_request)


async def _chat_ollama(client: httpx.AsyncClient, chat_request: ChatRequest) -> dict:
    """Chat usando Ollama"""
    model = chat_request.model or settings.ollama_default_model

    try:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": model,
                "messages": [m.model_dump() for m in chat_request.messages],
                "stream": False,
                "options": {
                    "temperature": chat_request.temperature,
                    "num_predict": chat_request.max_tokens
                }
            },
            timeout=120
        )

        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Ollama error")

        data = response.json()

        return {
            "model": model,
            "provider": "ollama",
            "message": {
                "role": "assistant",
                "content": data["message"]["content"]
            },
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0)
            }
        }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Ollama timeout")
    except Exception as e:
        log.error(f"Ollama error: {e}")
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")


async def _chat_codking(client: httpx.AsyncClient, chat_request: ChatRequest) -> dict:
    """Chat usando CodKing (via cybertools API)"""
    try:
        # Concatenar mensajes para CodKing
        text = "\n".join([f"{m.role}: {m.content}" for m in chat_request.messages])

        response = await client.post(
            f"{settings.security_service_url}/classify",
            json={
                "text": text,
                "core": chat_request.core,
                "return_scores": True
            },
            timeout=30
        )

        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="CodKing error")

        data = response.json()

        return {
            "model": "codking",
            "provider": "codking",
            "core": chat_request.core,
            "message": {
                "role": "assistant",
                "content": data.get("response", data.get("predicted_class", ""))
            },
            "metadata": {
                "confidence": data.get("confidence"),
                "scores": data.get("scores")
            }
        }

    except Exception as e:
        log.error(f"CodKing error: {e}")
        raise HTTPException(status_code=502, detail=f"CodKing error: {str(e)}")


@router.post("/embeddings")
async def create_embeddings(request: Request, embed_request: EmbeddingRequest):
    """
    Genera embeddings usando el modelo local (BGE-M3 via Ollama).
    """
    client: httpx.AsyncClient = request.app.state.http_client
    model = embed_request.model or settings.ollama_embedding_model

    try:
        response = await client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={
                "model": model,
                "input": embed_request.texts
            },
            timeout=60
        )

        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Embedding error")

        data = response.json()

        return {
            "model": model,
            "embeddings": data.get("embeddings", []),
            "dimensions": len(data.get("embeddings", [[]])[0]) if data.get("embeddings") else 0
        }

    except Exception as e:
        log.error(f"Embedding error: {e}")
        raise HTTPException(status_code=502, detail=f"Embedding error: {str(e)}")


@router.post("/threat-detection")
async def detect_threat(request: Request, detection_request: ThreatDetectionRequest):
    """
    Detección de amenazas usando CodKing core ciberseguridad.
    """
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        response = await client.post(
            f"{settings.security_service_url}/detect_threat",
            json={
                "log_content": detection_request.log_content,
                "source": detection_request.source
            },
            timeout=30
        )

        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Threat detection error")

        return response.json()

    except Exception as e:
        log.error(f"Threat detection error: {e}")
        raise HTTPException(status_code=502, detail=f"Error: {str(e)}")


@router.post("/health-analysis")
async def analyze_health(request: Request, analysis_request: HealthAnalysisRequest):
    """
    Análisis de salud usando CodKing core salud + RAG de biohack-app.
    """
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        # Si hay pregunta, usar Bio-Savant de biohack-app
        if analysis_request.question:
            response = await client.post(
                f"{settings.health_service_url}/api/v1/bio-savant/chat",
                json={
                    "message": analysis_request.question,
                    "health_context": analysis_request.metrics
                },
                timeout=60
            )
        else:
            # Solo análisis de métricas
            response = await client.post(
                f"{settings.health_service_url}/api/v1/ml-production/predict",
                json={"metrics": analysis_request.metrics},
                timeout=30
            )

        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Health analysis error")

        return response.json()

    except Exception as e:
        log.error(f"Health analysis error: {e}")
        raise HTTPException(status_code=502, detail=f"Error: {str(e)}")


@router.get("/models")
async def list_models(request: Request):
    """Lista todos los modelos disponibles"""
    client: httpx.AsyncClient = request.app.state.http_client

    models: Dict[str, List[Dict[str, Any]]] = {
        "ollama": [],
        "codking": [],
        "onnx": []
    }

    # Ollama models
    try:
        response = await client.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models["ollama"] = [
                {
                    "name": m["name"],
                    "size": m.get("size"),
                    "modified_at": m.get("modified_at")
                }
                for m in data.get("models", [])
            ]
    except Exception as e:
        log.debug(f"Failed to list Ollama models: {e}")

    # CodKing cores
    if settings.codking_enabled:
        models["codking"] = [
            {"name": "core_salud", "params": "9M", "tasks": ["prediction", "analysis"]},
            {"name": "core_educacion", "params": "9M", "tasks": ["summarization", "qa"]},
            {"name": "core_ciberseguridad", "params": "9M", "tasks": ["threat_detection", "anomaly"]}
        ]

    # ONNX models (from biohack-app)
    models["onnx"] = [
        {"name": "energy_model", "type": "regression"},
        {"name": "mood_model", "type": "classification"},
        {"name": "sleep_model", "type": "regression"},
        {"name": "weight_model", "type": "regression"}
    ]

    return models
