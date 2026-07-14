"""
API Router para MCP Server Generator de Micelia.

Generación, gestión y ciclo de vida de servidores MCP.
Soporta Python (FastMCP) y TypeScript (@modelcontextprotocol/sdk).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.logging import log
from app.core.security import verify_auth
from app.services.mcp_generator import get_mcp_generator

router = APIRouter(prefix="/mcp", dependencies=[Depends(verify_auth)])


# ==================== REQUEST/RESPONSE MODELS ====================

class ToolParameter(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    default: Optional[str] = None


class ToolDefinition(BaseModel):
    name: str
    description: str = ""
    parameters: List[ToolParameter] = []


class GenerateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9][a-z0-9_-]*$')
    # Optional para honrar el form del panel (MCPGenerateForm en skills/page.tsx):
    # el <input> de descripcion NO es `required` y handleSubmit solo exige name+tools,
    # asi que puede enviar description="". min_length=1 daba 422. Consistente con
    # SkillCreate.description (C60). max_length intacto.
    description: str = Field(default="", max_length=500)
    tools: List[ToolDefinition] = Field(..., min_length=1)
    language: str = Field(default="python", pattern=r'^(python|typescript)$')


class FromPromptRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=5000)
    language: str = Field(default="python", pattern=r'^(python|typescript)$')


# ==================== GENERATION ====================

@router.post("/generate")
async def generate_mcp_server(request: GenerateRequest):
    """
    Genera un servidor MCP completo a partir de una especificacion.

    Crea directorio con server code, config y README.
    Soporta Python (FastMCP) y TypeScript (MCP SDK).
    """
    generator = get_mcp_generator()

    try:
        tools = [t.model_dump() for t in request.tools]
        result = generator.generate(
            name=request.name,
            description=request.description,
            tools=tools,
            language=request.language,
        )
        log.info(f"MCP server generated: {request.name} ({request.language})")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        log.error(f"MCP generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


@router.post("/from-prompt")
async def generate_from_prompt(request: FromPromptRequest):
    """
    Genera un servidor MCP a partir de una descripcion en lenguaje natural.

    Analiza el prompt para extraer nombre, descripcion y herramientas,
    luego genera el servidor completo.
    """
    try:
        # Parse the prompt to extract server specification
        spec = _parse_prompt_to_spec(request.prompt)

        generator = get_mcp_generator()
        result = generator.generate(
            name=spec["name"],
            description=spec["description"],
            tools=spec["tools"],
            language=request.language,
        )

        result["parsed_from_prompt"] = True
        result["parsed_spec"] = spec

        log.info(f"MCP server generated from prompt: {spec['name']}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"MCP from-prompt generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


# ==================== SERVER MANAGEMENT ====================

@router.get("/servers")
async def list_servers():
    """Lista todos los servidores MCP generados."""
    generator = get_mcp_generator()

    try:
        servers = generator.list_servers()
        return {
            "servers": servers,
            "count": len(servers),
        }
    except Exception as e:
        log.error(f"Failed to list MCP servers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_id}")
async def get_server(server_id: str):
    """Obtiene detalle de un servidor MCP incluyendo codigo fuente."""
    generator = get_mcp_generator()

    try:
        server = generator.get_server(server_id)
        return server
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
    except Exception as e:
        log.error(f"Failed to get MCP server {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str):
    """Elimina un servidor MCP y su directorio."""
    generator = get_mcp_generator()

    try:
        generator.delete_server(server_id)
        return {"success": True, "server_id": server_id, "message": f"Server '{server_id}' deleted"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        log.error(f"Failed to delete MCP server {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LIFECYCLE ====================

@router.post("/servers/{server_id}/start")
async def start_server(server_id: str):
    """Inicia un servidor MCP como subproceso."""
    generator = get_mcp_generator()

    try:
        result = generator.start_server(server_id)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        log.error(f"Failed to start MCP server {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_id}/stop")
async def stop_server(server_id: str):
    """Detiene un servidor MCP en ejecucion."""
    generator = get_mcp_generator()

    try:
        result = generator.stop_server(server_id)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        log.error(f"Failed to stop MCP server {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TEMPLATES ====================

@router.get("/templates")
async def list_templates():
    """Lista las plantillas de servidor MCP disponibles."""
    return {
        "templates": [
            {
                "language": "python",
                "framework": "FastMCP",
                "description": "Python MCP server using FastMCP library",
                "requires": ["fastmcp>=2.0.0"],
                "entry_point": "server.py",
                "run_command": "python server.py",
            },
            {
                "language": "typescript",
                "framework": "@modelcontextprotocol/sdk",
                "description": "TypeScript MCP server using official MCP SDK",
                "requires": [
                    "@modelcontextprotocol/sdk@^1.0.0",
                    "zod@^3.22.0",
                ],
                "entry_point": "server.ts",
                "run_command": "npx tsx server.ts",
            },
        ],
        "count": 2,
    }


# ==================== HELPERS ====================

def _parse_prompt_to_spec(prompt: str) -> dict:
    """
    Analiza un prompt en lenguaje natural para extraer especificacion MCP.

    Extrae nombre, descripcion y herramientas del texto.
    Implementacion basica basada en heuristicas; para produccion,
    se usaria un LLM para el parsing.

    Args:
        prompt: Descripcion en lenguaje natural

    Returns:
        dict con name, description, tools
    """
    import re

    # Extract a name from the prompt
    # Try to find "called X" or "named X" patterns
    name_match = re.search(r'(?:called|named|create|build|make)\s+["\']?([a-z][a-z0-9_-]*)["\']?', prompt, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).lower().replace(" ", "-")
    else:
        # Generate name from first few words
        words = re.findall(r'[a-z]+', prompt.lower())[:3]
        name = "-".join(words) if words else "mcp-server"

    # Use prompt as description (truncated)
    description = prompt[:200].strip()

    # Extract tool-like patterns from the prompt
    tools = []
    # Look for bullet points, numbered lists, or "that can X" patterns
    tool_patterns = re.findall(
        r'(?:[-*]\s*|(?:that can|to|which)\s+)([a-z][a-z_ ]+(?:data|files?|info|text|items?|results?|content)?)',
        prompt,
        re.IGNORECASE,
    )

    if tool_patterns:
        for i, pattern in enumerate(tool_patterns[:10]):
            tool_name = re.sub(r'\s+', '_', pattern.strip().lower())
            tool_name = re.sub(r'[^a-z0-9_]', '', tool_name)
            if tool_name and len(tool_name) > 2:
                tools.append({
                    "name": tool_name,
                    "description": f"Tool: {pattern.strip()}",
                    "parameters": [
                        {"name": "input", "type": "string", "description": "Input data"}
                    ],
                })

    # If no tools found, create a default one
    if not tools:
        tools.append({
            "name": "process",
            "description": f"Process request for: {description[:100]}",
            "parameters": [
                {"name": "input", "type": "string", "description": "Input data"}
            ],
        })

    return {
        "name": name,
        "description": description,
        "tools": tools,
    }
