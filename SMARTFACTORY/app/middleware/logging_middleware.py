"""
Flask Middleware for Request-Scoped Logging Context.

Polling endpoints (status checks, detections) are logged at DEBUG to avoid
noise — they are called every 1-5 seconds from the browser frontend.
All other endpoints are logged at INFO as usual.
"""

import time
import uuid

from flask import request, g

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars


logger = structlog.get_logger(__name__)

# Endpoints polled frequently by the frontend — log at DEBUG, not INFO
_POLLING_PATHS = frozenset({
    "/api/uart/status",
    "/api/uart/read",
    "/api/camera/status",
    "/api/camera/detections",
})


def init_logging_middleware(app):
    """Register request lifecycle hooks for structured logging."""

    logger.info("logging_middleware_initializing")

    @app.before_request
    def before_request():
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        clear_contextvars()

        is_polling = request.path in _POLLING_PATHS

        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.path,
            client_ip=request.remote_addr,
            # Omit user_agent for polling requests — it never changes and wastes space
            **({"user_agent": request.headers.get("User-Agent")} if not is_polling else {}),
        )

        g.request_start_time = time.perf_counter()
        g.is_polling = is_polling

        if not is_polling:
            logger.info("request_started")
        else:
            logger.debug("request_started")

    @app.after_request
    def after_request(response):
        duration_ms = None
        if hasattr(g, "request_start_time"):
            duration_ms = round((time.perf_counter() - g.request_start_time) * 1000, 2)

        is_polling = getattr(g, "is_polling", False)

        if not is_polling:
            logger.info("request_finished",
                        status_code=response.status_code,
                        duration_ms=duration_ms)
        else:
            logger.debug("request_finished",
                         status_code=response.status_code,
                         duration_ms=duration_ms)

        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if request_id:
            response.headers["X-Request-ID"] = request_id

        clear_contextvars()
        return response

    @app.teardown_request
    def teardown_request(exception=None):
        clear_contextvars()
        if exception:
            logger.exception("request_failed", error_type=type(exception).__name__)

    logger.info("logging_middleware_initialized")
