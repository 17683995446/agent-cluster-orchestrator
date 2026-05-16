"""
Agent Cluster Orchestrator - Logging Package

Provides comprehensive logging system with structured output.

Key Features:
- Structured JSON logging
- Console logging for development
- Configurable log levels
- Context-aware logging
- Backward compatibility maintained

Usage:
```python
from app.core.logging import get_application_logger, setup_simple_logging

logger = get_application_logger()
logger.info("Application started", component="core")
```
"""
from app.core.logging.structured_logging_config import (
    configure_structured_logging,
    setup_simple_logging,
    get_application_logger,
    LogFormat,
    LoggingConfiguration,
    logger
)

__all__ = [
    "configure_structured_logging",
    "setup_simple_logging",
    "get_application_logger",
    "LogFormat",
    "LoggingConfiguration",
    "logger",
]
