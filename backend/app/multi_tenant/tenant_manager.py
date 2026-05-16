"""
Multi-tenant support for Agent Cluster Orchestrator.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Set
import uuid

import structlog

logger = structlog.get_logger()


class TenantStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@dataclass
class Tenant:
    """Represents a tenant in the system."""
    id: str
    name: str
    domain: str
    status: TenantStatus = TenantStatus.ACTIVE
    quota: TenantQuota = field(default_factory=lambda: TenantQuota())
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TenantQuota:
    """Resource quota for a tenant."""
    max_agents: int = 10
    max_tasks: int = 100
    max_concurrent_tasks: int = 10
    rate_limit: int = 1000  # requests per hour
    storage_limit_gb: int = 10


@dataclass
class TenantConfig:
    """Configuration for a tenant."""
    llm_providers: Set[str] = field(default_factory=lambda: {"openai", "anthropic"})
    default_model: str = "gpt-4"
    enable_websocket: bool = True
    enable_streaming: bool = True
    webhook_url: Optional[str] = None


class TenantManager(ABC):
    """Abstract base class for tenant management."""
    
    @abstractmethod
    async def create_tenant(self, name: str, domain: str, **kwargs) -> Tenant:
        pass
    
    @abstractmethod
    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        pass
    
    @abstractmethod
    async def get_tenant_by_domain(self, domain: str) -> Optional[Tenant]:
        pass
    
    @abstractmethod
    async def update_tenant(self, tenant_id: str, **kwargs) -> Tenant:
        pass
    
    @abstractmethod
    async def delete_tenant(self, tenant_id: str) -> bool:
        pass
    
    @abstractmethod
    async def list_tenants(self, status: Optional[TenantStatus] = None) -> list[Tenant]:
        pass
    
    @abstractmethod
    async def check_quota(self, tenant_id: str, resource_type: str) -> bool:
        pass


class InMemoryTenantManager(TenantManager):
    """In-memory tenant manager for testing and development."""
    
    def __init__(self):
        self._tenants: Dict[str, Tenant] = {}
        self._domain_map: Dict[str, str] = {}
    
    async def create_tenant(self, name: str, domain: str, **kwargs) -> Tenant:
        tenant_id = str(uuid.uuid4())
        tenant = Tenant(
            id=tenant_id,
            name=name,
            domain=domain,
            **kwargs
        )
        
        self._tenants[tenant_id] = tenant
        self._domain_map[domain] = tenant_id
        
        logger.info("tenant_created", tenant_id=tenant_id, name=name)
        return tenant
    
    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)
    
    async def get_tenant_by_domain(self, domain: str) -> Optional[Tenant]:
        tenant_id = self._domain_map.get(domain)
        if tenant_id:
            return self._tenants.get(tenant_id)
        return None
    
    async def update_tenant(self, tenant_id: str, **kwargs) -> Tenant:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        for key, value in kwargs.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)
        
        tenant.updated_at = datetime.now()
        logger.info("tenant_updated", tenant_id=tenant_id)
        return tenant
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        
        del self._tenants[tenant_id]
        del self._domain_map[tenant.domain]
        
        logger.info("tenant_deleted", tenant_id=tenant_id)
        return True
    
    async def list_tenants(self, status: Optional[TenantStatus] = None) -> list[Tenant]:
        tenants = list(self._tenants.values())
        if status:
            tenants = [t for t in tenants if t.status == status]
        return tenants
    
    async def check_quota(self, tenant_id: str, resource_type: str) -> bool:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        
        # In production, this would query actual usage
        return True


class TenantContext:
    """Context manager for tenant operations."""
    
    def __init__(self, tenant_manager: TenantManager, tenant_id: str):
        self.tenant_manager = tenant_manager
        self.tenant_id = tenant_id
        self.tenant: Optional[Tenant] = None
    
    async def __aenter__(self) -> Tenant:
        self.tenant = await self.tenant_manager.get_tenant(self.tenant_id)
        if not self.tenant:
            raise ValueError(f"Tenant {self.tenant_id} not found")
        return self.tenant
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.tenant:
            await self.tenant_manager.update_tenant(self.tenant_id)


# Global tenant manager instance
tenant_manager = InMemoryTenantManager()


# FastAPI dependency for tenant context
async def get_current_tenant(request) -> Tenant:
    """FastAPI dependency to get current tenant from request."""
    # In production, this would extract tenant from request context
    # (e.g., from domain, header, or JWT claim)
    tenant_id = request.headers.get("X-Tenant-ID")
    
    if not tenant_id:
        # Default tenant for development
        tenant = await tenant_manager.get_tenant_by_domain("default.local")
        if not tenant:
            tenant = await tenant_manager.create_tenant(
                name="Default Tenant",
                domain="default.local"
            )
        return tenant
    
    tenant = await tenant_manager.get_tenant(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    return tenant
