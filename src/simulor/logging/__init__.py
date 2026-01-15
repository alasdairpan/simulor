"""Logging configuration and utilities for Simulor.

Simulor uses Python's standard logging module, following library best practices.
By default, Simulor is completely silent (using NullHandler), giving you full control
over logging configuration using standard Python logging APIs.

Philosophy:
    - Standard Python Logging: Uses the standard logging module - no custom APIs to learn
    - Library-Friendly Design: Silent by default with NullHandler, respecting user's logging config
    - Hierarchical Organization: Logger names mirror module structure (simulor.engine, simulor.execution, etc.)
    - Performance-Conscious: Lazy evaluation and guarded expensive operations ensure minimal overhead

Quick Start:
    >>> import logging
    >>> import simulor
    >>>
    >>> # Configure Python's logging for Simulor
    >>> logging.basicConfig(
    ...     level=logging.INFO,
    ...     format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    ... )
    >>>
    >>> # Now run your backtest - you'll see important events logged
    >>> engine = simulor.Engine(...)
    >>> result = engine.run(...)

Logger Hierarchy:
    simulor                          # Root logger
    ├── simulor.engine               # Event loop orchestration
    ├── simulor.data                 # Data providers and subscriptions
    │   ├── simulor.data.providers   # CSV, Parquet, API providers
    │   └── simulor.data.market_store # Historical data management
    ├── simulor.universe             # Universe selection
    ├── simulor.alpha                # Signal generation
    ├── simulor.portfolio            # Portfolio construction & tracking
    ├── simulor.risk                 # Risk management
    ├── simulor.allocation           # Capital allocation
    ├── simulor.execution            # Order execution and fills
    │   ├── simulor.execution.broker # Broker-specific events
    │   └── simulor.execution.fills  # Order fill details
    └── simulor.analytics            # Performance analysis

Targeted Debugging Example:
    >>> import logging
    >>>
    >>> # Set global level
    >>> logging.basicConfig(level=logging.WARNING)
    >>>
    >>> # Enable DEBUG only for execution module
    >>> logging.getLogger('simulor.execution').setLevel(logging.DEBUG)
"""

from __future__ import annotations

import logging

__all__ = [
    "get_logger",
    "configure_null_handler",
]

# Root logger name
ROOT_LOGGER_NAME = "simulor"


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the standard Simulor naming convention.

    This function provides a consistent way to create loggers that follow the
    hierarchical structure. It automatically prepends 'simulor.' to the logger
    name if not already present.

    Args:
        name: Logger name, typically the module name (e.g., 'engine', 'execution.broker').
              The 'simulor.' prefix is added automatically if not present.

    Returns:
        A Logger instance configured with the hierarchical name.

    Examples:
        >>> from simulor.logging import get_logger
        >>>
        >>> # Within simulor/engine.py
        >>> logger = get_logger(__name__)  # Creates 'simulor.engine' logger
        >>>
        >>> # Within simulor/execution/broker.py
        >>> logger = get_logger(__name__)  # Creates 'simulor.execution.broker' logger
        >>>
        >>> # Manual specification (less common)
        >>> logger = get_logger('execution.fills')  # Creates 'simulor.execution.fills' logger

    Performance Note:
        Logger instances are cached by Python's logging module, so calling this
        function multiple times with the same name is efficient (O(1) lookup).
    """
    # Strip any leading 'simulor.' to avoid duplication
    if name.startswith(f"{ROOT_LOGGER_NAME}."):
        full_name = name
    elif name == ROOT_LOGGER_NAME:
        full_name = ROOT_LOGGER_NAME
    else:
        # Prepend 'simulor.' to create hierarchical logger
        full_name = f"{ROOT_LOGGER_NAME}.{name}"

    return logging.getLogger(full_name)


def configure_null_handler() -> None:
    """Configure the root Simulor logger with a NullHandler.

    This is a library best practice: libraries should not produce output by default.
    The NullHandler prevents "No handler found" warnings while ensuring the library
    remains silent unless the user explicitly configures logging.

    This function is called automatically when the simulor package is imported,
    so users typically don't need to call it directly.

    Example:
        >>> import logging
        >>> from simulor.logging import configure_null_handler
        >>>
        >>> # Explicitly configure NullHandler (usually automatic)
        >>> configure_null_handler()
        >>>
        >>> # Now configure user's logging to see Simulor output
        >>> logging.basicConfig(level=logging.INFO)

    Library Design Pattern:
        - Libraries: Use NullHandler by default (silent)
        - Applications: Configure logging explicitly with basicConfig() or handlers
        - Result: Clean separation between library and application logging concerns
    """
    root_logger = logging.getLogger(ROOT_LOGGER_NAME)

    # Only add NullHandler if no handlers are configured
    # This prevents duplicate handlers if called multiple times
    if not root_logger.handlers:
        root_logger.addHandler(logging.NullHandler())

    # Set propagate=True to ensure child loggers propagate to root
    # This allows users to configure the root 'simulor' logger and affect all children
    root_logger.propagate = True


# Configure NullHandler when module is imported
configure_null_handler()
