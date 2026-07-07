"""
Frangels: Free Angels - Cloud Helpers Computation Services

Sistema de orquestación de servicios cloud gratuitos que complementa
el cómputo local del Panel IDM. Aprovecha ~$650/mes en free tiers.
"""

from .angels import ANGEL_REGISTRY, Angel, AngelCategory, AngelTier, PrivacyLevel
from .orchestrator import FrangelsOrchestrator
from .provider_store import ProviderStore
from .quota_manager import QuotaManager

__all__ = [
    'Angel',
    'AngelCategory',
    'AngelTier',
    'PrivacyLevel',
    'ANGEL_REGISTRY',
    'FrangelsOrchestrator',
    'QuotaManager',
    'ProviderStore'
]
