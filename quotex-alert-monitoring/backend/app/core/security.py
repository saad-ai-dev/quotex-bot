"""
Simple optional API key middleware.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Paths that never require authentication
_PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates an optional API key passed via the ``X-API-Key`` header.

    When ``settings.API_KEY`` is ``None`` or empty the middleware is a
    pass-through and every request is allowed.  When a key is configured,
    all requests outside ``_PUBLIC_PATHS`` must supply a matching header.

    ALERT-ONLY: This protects the monitoring dashboard API.
    No trade-related endpoints exist.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        api_key = settings.API_KEY

        # No key configured -> allow everything
        if not api_key:
            return await call_next(request)

        # Public paths bypass auth
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Allow WebSocket upgrade without header (token checked on connect)
        if request.url.path.startswith("/ws"):
            return await call_next(request)

        # Allow static files
        if request.url.path.startswith("/static"):
            return await call_next(request)

        supplied_key = request.headers.get("X-API-Key")
        if supplied_key != api_key:
            logger.warning(
                "Rejected request to %s - invalid or missing API key",
                request.url.path,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API key",
            )

        return await call_next(request)
