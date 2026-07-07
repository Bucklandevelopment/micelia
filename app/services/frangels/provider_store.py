"""
Provider Store - Almacenamiento seguro de credenciales de proveedores
"""

import base64
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings
from app.core.logging import log


@dataclass
class ProviderCredential:
    """Credencial de un proveedor"""
    provider_id: str
    api_key: str
    extra_key: Optional[str] = None
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
    last_used: Optional[str] = None

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now


class ProviderStore:
    """
    Almacena credenciales de proveedores de forma segura.
    Las credenciales se encriptan antes de guardar en disco.
    """

    def __init__(self, storage_path: str = "./data/frangels"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.credentials_file = self.storage_path / "providers.enc"
        self._credentials: Dict[str, ProviderCredential] = {}
        self._fernet = self._init_encryption()
        self._load()

    def _init_encryption(self) -> Fernet:
        """Inicializa encriptación usando la secret_key del sistema"""
        # Derivar clave de encriptación desde secret_key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'frangels_salt_v1',  # Salt fijo para reproducibilidad
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
        return Fernet(key)

    def _load(self):
        """Carga credenciales desde disco"""
        if not self.credentials_file.exists():
            self._credentials = {}
            return

        try:
            encrypted_data = self.credentials_file.read_bytes()
            decrypted_data = self._fernet.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode())

            self._credentials = {
                k: ProviderCredential(**v) for k, v in data.items()
            }
            log.info(f"Loaded {len(self._credentials)} provider credentials")
        except Exception as e:
            log.error(f"Failed to load provider credentials: {e}")
            self._credentials = {}

    def _save(self):
        """Guarda credenciales a disco (encriptadas)"""
        try:
            data = {k: asdict(v) for k, v in self._credentials.items()}
            json_data = json.dumps(data).encode()
            encrypted_data = self._fernet.encrypt(json_data)
            self.credentials_file.write_bytes(encrypted_data)
            log.debug(f"Saved {len(self._credentials)} provider credentials")
        except Exception as e:
            log.error(f"Failed to save provider credentials: {e}")

    def get(self, provider_id: str) -> Optional[ProviderCredential]:
        """Obtiene credencial de un proveedor"""
        return self._credentials.get(provider_id)

    def get_api_key(self, provider_id: str) -> Optional[str]:
        """Obtiene solo la API key de un proveedor"""
        cred = self._credentials.get(provider_id)
        if cred and cred.enabled:
            return cred.api_key
        return None

    def set(self, provider_id: str, api_key: str,
            extra_key: Optional[str] = None, enabled: bool = True):
        """Guarda o actualiza credencial de un proveedor"""
        existing = self._credentials.get(provider_id)

        if existing:
            existing.api_key = api_key
            existing.extra_key = extra_key
            existing.enabled = enabled
            existing.updated_at = datetime.now(timezone.utc).isoformat()
        else:
            self._credentials[provider_id] = ProviderCredential(
                provider_id=provider_id,
                api_key=api_key,
                extra_key=extra_key,
                enabled=enabled
            )

        self._save()
        log.info(f"Updated credentials for provider: {provider_id}")

    def delete(self, provider_id: str):
        """Elimina credencial de un proveedor"""
        if provider_id in self._credentials:
            del self._credentials[provider_id]
            self._save()
            log.info(f"Deleted credentials for provider: {provider_id}")

    def enable(self, provider_id: str):
        """Habilita un proveedor"""
        if provider_id in self._credentials:
            self._credentials[provider_id].enabled = True
            self._save()

    def disable(self, provider_id: str):
        """Deshabilita un proveedor"""
        if provider_id in self._credentials:
            self._credentials[provider_id].enabled = False
            self._save()

    def mark_used(self, provider_id: str):
        """Marca un proveedor como usado"""
        if provider_id in self._credentials:
            self._credentials[provider_id].last_used = datetime.now(timezone.utc).isoformat()
            self._save()

    def list_configured(self) -> Dict[str, bool]:
        """Lista proveedores configurados y su estado"""
        return {
            k: v.enabled for k, v in self._credentials.items()
        }

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene estado de todos los proveedores configurados"""
        return {
            k: {
                "configured": True,
                "enabled": v.enabled,
                "created_at": v.created_at,
                "updated_at": v.updated_at,
                "last_used": v.last_used,
                "has_extra_key": v.extra_key is not None
            }
            for k, v in self._credentials.items()
        }

    def export_to_env(self) -> Dict[str, str]:
        """
        Exporta credenciales como variables de entorno.
        Útil para integraciones que requieren env vars.
        """
        from .angels import ANGEL_REGISTRY

        env_vars = {}
        for provider_id, cred in self._credentials.items():
            if not cred.enabled:
                continue

            angel = ANGEL_REGISTRY.get(provider_id)
            if angel:
                env_vars[angel.env_key] = cred.api_key
                if cred.extra_key and angel.env_key_extra:
                    env_vars[angel.env_key_extra] = cred.extra_key

        return env_vars

    def sync_from_env(self):
        """
        Sincroniza credenciales desde variables de entorno.
        Útil para migración desde .env existente.
        """
        from .angels import ANGEL_REGISTRY

        for provider_id, angel in ANGEL_REGISTRY.items():
            api_key = os.getenv(angel.env_key)
            extra_key = os.getenv(angel.env_key_extra) if angel.env_key_extra else None

            if api_key and provider_id not in self._credentials:
                self.set(provider_id, api_key, extra_key)
                log.info(f"Synced {provider_id} from environment")


# Singleton global
_provider_store: Optional[ProviderStore] = None


def get_provider_store() -> ProviderStore:
    """Obtiene la instancia singleton del provider store"""
    global _provider_store
    if _provider_store is None:
        _provider_store = ProviderStore()
    return _provider_store
