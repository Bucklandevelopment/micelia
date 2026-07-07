"""
API Gateway: Proxy transparente a microservicios.

Rutea requests a:
- /health/* → biohack-app
- /research/* → canela-molida
- /education/* → ideacursi-tool
- /security/* → cybertools
"""

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.config import settings
from app.core.logging import log
from app.core.security import verify_auth

router = APIRouter(prefix="/gateway", dependencies=[Depends(verify_auth)])


# Mapeo de prefijos a servicios
SERVICE_ROUTES = {
    "health": settings.health_service_url,
    "research": settings.research_service_url,
    "education": settings.education_service_url,
    "security": settings.security_service_url,
}


async def proxy_request(
    request: Request,
    service_name: str,
    path: str,
    method: Optional[str] = None
) -> Response:
    """
    Proxea una request a un microservicio.
    """
    client: httpx.AsyncClient = request.app.state.http_client
    service_url = SERVICE_ROUTES.get(service_name)

    if not service_url:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

    # Construir URL destino
    target_url = f"{service_url}{path}"

    # Obtener método HTTP
    http_method = method or request.method

    # Preparar headers (copiar relevantes)
    headers = {}
    for key, value in request.headers.items():
        if key.lower() not in ["host", "content-length"]:
            headers[key] = value

    # Preparar body si existe
    body = None
    if http_method in ["POST", "PUT", "PATCH"]:
        body = await request.body()

    # Preparar query params
    params = dict(request.query_params)

    try:
        log.debug(f"Proxying {http_method} {path} → {target_url}")

        response = await client.request(
            method=http_method,
            url=target_url,
            headers=headers,
            content=body,
            params=params,
            timeout=settings.service_timeout
        )

        # Construir respuesta
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type")
        )

    except httpx.TimeoutException:
        log.error(f"Timeout calling {service_name}: {target_url}")
        raise HTTPException(status_code=504, detail=f"Service '{service_name}' timeout")

    except httpx.ConnectError:
        log.error(f"Connection error to {service_name}: {target_url}")
        raise HTTPException(status_code=503, detail=f"Service '{service_name}' unavailable")

    except Exception as e:
        log.error(f"Error proxying to {service_name}: {e}")
        raise HTTPException(status_code=502, detail=f"Gateway error: {str(e)}")


# ============================================================================
# HEALTH SERVICE (biohack-app)
# ============================================================================

@router.api_route("/health/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_health_service(request: Request, path: str):
    """Proxy a biohack-app (servicio de salud)"""
    return await proxy_request(request, "health", f"/{path}")


# ============================================================================
# RESEARCH SERVICE (canela-molida)
# ============================================================================

@router.api_route("/research/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_research_service(request: Request, path: str):
    """Proxy a canela-molida (servicio de investigación)"""
    return await proxy_request(request, "research", f"/{path}")


# ============================================================================
# EDUCATION SERVICE (ideacursi-tool)
# ============================================================================

@router.api_route("/education/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_education_service(request: Request, path: str):
    """Proxy a ideacursi-tool (servicio de educación)"""
    return await proxy_request(request, "education", f"/{path}")


# ============================================================================
# SECURITY SERVICE (cybertools)
# ============================================================================

@router.api_route("/security/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_security_service(request: Request, path: str):
    """Proxy a cybertools (servicio de seguridad)"""
    return await proxy_request(request, "security", f"/{path}")


# ============================================================================
# KNOWLEDGE PIPELINE (Cross-service)
# ============================================================================

@router.post("/pipeline/research-to-course")
async def research_to_course_pipeline(
    request: Request,
    topic: str,
    max_papers: int = 50,
    target_audience: str = "intermediate",
    num_modules: int = 5
):
    """
    Pipeline completo: Papers → Síntesis → Curso

    1. Busca papers en canela-molida
    2. Genera síntesis con RAG
    3. Crea curso en ideacursi-tool
    """
    client: httpx.AsyncClient = request.app.state.http_client
    event_store = request.app.state.event_store

    try:
        # Paso 1: Buscar papers
        log.info(f"Pipeline: Buscando papers sobre '{topic}'")
        papers_response = await client.get(
            f"{settings.research_service_url}/api/papers/search/openalex",
            params={"query": topic, "per_page": max_papers}
        )
        papers = papers_response.json()

        # Paso 2: Generar síntesis (RAG query)
        log.info(f"Pipeline: Generando síntesis de {len(papers.get('results', []))} papers")
        synthesis_response = await client.post(
            f"{settings.research_service_url}/api/rag/query",
            json={
                "question": f"Summarize the key findings and practical applications about: {topic}",
                "top_k": 20
            }
        )
        synthesis = synthesis_response.json()

        # Paso 3: Crear curso (si ideacursi-tool está disponible)
        if settings.education_service_enabled:
            log.info(f"Pipeline: Generando curso para '{topic}'")
            course_response = await client.post(
                f"{settings.education_service_url}/courses/create",
                json={
                    "title": f"Curso: {topic}",
                    "description": synthesis.get("answer", "")[:500],
                    "target_audience": target_audience,
                    "num_modules": num_modules,
                    "source_synthesis": synthesis
                }
            )
            course = course_response.json()
        else:
            course = None

        # Registrar evento
        if event_store:
            await event_store.append_event(
                category="education",
                subcategory="pipeline",
                source="gateway",
                action="create",
                event_type="education.pipeline.research_to_course",
                payload={
                    "topic": topic,
                    "papers_found": len(papers.get("results", [])),
                    "synthesis_length": len(synthesis.get("answer", "")),
                    "course_created": course is not None
                }
            )

        return {
            "status": "completed",
            "topic": topic,
            "papers_analyzed": len(papers.get("results", [])),
            "synthesis": {
                "answer": synthesis.get("answer"),
                "sources": len(synthesis.get("contexts", []))
            },
            "course": course
        }

    except Exception as e:
        log.error(f"Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")
