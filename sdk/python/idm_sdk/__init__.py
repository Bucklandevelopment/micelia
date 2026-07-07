"""idm-sdk -- Python SDK for integrating microservices with Micelia."""

import warnings

from idm_sdk.client import MiceliaClient
from idm_sdk.config import IdmConfig
from idm_sdk.events import EventBusChannel, EventCategory, create_event


class IdmClient(MiceliaClient):
    """Deprecated alias of :class:`MiceliaClient`. Removible en v0.2.

    Mantiene la firma exacta de ``MiceliaClient`` pero emite
    ``DeprecationWarning`` al instanciarse. Sigue siendo subclass para
    preservar ``isinstance(x, IdmClient)`` y ``isinstance(x, MiceliaClient)``.
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "`IdmClient` está deprecado, usa `MiceliaClient`. "
            "Será removido en v0.2.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


__all__ = [
    "MiceliaClient",
    "IdmClient",
    "IdmConfig",
    "EventCategory",
    "EventBusChannel",
    "create_event",
]
