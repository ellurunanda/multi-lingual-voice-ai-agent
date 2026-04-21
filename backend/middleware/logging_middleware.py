"""
Request/response logging middleware with latency tracking.
Logs method, path, status code, and duration for every HTTP request.
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("arogya.http")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that logs every HTTP request with:
    - HTTP method and path
    - Response status code
    - Request duration in milliseconds
    - Client IP address
    """

    def __init__(self, app: ASGIApp, log_level: int = logging.INFO) -> None:
        super().__init__(app)
        self.log_level = log_level

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # Extract client info
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query = f"?{request.url.query}" if request.url.query else ""

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            status_code = response.status_code

            # Color-code by status
            if status_code < 300:
                level = logging.INFO
            elif status_code < 400:
                level = logging.INFO
            elif status_code < 500:
                level = logging.WARNING
            else:
                level = logging.ERROR

            logger.log(
                level,
                "%s %s%s → %d  [%.1fms]  ip=%s",
                method,
                path,
                query,
                status_code,
                duration_ms,
                client_ip,
            )

            # Add latency header for debugging
            response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "%s %s%s → 500  [%.1fms]  ip=%s  error=%s",
                method,
                path,
                query,
                duration_ms,
                client_ip,
                str(exc),
            )
            raise