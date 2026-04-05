from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

API_KEY_HEADER = "X-API-Key"


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Simple API key middleware.
    If API_KEY is set in settings, requests must include it in the X-API-Key header.
    If API_KEY is empty (default), all requests are permitted.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check and docs
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # If no API key configured, allow all requests (permissive mode)
        if not settings.API_KEY:
            return await call_next(request)

        # Check for API key in header
        provided_key = request.headers.get(API_KEY_HEADER)
        if not provided_key or provided_key != settings.API_KEY:
            logger.warning(
                f"Unauthorized request to {request.url.path} from {request.client.host}"
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
