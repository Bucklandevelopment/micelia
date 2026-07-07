"""
micelia-sdk: Lightweight SDK for microservice integration with Micelia.

Usage:
    from app.sdk import IdmServiceClient

    client = IdmServiceClient(
        service_name="biohack-app",
        port=8080,
        category="health",
        micelia_url="http://localhost:8888",
        api_key="your-api-key",
    )

    # Register with Micelia and start heartbeat
    await client.start()

    # Publish events
    await client.publish_event(
        category="health",
        action="create",
        event_type="biomarker.recorded",
        payload={"heart_rate": 72},
    )

    # Generate standardized health response
    health = client.health_response(dependencies={"postgresql": "healthy"})

    # Shutdown
    await client.stop()
"""

from app.sdk.client import IdmServiceClient
from app.sdk.models import HealthResponse, IdmEvent

MiceliaServiceClient = IdmServiceClient  # canonical alias for v0.1+

__all__ = [
    "MiceliaServiceClient",
    "IdmServiceClient",
    "HealthResponse",
    "IdmEvent",
]
