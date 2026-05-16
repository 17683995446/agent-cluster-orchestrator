"""
Dynamic configuration management for Agent Cluster Orchestrator.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from pathlib import Path

import structlog

logger = structlog.get_logger()


class ConfigSourceType(Enum):
    ENVIRONMENT = "environment"
    FILE = "file"
    DATABASE = "database"
    CONSUL = "consul"
    ETCD = "etcd"


class ConfigScope(Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"


@dataclass
class ConfigEntry:
    """A single configuration entry."""
    key: str
    value: Any
    scope: ConfigScope = ConfigScope.GLOBAL
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    description: Optional[str] = None
    default_value: Optional[Any] = None
    validation_schema: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConfigSchema:
    """Schema definition for configuration validation."""
    type: str
    min: Optional[Union[int, float]] = None
    max: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    enum: Optional[list] = None
    required: bool = False


class ConfigManager(ABC):
    """Abstract base class for configuration management."""
    
    @abstractmethod
    async def get(self, key: str, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> Any:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> None:
        pass
    
    @abstractmethod
    async def get_all(self, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def delete(self, key: str, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> bool:
        pass
    
    @abstractmethod
    async def reload(self) -> None:
        pass


class InMemoryConfigManager(ConfigManager):
    """In-memory configuration manager."""
    
    def __init__(self):
        self._configs: Dict[str, ConfigEntry] = {}
        self._load_defaults()
    
    def _load_defaults(self):
        """Load default configuration values."""
        defaults = [
            ConfigEntry(
                key="app.name",
                value="Agent Cluster Orchestrator",
                description="Application name"
            ),
            ConfigEntry(
                key="app.version",
                value="2.0.0",
                description="Application version"
            ),
            ConfigEntry(
                key="api.rate_limit",
                value=1000,
                description="API rate limit per hour",
                validation_schema={"type": "integer", "min": 10, "max": 10000}
            ),
            ConfigEntry(
                key="api.timeout",
                value=30,
                description="API request timeout in seconds",
                validation_schema={"type": "integer", "min": 5, "max": 300}
            ),
            ConfigEntry(
                key="llm.default_provider",
                value="openai",
                description="Default LLM provider",
                validation_schema={"type": "string", "enum": ["openai", "anthropic", "local"]}
            ),
            ConfigEntry(
                key="llm.default_model",
                value="gpt-4",
                description="Default LLM model"
            ),
            ConfigEntry(
                key="cache.ttl",
                value=3600,
                description="Default cache TTL in seconds",
                validation_schema={"type": "integer", "min": 60, "max": 86400}
            ),
            ConfigEntry(
                key="task.retry_max_attempts",
                value=5,
                description="Maximum retry attempts for tasks",
                validation_schema={"type": "integer", "min": 1, "max": 20}
            ),
            ConfigEntry(
                key="websocket.heartbeat_interval",
                value=30,
                description="WebSocket heartbeat interval in seconds"
            ),
            ConfigEntry(
                key="logging.level",
                value="INFO",
                description="Logging level",
                validation_schema={"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]}
            ),
        ]
        
        for entry in defaults:
            self._configs[entry.key] = entry
    
    def _validate_value(self, entry: ConfigEntry, value: Any) -> bool:
        """Validate value against schema."""
        if not entry.validation_schema:
            return True
        
        schema = entry.validation_schema
        
        if "type" in schema:
            type_mapping = {
                "string": str,
                "integer": int,
                "float": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            expected_type = type_mapping.get(schema["type"])
            if expected_type and not isinstance(value, expected_type):
                return False
        
        if "min" in schema and value < schema["min"]:
            return False
        
        if "max" in schema and value > schema["max"]:
            return False
        
        if "enum" in schema and value not in schema["enum"]:
            return False
        
        return True
    
    async def get(self, key: str, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> Any:
        """Get configuration value."""
        # First try specific scope
        if tenant_id and scope == ConfigScope.TENANT:
            tenant_key = f"{tenant_id}:{key}"
            if tenant_key in self._configs:
                return self._configs[tenant_key].value
        
        # Fall back to global
        if key in self._configs:
            return self._configs[key].value
        
        return None
    
    async def set(self, key: str, value: Any, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> None:
        """Set configuration value."""
        actual_key = key
        
        if tenant_id and scope == ConfigScope.TENANT:
            actual_key = f"{tenant_id}:{key}"
        
        # Check if we have a global entry for validation
        base_entry = self._configs.get(key)
        if base_entry and not self._validate_value(base_entry, value):
            raise ValueError(f"Invalid value for {key}: {value}")
        
        entry = ConfigEntry(
            key=actual_key,
            value=value,
            scope=scope,
            tenant_id=tenant_id,
            default_value=base_entry.value if base_entry else None,
            validation_schema=base_entry.validation_schema if base_entry else None,
        )
        
        self._configs[actual_key] = entry
        logger.info("config_updated", key=key, scope=scope.value)
    
    async def get_all(self, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all configurations for a scope."""
        result = {}
        
        if tenant_id and scope == ConfigScope.TENANT:
            prefix = f"{tenant_id}:"
            for key, entry in self._configs.items():
                if key.startswith(prefix):
                    result[key[len(prefix):]] = entry.value
        else:
            for key, entry in self._configs.items():
                if ":" not in key:  # Global configs
                    result[key] = entry.value
        
        return result
    
    async def delete(self, key: str, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> bool:
        """Delete configuration entry."""
        actual_key = key
        
        if tenant_id and scope == ConfigScope.TENANT:
            actual_key = f"{tenant_id}:{key}"
        
        if actual_key in self._configs:
            del self._configs[actual_key]
            logger.info("config_deleted", key=key)
            return True
        
        return False
    
    async def reload(self) -> None:
        """Reload configurations."""
        self._load_defaults()
        logger.info("configs_reloaded")


class FileConfigManager(InMemoryConfigManager):
    """Configuration manager that loads from file."""
    
    def __init__(self, config_file: str = "config.json"):
        super().__init__()
        self.config_file = Path(config_file)
        self._load_from_file()
    
    def _load_from_file(self):
        """Load configuration from JSON file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                
                for key, value in data.items():
                    if key in self._configs:
                        self._configs[key].value = value
                    else:
                        self._configs[key] = ConfigEntry(key=key, value=value)
                
                logger.info("configs_loaded_from_file", file=str(self.config_file))
            except Exception as e:
                logger.error("failed_to_load_config_file", error=str(e))
    
    async def save_to_file(self):
        """Save configuration to file."""
        data = {key: entry.value for key, entry in self._configs.items() if ":" not in key}
        
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info("configs_saved_to_file", file=str(self.config_file))
    
    async def set(self, key: str, value: Any, scope: ConfigScope = ConfigScope.GLOBAL, tenant_id: Optional[str] = None) -> None:
        await super().set(key, value, scope, tenant_id)
        if scope == ConfigScope.GLOBAL:
            await self.save_to_file()


# Global configuration manager instance
config_manager = FileConfigManager()


# Helper function to get configuration
async def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value with fallback."""
    value = await config_manager.get(key)
    return value if value is not None else default


# Helper function to set configuration
async def set_config(key: str, value: Any) -> None:
    """Set configuration value."""
    await config_manager.set(key, value)
