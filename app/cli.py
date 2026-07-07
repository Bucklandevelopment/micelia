"""
CLI de administración de Micelia.

Uso:
    idm status              # Ver estado del sistema
    idm services            # Ver estado de servicios
    idm start               # Iniciar el gateway
    idm events              # Ver últimos eventos
    idm ai status           # Estado de IA
    idm energy              # Estado de energía
"""

import asyncio
import sys
from functools import wraps
from typing import Any

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def async_command(f):
    """Decorator para comandos async"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.version_option(version="0.1.0", prog_name="micelia")
def main():
    """
    Micelia: CLI del orquestador

    Orquestador central que integra salud, educación, investigación y seguridad.
    """
    pass


@main.command()
@click.option('--host', default='localhost', help='Host del gateway')
@click.option('--port', default=8888, help='Puerto del gateway')
@async_command
async def status(host: str, port: int):
    """Ver estado general del sistema"""
    base_url = f"http://{host}:{port}"

    console.print(Panel.fit(
        "[bold blue]Micelia[/bold blue] — Orquestador",
        border_style="blue"
    ))

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Health check
            health_resp = await client.get(f"{base_url}/api/v1/health/detailed")

            if health_resp.status_code == 200:
                data = health_resp.json()

                # Estado general
                status_color = {
                    "healthy": "green",
                    "degraded": "yellow",
                    "unhealthy": "red"
                }.get(data["status"], "white")

                console.print(f"\n[bold]Estado:[/bold] [{status_color}]{data['status'].upper()}[/{status_color}]")
                console.print(f"[bold]Uptime:[/bold] {data['uptime_seconds']:.0f}s")

                # Tabla de servicios
                table = Table(title="Servicios")
                table.add_column("Servicio", style="cyan")
                table.add_column("Estado", justify="center")
                table.add_column("Latencia", justify="right")
                table.add_column("URL")

                for name, service in data["services"].items():
                    status_icon = "✅" if service["healthy"] else "❌"
                    latency = f"{service['latency_ms']:.0f}ms" if service["latency_ms"] else "-"
                    table.add_row(
                        name,
                        status_icon,
                        latency,
                        service["url"]
                    )

                console.print(table)

                # Recursos
                resources = data["resources"]
                console.print("\n[bold]Recursos:[/bold]")
                console.print(f"  CPU: {resources['cpu_percent']}%")
                console.print(f"  RAM: {resources['memory']['available_gb']:.1f}GB disponible ({resources['memory']['percent']}% usado)")
                console.print(f"  Disco: {resources['disk']['free_gb']:.1f}GB libre ({resources['disk']['percent']}% usado)")

            else:
                console.print(f"[red]Error: {health_resp.status_code}[/red]")

    except httpx.ConnectError:
        console.print(f"[red]Error: No se puede conectar a {base_url}[/red]")
        console.print("Asegúrate de que Micelia está ejecutándose.")
        sys.exit(1)


@main.command()
@click.option('--host', default='localhost', help='Host del gateway')
@click.option('--port', default=8888, help='Puerto del gateway')
@async_command
async def services(host: str, port: int):
    """Ver estado detallado de servicios"""
    base_url = f"http://{host}:{port}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/api/v1/health/services")

            if resp.status_code == 200:
                data = resp.json()

                table = Table(title="Estado de Microservicios")
                table.add_column("Servicio", style="cyan", width=15)
                table.add_column("Habilitado", justify="center", width=10)
                table.add_column("Saludable", justify="center", width=10)
                table.add_column("Latencia", justify="right", width=10)
                table.add_column("URL", width=35)
                table.add_column("Error", style="red", width=20)

                for name, service in data["services"].items():
                    enabled = "✅" if service["enabled"] else "❌"
                    healthy = "✅" if service["healthy"] else "❌"
                    latency = f"{service['latency_ms']:.0f}ms" if service["latency_ms"] else "-"
                    error = service.get("error", "-") or "-"

                    table.add_row(
                        name,
                        enabled,
                        healthy,
                        latency,
                        service["url"],
                        error[:20] if len(error) > 20 else error
                    )

                console.print(table)

    except httpx.ConnectError:
        console.print(f"[red]Error: No se puede conectar a {base_url}[/red]")
        sys.exit(1)


@main.command()
@click.option('--host', default='0.0.0.0', help='Host a escuchar')
@click.option('--port', default=8888, help='Puerto')
@click.option('--reload', is_flag=True, help='Hot reload')
@click.option(
    '--log-level',
    type=click.Choice(['critical', 'error', 'warning', 'info', 'debug', 'trace'], case_sensitive=False),
    default='info',
    help='Nivel de log de uvicorn (default: info)',
)
@click.option(
    '--access-log/--no-access-log',
    default=True,
    help='Mostrar log de cada request HTTP (default: activado)',
)
def start(host: str, port: int, reload: bool, log_level: str, access_log: bool):
    """Iniciar el gateway de Micelia"""
    import uvicorn

    console.print(Panel.fit(
        "[bold blue]Iniciando Micelia[/bold blue]",
        border_style="blue"
    ))

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
        access_log=access_log,
    )


@main.command()
@click.option('--host', default='localhost', help='Host del gateway')
@click.option('--port', default=8888, help='Puerto del gateway')
@click.option('--limit', default=20, help='Número de eventos')
@click.option('--category', default=None, help='Filtrar por categoría')
@async_command
async def events(host: str, port: int, limit: int, category: str):
    """Ver últimos eventos del sistema"""
    base_url = f"http://{host}:{port}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            params: dict[str, Any] = {"limit": limit}
            if category:
                params["category"] = category

            resp = await client.get(f"{base_url}/api/v1/events", params=params)

            if resp.status_code == 200:
                data = resp.json()

                table = Table(title=f"Últimos {len(data['events'])} eventos")
                table.add_column("Tiempo", style="dim", width=20)
                table.add_column("Categoría", style="cyan", width=12)
                table.add_column("Tipo", width=30)
                table.add_column("Fuente", width=12)

                for event in data["events"]:
                    timestamp = event.get("timestamp", "")[:19].replace("T", " ")
                    table.add_row(
                        timestamp,
                        event.get("category", "-"),
                        event.get("event_type", "-"),
                        event.get("source", "-")
                    )

                console.print(table)
                console.print(f"\nTotal: {data['count']} eventos")

            elif resp.status_code == 503:
                console.print("[yellow]Event Store no disponible[/yellow]")
            else:
                console.print(f"[red]Error: {resp.status_code}[/red]")

    except httpx.ConnectError:
        console.print(f"[red]Error: No se puede conectar a {base_url}[/red]")
        sys.exit(1)


@main.group()
def ai():
    """Comandos de IA"""
    pass


@ai.command(name="status")
@click.option('--host', default='localhost', help='Host del gateway')
@click.option('--port', default=8888, help='Puerto del gateway')
@async_command
async def ai_status(host: str, port: int):
    """Ver estado de servicios de IA"""
    base_url = f"http://{host}:{port}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/api/v1/ai/status")

            if resp.status_code == 200:
                data = resp.json()

                # Ollama
                console.print("\n[bold]Ollama:[/bold]")
                if data["ollama"]["available"]:
                    console.print("  Estado: [green]Disponible[/green]")
                    console.print(f"  Modelos: {', '.join(data['ollama']['models'][:5])}")
                else:
                    console.print("  Estado: [red]No disponible[/red]")

                # CodKing
                console.print("\n[bold]CodKing:[/bold]")
                if data["codking"]["available"]:
                    console.print("  Estado: [green]Habilitado[/green]")
                    console.print(f"  Cores: {', '.join(data['codking']['cores'])}")
                else:
                    console.print("  Estado: [yellow]Deshabilitado[/yellow]")

                # Compute Router
                console.print("\n[bold]Compute Router:[/bold]")
                console.print(f"  Habilitado: {'✅' if data['compute_router']['enabled'] else '❌'}")

    except httpx.ConnectError:
        console.print(f"[red]Error: No se puede conectar a {base_url}[/red]")
        sys.exit(1)


@main.command()
@click.option('--host', default='localhost', help='Host del gateway')
@click.option('--port', default=8888, help='Puerto del gateway')
@async_command
async def energy(host: str, port: int):
    """Ver estado de energía del sistema"""
    base_url = f"http://{host}:{port}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/api/v1/energy/status")

            if resp.status_code == 200:
                data = resp.json()

                # Estado
                state_colors = {
                    "abundant": "green",
                    "normal": "blue",
                    "conserving": "yellow",
                    "critical": "red",
                    "survival": "magenta"
                }
                state_color = state_colors.get(data["state"], "white")

                console.print(Panel.fit(
                    f"[bold {state_color}]{data['state'].upper()}[/bold {state_color}]",
                    title="Estado de Energía",
                    border_style=state_color
                ))

                # Detalles
                console.print(f"\n[bold]Batería:[/bold] {data['battery_level']}%")
                console.print(f"[bold]Cargando:[/bold] {'Sí' if data['is_charging'] else 'No'}")
                console.print(f"[bold]Fuente:[/bold] {data['power_source']}")

                if data["time_remaining_minutes"] > 0:
                    hours = data["time_remaining_minutes"] // 60
                    mins = data["time_remaining_minutes"] % 60
                    console.print(f"[bold]Tiempo restante:[/bold] {hours}h {mins}m")

                if data["solar_available"]:
                    console.print(f"[bold]Solar:[/bold] {data['solar_watts']}W")

                console.print(f"[bold]Online:[/bold] {'Sí' if data['is_online'] else 'No'}")

                # Recomendaciones
                if data["recommendations"]:
                    console.print("\n[bold]Recomendaciones:[/bold]")
                    for rec in data["recommendations"]:
                        console.print(f"  • {rec}")

    except httpx.ConnectError:
        console.print(f"[red]Error: No se puede conectar a {base_url}[/red]")
        sys.exit(1)


@main.command()
@click.option('--host', default='localhost', help='Host del gateway')
@click.option('--port', default=8888, help='Puerto del gateway')
@click.argument('topic')
@click.option('--papers', default=30, help='Número de papers a analizar')
@async_command
async def create_course(host: str, port: int, topic: str, papers: int):
    """Crear curso desde investigación (pipeline completo)"""
    base_url = f"http://{host}:{port}"

    console.print(f"\n[bold]Creando curso sobre:[/bold] {topic}")
    console.print(f"[bold]Papers a analizar:[/bold] {papers}")
    console.print("\nEsto puede tomar varios minutos...\n")

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{base_url}/api/v1/gateway/pipeline/research-to-course",
                params={
                    "topic": topic,
                    "max_papers": papers,
                    "num_modules": 5
                }
            )

            if resp.status_code == 200:
                data = resp.json()

                console.print("[green]✅ Curso creado exitosamente[/green]\n")
                console.print(f"[bold]Papers analizados:[/bold] {data.get('papers_analyzed', 0)}")
                console.print(f"[bold]Fuentes en síntesis:[/bold] {data.get('synthesis', {}).get('sources', 0)}")

                if data.get("course"):
                    console.print(f"\n[bold]Curso:[/bold] {data['course'].get('title', topic)}")
            else:
                console.print(f"[red]Error: {resp.status_code}[/red]")
                console.print(resp.text)

    except httpx.TimeoutException:
        console.print("[red]Timeout: El pipeline tardó demasiado[/red]")
    except httpx.ConnectError:
        console.print(f"[red]Error: No se puede conectar a {base_url}[/red]")
        sys.exit(1)


def _main_deprecated():
    """Entrypoint deprecado del CLI `idm`. Usa `micelia` en su lugar."""
    import warnings
    warnings.warn(
        "El CLI `idm` está deprecado, usa `micelia`. Será removido en v0.2.",
        DeprecationWarning,
        stacklevel=2,
    )
    main()


if __name__ == "__main__":
    main()
