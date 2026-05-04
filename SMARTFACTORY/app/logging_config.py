"""
Backward Compatibility Layer for Logging Configuration.

This module provides a backward-compatible interface to the new structlog-based
logging system. Existing code that imports `init_logger` from this module
will continue to work without modification.

The `init_logger` function now delegates to `app.core.logging` module,
which provides the full structlog configuration.

For new code, prefer importing directly from `app.core.logging`:
    from app.core.logging import get_logger, configure_logging

Migration Guide:
---------------
Old code:
    from app.logging_config import init_logger
    logger = init_logger(name="MyModule")

New code:
    from app.core.logging import get_logger
    logger = get_logger(__name__)

Architecture:
------------
- app.core.logging: Core structlog configuration (processor chain, renderers, etc.)
- app.logging_config: Backward-compatible wrapper (this module)
- app.middleware.logging_middleware: Flask request context middleware
"""

from app.core.logging import get_logger, configure_logging


def init_logger(name="SmartFactory", log_file=None, level=None):
    """
    Backward-compatible logger initialization.

    This function provides compatibility with existing code that expects
    a traditional logging.Logger instance. It now returns a structlog
    BoundLogger configured with the application's processor chain.

    Note: Parameters `log_file` and `level` are ignored.
    Use environment variables instead:
    - LOG_LEVEL: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - LOG_FORMAT: Set output format (console, json)
    - ENVIRONMENT: Set environment (development, production)

    Args:
        name: Logger name (used as the 'logger' field in log output)
        log_file: Ignored (structlog logs to stdout/stderr)
        level: Ignored (use LOG_LEVEL environment variable)

    Returns:
        structlog.stdlib.BoundLogger: Configured structlog logger instance
    """
    # Ensure logging is configured (idempotent)
    configure_logging()

    # Return a structlog logger bound to the given name
    return get_logger(name)
