import logging
import re
import time
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from backend.app.core.logging import request_id_ctx

logger = logging.getLogger("backend.app.access")

# Request ID: alphanumeric, hyphen, underscore; 1 to 64 chars
REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces request correlation and structured audit logging:
    1. Extracts or securely generates a sanitized X-Request-ID.
    2. Binds it to request.state and contextvars for structured logging.
    3. Measures request duration and logs request completion in JSON format.
    4. Attaches X-Request-ID header to every response (including 500 errors).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        raw_req_id = request.headers.get("X-Request-ID")
        if raw_req_id and REQUEST_ID_REGEX.match(raw_req_id):
            request_id = raw_req_id
        else:
            request_id = str(uuid.uuid4())

        # Bind to request state and contextvar
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Log request completion with structured attributes
            logger.info(
                f"{request.method} {request.url.path} returned {response.status_code} in {duration_ms}ms",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled exception during {request.method} {request.url.path}: {exc}",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            # Fail closed with sanitized JSON response
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={"X-Request-ID": request_id},
            )
        finally:
            request_id_ctx.reset(token)
