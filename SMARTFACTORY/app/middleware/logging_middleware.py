"""
Flask Middleware for Request-Scoped Logging Context.

This module implements request lifecycle hooks that bind contextual information
to structlog's contextvars, making every log statement within a request
automatically include request-specific fields.

Context Variables Bound:
---------------------
- request_id: Unique identifier for each request (from X-Request-ID header or auto-generated)
- method: HTTP method (GET, POST, etc.)
- path: Request path
- client_ip: Client IP address
- user_agent: User-Agent header value
- duration_ms: Request duration in milliseconds (added on response)

Request Lifecycle:
---------------
1. before_request: Generate/capture request_id, bind context, record start time
2. after_request: Calculate duration, log request_finished, clear context
3. teardown_request: Clear context on error, log exceptions

Usage:
------
    from app.middleware.logging_middleware import init_logging_middleware

    def create_app():
        app = Flask(__name__)
        init_logging_middleware(app)
        return app

Security:
---------
- Context is cleared after each request to prevent data leakage
- Request IDs are captured from headers or auto-generated (UUID4)
- Request IDs are added to response headers for tracing
"""

import time
import uuid

from flask import request, g

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars


# Module-level logger for middleware events
logger = structlog.get_logger(__name__)


def init_logging_middleware(app):
    """
    Initialize logging middleware for Flask application.

    Registers before_request, after_request, and teardown_request hooks
    to automatically manage request-scoped logging context.

    Args:
        app: Flask application instance
    """
    logger.info("logging_middleware_initializing")

    @app.before_request
    def before_request():
        """
        Executed before each request.

        Responsibilities:
        1. Generate or extract request ID
        2. Clear any leftover context from previous requests
        3. Bind request context to structlog contextvars
        4. Record request start time for duration calculation
        5. Log request_started event
        """
        # -----------------------------------------------------------------------
        # Request ID Management
        # Use X-Request-ID header if provided (for distributed tracing),
        # otherwise generate a new UUID4
        # -----------------------------------------------------------------------
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # -----------------------------------------------------------------------
        # Context Cleanup
        # Clear any context that might have leaked from previous requests
        # (important in threaded/async environments)
        # -----------------------------------------------------------------------
        clear_contextvars()

        # -----------------------------------------------------------------------
        # Bind Request Context
        # This makes these fields available to all log statements
        # within the request lifecycle
        # -----------------------------------------------------------------------
        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.path,
            client_ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )

        # -----------------------------------------------------------------------
        # Record Start Time
        # Store in Flask's g object for duration calculation
        # -----------------------------------------------------------------------
        g.request_start_time = time.perf_counter()

        # -----------------------------------------------------------------------
        # Log Request Start
        # This event includes all bound context variables automatically
        # -----------------------------------------------------------------------
        logger.info("request_started")

    @app.after_request
    def after_request(response):
        """
        Executed after each request (including on error).

        Responsibilities:
        1. Calculate request duration
        2. Log request_finished event with status code and duration
        3. Add request_id to response headers for client-side tracing
        4. Clear context to prevent data leakage
        """
        # -----------------------------------------------------------------------
        # Calculate Duration
        # Time from request start to response, in milliseconds
        # -----------------------------------------------------------------------
        duration_ms = None
        if hasattr(g, "request_start_time"):
            duration_ms = round((time.perf_counter() - g.request_start_time) * 1000, 2)

        # -----------------------------------------------------------------------
        # Log Request Completion
        # Includes status_code, duration_ms, and all bound context
        # -----------------------------------------------------------------------
        logger.info(
            "request_finished",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # -----------------------------------------------------------------------
        # Add Request ID to Response Headers
        # Allows clients to correlate requests and responses
        # -----------------------------------------------------------------------
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if request_id:
            response.headers["X-Request-ID"] = request_id

        # -----------------------------------------------------------------------
        # Clear Context
        # Critical: prevents context leakage between requests
        # -----------------------------------------------------------------------
        clear_contextvars()

        return response

    @app.teardown_request
    def teardown_request(exception=None):
        """
        Executed when request context is torn down (always runs).

        Responsibilities:
        1. Clear context (safety net)
        2. Log exceptions if they occurred
        """
        # -----------------------------------------------------------------------
        # Clear Context (Safety Net)
        # Double-clear to ensure no context leakage
        # -----------------------------------------------------------------------
        clear_contextvars()

        # -----------------------------------------------------------------------
        # Log Exceptions
        # If an unhandled exception occurred, log it with traceback
        # -----------------------------------------------------------------------
        if exception:
            logger.exception(
                "request_failed",
                error_type=type(exception).__name__,
            )
            logger.info("logging_middleware_initialized")
