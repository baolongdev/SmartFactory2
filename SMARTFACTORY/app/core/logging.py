"""
Centralized Structured Logging Configuration for SmartFactory2.

This module provides a production-ready logging system using structlog:
- Development: Human-readable colored console output
- Production: Machine-parseable JSON logs
- Automatic sensitive data redaction (passwords, tokens, API keys)
- Request-scoped context via contextvars (request_id, user_id, etc.)
- Seamless integration with standard logging and Flask

Architecture:
------------
1. Processor Chain:
   - merge_contextvars: Merge request-scoped context
   - add_log_level: Add log level to event
   - StackInfoRenderer: Render stack info when requested
   - format_exc_info: Format exception tracebacks
   - TimeStamper: Add ISO timestamp
   - redact_sensitive_data: Redact sensitive fields
   - EventRenamer: Rename 'event' to 'message' for compatibility
   - CallsiteParameterAdder: Add module/function/line info

2. Renderers:
   - ConsoleRenderer: Colored, human-readable (development)
   - JSONRenderer: Structured JSON output (production)

3. Integration:
   - Standard logging → structlog formatter
   - Third-party libraries → redirected through structlog
   - Flask app → middleware for request context

Usage:
------
    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("event_name", key1="value1", key2="value2")

Environment Variables:
-------------------
    LOG_LEVEL: DEBUG|INFO|WARNING|ERROR|CRITICAL (default: INFO)
    LOG_FORMAT: console|json (default: console)
    ENVIRONMENT: development|staging|production (default: development)
    SERVICE_NAME: Service identifier (default: SmartFactory2)
"""

import logging
import os
import sys
from typing import Any

import structlog


# ---------------------------------------------------------------------------
# Windows ANSI Support
# ---------------------------------------------------------------------------
def _enable_windows_ansi() -> bool:
    """
    Enable ANSI escape code (VT100) support on Windows 10+ consoles.
    Uses SetConsoleMode with ENABLE_VIRTUAL_TERMINAL_PROCESSING.
    Safe to call on non-Windows — returns False silently.
    """
    if os.name != 'nt':
        return False
    try:
        import ctypes
        import ctypes.wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.wintypes.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Sensitive Data Protection
# ---------------------------------------------------------------------------
# Keys that will be automatically redacted from log output
# Matching is case-insensitive and checks if sensitive string is in key name
SENSITIVE_KEYS = frozenset({
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "secret",
    "api_key",
    "apikey",
    "private_key",
    "credit_card",
    "ssn",
    "mqtt_password",
})


def redact_sensitive_data(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Structlog processor that redacts sensitive data from log events.

    Scans event_dict keys and recursively checks nested dicts/lists.
    If a key contains any sensitive string (case-insensitive),
    its value is replaced with "***REDACTED***".

    Args:
        logger: The logger instance (unused, required by processor signature)
        method_name: The log method name (unused, required by processor signature)
        event_dict: The log event dictionary to process.

    Returns:
        dict[str, Any]: The processed event dictionary with sensitive data redacted
    """
    keys_to_redact = set()

    # Check top-level keys
    for key in event_dict.keys():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            keys_to_redact.add(key)

    # Redact matched keys
    for key in keys_to_redact:
        event_dict[key] = "***REDACTED***"

    # Recursively check nested structures
    for key, value in event_dict.items():
        if isinstance(value, dict):
            redact_sensitive_data(logger, method_name, value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    redact_sensitive_data(logger, method_name, item)

    return event_dict


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
def configure_logging() -> None:
    """
    Configure structlog for the entire application.

    This function:
    1. Reads environment variables for configuration
    2. Sets up the processor chain for both structlog and standard logging
    3. Configures the appropriate renderer (console or JSON)
    4. Sets up the root logger with structlog formatter
    5. Reduces noise from verbose third-party loggers
    6. Binds global context (service name, environment)

    Should be called once at application startup, before any logging occurs.
    """
    # Enable Windows ANSI colors (no-op on Linux/macOS)
    _enable_windows_ansi()

    # Read configuration from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "console").lower()
    environment = os.getenv("ENVIRONMENT", "development")
    service_name = os.getenv("SERVICE_NAME", "SmartFactory2")

    # Map string level to numeric (required by standard logging)
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Create timestamper for ISO format timestamps
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    # -----------------------------------------------------------------------
    # Shared Processors
    # These are used by both structlog and standard logging formatters
    # Order matters: processors are called in order
    # -----------------------------------------------------------------------
    shared_processors = [
        # Merge contextvars (request-scoped context like request_id)
        structlog.contextvars.merge_contextvars,

        # Add log level to event dict
        structlog.processors.add_log_level,

        # Render stack info when requested
        structlog.processors.StackInfoRenderer(),

        # Format exception info into event dict
        structlog.processors.format_exc_info,

        # Add ISO timestamp
        timestamper,

        # Redact sensitive data (passwords, tokens, etc.)
        redact_sensitive_data,

        # Rename 'event' key to 'message' for compatibility
        structlog.processors.EventRenamer("message"),
    ]

    # Callsite info (module/func/lineno) only in DEBUG — too noisy otherwise
    if numeric_level <= logging.DEBUG:
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            )
        )

    # -----------------------------------------------------------------------
    # Choose Renderer
    # Console for development (human-readable, colored)
    # JSON for production (machine-parseable)
    # Disable colors on Windows to avoid colorama issues
    # -----------------------------------------------------------------------
    use_colors = (log_format != "json" and environment != "production")

    if log_format == "json" or environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=use_colors)

    # -----------------------------------------------------------------------
    # Configure Standard Logging
    # This ensures third-party libraries using standard logging work with structlog
    # -----------------------------------------------------------------------
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # -----------------------------------------------------------------------
    # Configure Structlog
    # wrapper_class: Use BoundLogger for stdlib compatibility
    # logger_factory: Use stdlib LoggerFactory for integration
    # cache_logger_on_first_use: Performance optimization
    # -----------------------------------------------------------------------
    structlog.configure(
        processors=[
            # Filter by log level (respects standard logging levels)
            structlog.stdlib.filter_by_level,
            # Apply shared processors
            *shared_processors,
            # Wrap for formatter (allows standard logging to use structlog processors)
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # -----------------------------------------------------------------------
    # Create Formatter for Standard Logging
    # This formatter is used by the root logger and applies structlog processors
    # -----------------------------------------------------------------------
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    # -----------------------------------------------------------------------
    # Set Up Root Logger
    # Clear existing handlers and add structlog-configured handler
    # -----------------------------------------------------------------------
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # -----------------------------------------------------------------------
    # Reduce Noise from Third-Party Loggers
    # These libraries can be very verbose; set them to WARNING or higher
    # -----------------------------------------------------------------------
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # -----------------------------------------------------------------------
    # Bind Global Context
    # These values are added to every log event
    # -----------------------------------------------------------------------
    structlog.contextvars.bind_contextvars(
        service=service_name,
        environment=environment,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger for the given name.

    Usage:
        logger = get_logger(__name__)

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        structlog.stdlib.BoundLogger: Configured structlog logger
    """
    return structlog.get_logger(name)
