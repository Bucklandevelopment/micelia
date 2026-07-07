"""
Security module for Micelia.

Provides:
- API Key authentication for critical endpoints
- Rate limiting per IP
- Audit logging to Event Store
- Input sanitization for AppleScript injection prevention
"""

import hashlib
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.core.logging import log

# =============================================================================
# API KEY AUTHENTICATION
# =============================================================================

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyManager:
    """
    Manages API keys for secure endpoints.

    In production, keys should be stored in a database or secrets manager.
    For now, we use environment variable and in-memory storage.
    """

    def __init__(self):
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._load_default_keys()

    def _load_default_keys(self):
        """Load default API keys from environment"""
        # Master key from settings
        master_key = getattr(settings, 'system_api_key', None)
        if master_key and master_key != "change-me-in-production":
            self._keys[self._hash_key(master_key)] = {
                "name": "master",
                "permissions": {"all"},
                "created": datetime.now(timezone.utc),
                "rate_limit": 1000  # Higher limit for master key
            }

        # Read-only key from settings
        readonly_key = getattr(settings, 'system_api_key_readonly', None)
        if readonly_key:
            self._keys[self._hash_key(readonly_key)] = {
                "name": "readonly",
                "permissions": {"read"},
                "created": datetime.now(timezone.utc),
                "rate_limit": 100
            }

    def _hash_key(self, key: str) -> str:
        """Hash API key for secure storage"""
        return hashlib.sha256(key.encode()).hexdigest()

    def validate_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return its metadata"""
        if not key:
            return None
        hashed = self._hash_key(key)
        return self._keys.get(hashed)

    def has_permission(self, key: str, permission: str) -> bool:
        """Check if key has specific permission"""
        key_data = self.validate_key(key)
        if not key_data:
            return False
        permissions = key_data.get("permissions", set())
        return "all" in permissions or permission in permissions

    def generate_key(self, name: str, permissions: Set[str], rate_limit: int = 100) -> str:
        """Generate a new API key"""
        key = secrets.token_urlsafe(32)
        self._keys[self._hash_key(key)] = {
            "name": name,
            "permissions": permissions,
            "created": datetime.now(timezone.utc),
            "rate_limit": rate_limit
        }
        return key


api_key_manager = APIKeyManager()


# =============================================================================
# RATE LIMITING
# =============================================================================

class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    For production, use Redis-based rate limiting.
    """

    def __init__(self, default_limit: int = 60, window_seconds: int = 60):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)

    def _cleanup_old_requests(self, key: str, now: float):
        """Remove requests outside the current window"""
        cutoff = now - self.window_seconds
        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]

    def is_allowed(self, key: str, limit: Optional[int] = None) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed under rate limit.

        Returns:
            (allowed, info) where info contains remaining, reset_at
        """
        limit = limit or self.default_limit
        now = time.time()

        self._cleanup_old_requests(key, now)

        current_count = len(self._requests[key])
        remaining = max(0, limit - current_count - 1)
        reset_at = int(now + self.window_seconds)

        info = {
            "limit": limit,
            "remaining": remaining,
            "reset_at": reset_at
        }

        if current_count >= limit:
            return False, info

        self._requests[key].append(now)
        return True, info

    def get_limit_for_key(self, api_key: Optional[str]) -> int:
        """Get rate limit based on API key tier"""
        if api_key:
            key_data = api_key_manager.validate_key(api_key)
            if key_data:
                return key_data.get("rate_limit", self.default_limit)
        return self.default_limit


rate_limiter = RateLimiter(
    default_limit=getattr(settings, 'osascript_rate_limit', 30),
    window_seconds=60
)


# =============================================================================
# INPUT SANITIZATION
# =============================================================================

class AppleScriptSanitizer:
    """
    Sanitizes input to prevent AppleScript injection attacks.

    AppleScript injection can allow arbitrary code execution on the system.
    """

    # Dangerous patterns that could be used for injection
    DANGEROUS_PATTERNS = [
        r'do shell script',
        r'run script',
        r'tell application "Terminal"',
        r'tell application "iTerm"',
        r'System Events.*keystroke',
        r'System Events.*key code',
        r'sudo',
        r'/bin/sh',
        r'/bin/bash',
        r'/usr/bin/osascript',
        r'with administrator privileges',
        r'using.*password',
    ]

    # Characters that need escaping in AppleScript strings
    ESCAPE_CHARS = {
        '"': '\\"',
        '\\': '\\\\',
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
    }

    # Maximum lengths for different input types
    MAX_LENGTHS = {
        "title": 200,
        "message": 1000,
        "text": 5000,
        "url": 2048,
        "path": 1024,
        "name": 200,
        "body": 10000,
        "query": 100,
        "default": 500
    }

    def __init__(self):
        self._dangerous_regex = re.compile(
            '|'.join(self.DANGEROUS_PATTERNS),
            re.IGNORECASE
        )

    def sanitize_string(self, value: str, field_type: str = "default") -> str:
        """
        Sanitize a string value for safe AppleScript use.

        Args:
            value: Input string to sanitize
            field_type: Type of field (for length limits)

        Returns:
            Sanitized string

        Raises:
            ValueError: If input contains dangerous patterns
        """
        if not value:
            return ""

        # Check length
        max_len = self.MAX_LENGTHS.get(field_type, self.MAX_LENGTHS["default"])
        if len(value) > max_len:
            value = value[:max_len]

        # Check for dangerous patterns
        if self._dangerous_regex.search(value):
            log.warning(f"Dangerous pattern detected in input: {value[:50]}...")
            raise ValueError("Input contains potentially dangerous patterns")

        # Escape special characters
        for char, escaped in self.ESCAPE_CHARS.items():
            value = value.replace(char, escaped)

        # Remove null bytes and other control characters
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)

        return value

    def validate_url(self, url: str) -> str:
        """Validate and sanitize URL"""
        # Basic URL validation
        if not url:
            raise ValueError("URL cannot be empty")

        url = self.sanitize_string(url, "url")

        # Only allow http/https URLs
        if not re.match(r'^https?://', url, re.IGNORECASE):
            raise ValueError("Only HTTP/HTTPS URLs are allowed")

        # Block dangerous URL patterns
        dangerous_url_patterns = [
            r'javascript:',
            r'data:',
            r'file://',
            r'localhost',
            r'127\.0\.0\.1',
            r'0\.0\.0\.0',
            r'::1',
        ]
        for pattern in dangerous_url_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                # Allow localhost for development
                if not settings.debug and pattern in ['localhost', r'127\.0\.0\.1']:
                    raise ValueError(f"Blocked URL pattern: {pattern}")

        return url

    def validate_path(self, path: str) -> str:
        """Validate and sanitize file path"""
        if not path:
            raise ValueError("Path cannot be empty")

        path = self.sanitize_string(path, "path")

        # Block path traversal attempts
        if '..' in path:
            raise ValueError("Path traversal not allowed")

        # Only allow paths within allowed directories
        allowed_prefixes = getattr(settings, 'osascript_allowed_paths', [
            '/Users/',
            '/tmp/',
            '/var/folders/',
        ])

        if not any(path.startswith(prefix) for prefix in allowed_prefixes):
            raise ValueError("Path not in allowed directories")

        return path

    def is_safe(self, value: str) -> bool:
        """Check if value is safe without raising exception"""
        try:
            self.sanitize_string(value)
            return True
        except ValueError:
            return False


sanitizer = AppleScriptSanitizer()


# =============================================================================
# AUDIT LOGGING
# =============================================================================

class AuditLogger:
    """
    Logs security-relevant events to Event Store and file.
    """

    def __init__(self):
        self._buffer: list = []
        self._buffer_size = 10

    async def log_operation(
        self,
        operation: str,
        request: Request,
        api_key: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log an OSASCRIPT operation for audit.

        Args:
            operation: Name of the operation (e.g., "send_notification")
            request: FastAPI request object
            api_key: API key used (if any)
            success: Whether operation succeeded
            details: Additional details
        """
        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Mask API key for logging
        masked_key = None
        if api_key:
            masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"

        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "client_ip": client_ip,
            "user_agent": user_agent[:100],
            "api_key": masked_key,
            "success": success,
            "details": details or {},
            "path": str(request.url.path),
            "method": request.method
        }

        # Log immediately for critical operations
        log.info(f"AUDIT: {operation} from {client_ip} - {'OK' if success else 'FAILED'}")

        # Try to store in Event Store
        try:
            event_store = getattr(request.app.state, 'event_store', None)
            if event_store:
                await event_store.append_event(
                    category="security",
                    source="osascript",
                    action="audit",
                    event_type=f"osascript.{operation}",
                    payload=audit_entry,
                    event_metadata={
                        "ip": client_ip,
                        "success": success
                    }
                )
        except Exception as e:
            log.error(f"Failed to store audit event: {e}")

    async def log_security_event(
        self,
        event_type: str,
        request: Request,
        details: Dict[str, Any]
    ):
        """Log security-related events (rate limit, auth failure, etc.)"""
        client_ip = request.client.host if request.client else "unknown"

        log.warning(f"SECURITY: {event_type} from {client_ip} - {details}")

        try:
            event_store = getattr(request.app.state, 'event_store', None)
            if event_store:
                await event_store.append_event(
                    category="security",
                    source="osascript",
                    action="alert",
                    event_type=f"security.{event_type}",
                    payload={
                        "client_ip": client_ip,
                        **details
                    }
                )
        except Exception:
            pass


audit_logger = AuditLogger()


# =============================================================================
# JWT AUTHENTICATION (for browser/dashboard access)
# =============================================================================

from datetime import timedelta  # noqa: E402

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # noqa: E402
from jose import JWTError  # noqa: E402
from jose import jwt as jose_jwt  # noqa: E402
from passlib.context import CryptContext  # noqa: E402

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
BEARER_SCHEME = HTTPBearer(auto_error=False)


class JWTAuthManager:
    """Single-user JWT authentication for dashboard access."""

    def __init__(self):
        self._secret = settings.jwt_secret_key
        self._algorithm = settings.jwt_algorithm
        self._access_expire = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        self._refresh_expire = timedelta(days=settings.jwt_refresh_token_expire_days)

    def verify_password(self, plain_password: str) -> bool:
        stored_hash = settings.auth_password_hash
        if not stored_hash:
            return False
        return pwd_context.verify(plain_password, stored_hash)

    @staticmethod
    def hash_password(plain_password: str) -> str:
        return pwd_context.hash(plain_password)

    def create_access_token(self, subject: str = "admin") -> str:
        expire = datetime.now(timezone.utc) + self._access_expire
        payload = {"sub": subject, "exp": expire, "type": "access"}
        return jose_jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, subject: str = "admin") -> str:
        expire = datetime.now(timezone.utc) + self._refresh_expire
        payload = {"sub": subject, "exp": expire, "type": "refresh"}
        return jose_jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict:
        return jose_jwt.decode(token, self._secret, algorithms=[self._algorithm])


jwt_auth = JWTAuthManager()


# =============================================================================
# UNIFIED AUTH: API Key OR JWT Bearer (backward compatible)
# =============================================================================

async def verify_auth(
    request: Request,
    api_key: Optional[str] = Security(API_KEY_HEADER),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(BEARER_SCHEME),
) -> str:
    """
    Unified auth dependency. Accepts either X-API-Key header or Bearer JWT.
    API keys take precedence for backward compatibility with satellite services.
    """
    # Try API key first
    if api_key:
        key_info = api_key_manager.validate_key(api_key)
        if key_info:
            return f"apikey:{key_info.get('name', 'unknown')}"
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Try JWT Bearer token
    if bearer and bearer.credentials:
        try:
            payload = jwt_auth.decode_token(bearer.credentials)
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Invalid token type")
            return f"jwt:{payload.get('sub', 'admin')}"
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide X-API-Key header or Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# =============================================================================
# FASTAPI DEPENDENCIES
# =============================================================================

async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Security(API_KEY_HEADER)
) -> Optional[str]:
    """
    Verify API key for protected endpoints.

    If OSASCRIPT_REQUIRE_AUTH is True, API key is required.
    Otherwise, it's optional but provides higher rate limits.
    """
    require_auth = getattr(settings, 'osascript_require_auth', True)

    if require_auth:
        if not api_key:
            await audit_logger.log_security_event(
                "auth_missing",
                request,
                {"reason": "API key required but not provided"}
            )
            raise HTTPException(
                status_code=401,
                detail="API key required. Provide X-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"}
            )

        if not api_key_manager.validate_key(api_key):
            await audit_logger.log_security_event(
                "auth_invalid",
                request,
                {"reason": "Invalid API key"}
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "ApiKey"}
            )

    return api_key


async def check_rate_limit(
    request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """
    Check rate limit for the request.

    Rate limits are:
    - Unauthenticated: 30 req/min
    - Authenticated: Based on API key tier
    """
    # Get client identifier
    client_ip = request.client.host if request.client else "unknown"
    limit_key = f"osascript:{client_ip}"

    # Get limit based on API key
    limit = rate_limiter.get_limit_for_key(api_key)

    allowed, info = rate_limiter.is_allowed(limit_key, limit)

    # Add rate limit headers to response
    request.state.rate_limit_info = info

    if not allowed:
        await audit_logger.log_security_event(
            "rate_limit_exceeded",
            request,
            {"limit": info["limit"], "reset_at": info["reset_at"]}
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please slow down.",
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info["reset_at"]),
                "Retry-After": str(info["reset_at"] - int(time.time()))
            }
        )


async def require_write_permission(
    request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """
    Require write permission for modifying operations.

    Operations like creating events, reminders, notes require write permission.
    """
    # If auth is required, check write permission
    require_auth = getattr(settings, 'osascript_require_auth', True)

    if require_auth and api_key:
        if not api_key_manager.has_permission(api_key, "write"):
            if not api_key_manager.has_permission(api_key, "all"):
                await audit_logger.log_security_event(
                    "permission_denied",
                    request,
                    {"required": "write", "operation": request.url.path}
                )
                raise HTTPException(
                    status_code=403,
                    detail="Write permission required for this operation"
                )


def osascript_security(write: bool = False):
    """
    Combined security dependency for OSASCRIPT endpoints.

    Args:
        write: If True, require write permission

    Usage:
        @router.post("/endpoint")
        async def endpoint(
            request: Request,
            _security = Depends(osascript_security(write=True))
        ):
            ...
    """
    async def _security(
        request: Request,
        api_key: Optional[str] = Depends(verify_api_key)
    ):
        # Check rate limit
        await check_rate_limit(request, api_key)

        # Check write permission if needed
        if write:
            await require_write_permission(request, api_key)

        return api_key

    return _security


# =============================================================================
# GLOBAL API KEY AUTH (for all endpoints beyond OSASCRIPT)
# =============================================================================

async def verify_api_key_global(
    request: Request,
    api_key: Optional[str] = Security(API_KEY_HEADER)
) -> Optional[str]:
    """
    Global API key verification for all protected endpoints.

    Validates the X-API-Key header against configured keys.
    Used as a router-level dependency for non-OSASCRIPT endpoints.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    if not api_key_manager.validate_key(api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    return api_key


# =============================================================================
# SECURITY MIDDLEWARE HELPERS
# =============================================================================

def add_security_headers(response):
    """Add security headers to response"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


class OSAScriptSecurityContext:
    """
    Context for OSASCRIPT operations with security features.

    Usage:
        async with OSAScriptSecurityContext(request) as ctx:
            if ctx.is_allowed("send_notification"):
                ...
    """

    # Operations classified by risk level
    READ_OPERATIONS = {
        "get_system_info",
        "get_frontmost_app",
        "get_running_apps",
        "get_volume",
        "is_dark_mode",
        "get_calendars",
        "get_today_events",
        "get_reminder_lists",
        "get_reminders",
        "get_note_folders",
        "get_notes",
        "get_safari_tabs",
        "get_current_safari_url",
        "search_contacts",
        "get_selected_files",
        "get_clipboard",
        "get_current_track",
    }

    WRITE_OPERATIONS = {
        "send_notification",
        "say_text",
        "set_volume",
        "toggle_dark_mode",
        "create_calendar_event",
        "create_reminder",
        "complete_reminder",
        "create_note",
        "open_url_in_safari",
        "reveal_in_finder",
        "set_clipboard",
        "music_play_pause",
    }

    # High-risk operations that might be disabled
    HIGH_RISK_OPERATIONS = {
        "toggle_dark_mode",
        "set_volume",
        "open_url_in_safari",
        "reveal_in_finder",
        "set_clipboard",
    }

    def __init__(self, request: Request, api_key: Optional[str] = None):
        self.request = request
        self.api_key = api_key
        self._disabled_ops = set(getattr(settings, 'osascript_disabled_operations', []))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def is_allowed(self, operation: str) -> bool:
        """Check if operation is allowed"""
        # Check if globally disabled
        if operation in self._disabled_ops:
            return False

        # Check high-risk operations in production
        if settings.is_production and operation in self.HIGH_RISK_OPERATIONS:
            allow_high_risk = getattr(settings, 'osascript_allow_high_risk', False)
            if not allow_high_risk:
                return False

        return True

    def is_write_operation(self, operation: str) -> bool:
        """Check if operation modifies state"""
        return operation in self.WRITE_OPERATIONS
