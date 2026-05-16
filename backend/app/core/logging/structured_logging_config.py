"""
Agent Cluster Orchestrator - Structured Logging Configuration

Provides comprehensive structured logging setup with multiple format options.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog


class LogFormat(str, Enum):
    """Supported log output formats."""
    JSON = "json"
    CONSOLE = "console"
    PRETTY = "pretty"


@dataclass
class LoggingConfiguration:
    """Configuration parameters for logging system."""
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.JSON
    include_timestamp: bool = True
    include_process_info: bool = True
    include_thread_info: bool = False
    color_output: bool = True


def configure_structured_logging(
    config: Optional[LoggingConfiguration] = None
) -> structlog.stdlib.BoundLogger:
    """
    Configure structured logging system with specified parameters.
    
    Args:
        config: Logging configuration instance or None for defaults
        
    Returns:
        Configured structlog logger instance
    """
    if config is None:
        config = LoggingConfiguration()
    
    # Validate and set log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    log_level = config.log_level.upper()
    if log_level not in valid_levels:
        log_level = "INFO"
    
    numeric_level = getattr(logging, log_level)
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )
    
    # Configure format-specific handlers
    if config.log_format in [LogFormat.JSON, LogFormat.PRETTY]:
        try:
            from pythonjsonlogger.jsonlogger import JsonFormatter
            handler = logging.StreamHandler(sys.stdout)
            formatter_fields = ["levelname", "name", "message"]
            if config.include_timestamp:
                formatter_fields.insert(0, "asctime")
            if config.include_process_info:
                formatter_fields.append("process")
            if config.include_thread_info:
                formatter_fields.append("thread")
            
            handler.setFormatter(JsonFormatter(
                " ".join(f"%({field})s" for field in formatter_fields),
                rename_fields={"levelname": "level", "asctime": "timestamp"}
            ))
            logging.root.handlers = [handler]
        except ImportError:
            # Fall back to console logging if pythonjsonlogger not available
            pass
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
    ]
    
    if config.include_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt="iso"))
    
    processors.extend([
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ])
    
    # Add renderer based on log format
    if config.log_format == LogFormat.JSON:
        processors.append(structlog.processors.JSONRenderer())
    elif config.log_format == LogFormat.PRETTY:
        processors.append(structlog.processors.JSONRenderer(indent=2))
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(colors=config.color_output)
        )
    
    # Final structlog configuration
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger()


def setup_simple_logging(
    log_level: str = "INFO",
    log_format: str = "json"
) -> structlog.stdlib.BoundLogger:
    """
    Backward-compatible logging setup function.
    
    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log output format (json or console)
        
    Returns:
        Configured structlog logger instance
    """
    config = LoggingConfiguration(
        log_level=log_level,
        log_format=LogFormat(log_format)
    )
    return configure_structured_logging(config)


# Default logger instance
_default_logger: Optional[structlog.stdlib.BoundLogger] = None


def get_application_logger() -> structlog.stdlib.BoundLogger:
    """
    Get or create the default application logger.
    
    Returns:
        Configured structlog logger instance
    """
    global _default_logger
    
    if _default_logger is None:
        _default_logger = setup_simple_logging()
    
    return _default_logger


# Initialize default logger
logger = get_application_logger()
