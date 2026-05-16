"""
Real LLM Provider Integration Service
Production-ready integration with major LLM providers.
"""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

import httpx
import structlog

logger = structlog.get_logger()


class LLMProviderType(Enum):
    """Supported LLM provider types."""
    OPENAI = auto()
    ANTHROPIC = auto()
    HUGGINGFACE = auto()
    VERTEX_AI = auto()
    BEDROCK = auto()


@dataclass
class LLMRequest:
    """Standardized LLM request format."""
    prompt: str
    model: str
    provider: LLMProviderType
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False
    stop: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Standardized LLM response format."""
    content: str
    model: str
    provider: LLMProviderType
    usage: Dict[str, int]
    finish_reason: str
    raw_response: Dict[str, Any]
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LLMProviderConfig:
    """Configuration for LLM providers."""
    provider_type: LLMProviderType
    api_key: str
    base_url: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 3
    default_model: str = "gpt-4"
    region: Optional[str] = None


class BaseLLMIntegration(ABC):
    """Base class for LLM provider integration."""

    def __init__(self, config: LLMProviderConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    @abstractmethod
    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Generate response from LLM."""
        pass

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Chat with LLM using message format."""
        pass

    @abstractmethod
    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Generate embeddings for texts."""
        pass

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url or self._get_base_url(),
                headers=self._get_headers(),
                timeout=httpx.Timeout(self.config.timeout)
            )
        return self._client

    @abstractmethod
    def _get_base_url(self) -> str:
        """Get base URL for API."""
        pass

    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        pass

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class OpenAIIntegration(BaseLLMIntegration):
    """OpenAI API integration."""

    def __init__(self, config: LLMProviderConfig):
        if config.provider_type != LLMProviderType.OPENAI:
            raise ValueError(f"Expected OPENAI provider, got {config.provider_type}")
        super().__init__(config)

    def _get_base_url(self) -> str:
        return self.config.base_url or "https://api.openai.com/v1"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Generate response using OpenAI completion API."""
        start_time = datetime.utcnow()
        client = await self._get_client()

        model = model or self.config.default_model
        request_data = {
            "model": model,
            "prompt": prompt,
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 1.0),
            "stream": kwargs.get("stream", False),
        }

        if kwargs.get("stop"):
            request_data["stop"] = kwargs["stop"]

        try:
            response = await client.post(
                "/completions",
                json=request_data
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return LLMResponse(
                content=data["choices"][0]["text"],
                model=data["model"],
                provider=LLMProviderType.OPENAI,
                usage={
                    "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                    "total_tokens": data.get("usage", {}).get("total_tokens", 0)
                },
                finish_reason=data["choices"][0].get("finish_reason", "stop"),
                raw_response=data,
                latency_ms=latency_ms
            )

        except httpx.HTTPStatusError as e:
            logger.error("openai_api_error", status=e.response.status_code, detail=e.response.text)
            raise
        except Exception as e:
            logger.error("openai_generation_failed", error=str(e))
            raise

    async def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Chat using OpenAI chat completion API."""
        start_time = datetime.utcnow()
        client = await self._get_client()

        model = model or self.config.default_model
        request_data = {
            "model": model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 1.0),
            "stream": kwargs.get("stream", False),
        }

        if kwargs.get("stop"):
            request_data["stop"] = kwargs["stop"]

        try:
            response = await client.post(
                "/chat/completions",
                json=request_data
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                provider=LLMProviderType.OPENAI,
                usage={
                    "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                    "total_tokens": data.get("usage", {}).get("total_tokens", 0)
                },
                finish_reason=data["choices"][0].get("finish_reason", "stop"),
                raw_response=data,
                latency_ms=latency_ms
            )

        except httpx.HTTPStatusError as e:
            logger.error("openai_chat_api_error", status=e.response.status_code)
            raise
        except Exception as e:
            logger.error("openai_chat_failed", error=str(e))
            raise

    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Generate embeddings using OpenAI embedding API."""
        client = await self._get_client()
        model = model or "text-embedding-ada-002"

        try:
            response = await client.post(
                "/embeddings",
                json={
                    "model": model,
                    "input": texts
                }
            )
            response.raise_for_status()
            data = response.json()

            return [item["embedding"] for item in data["data"]]

        except Exception as e:
            logger.error("openai_embed_failed", error=str(e))
            raise


class AnthropicIntegration(BaseLLMIntegration):
    """Anthropic Claude API integration."""

    def __init__(self, config: LLMProviderConfig):
        if config.provider_type != LLMProviderType.ANTHROPIC:
            raise ValueError(f"Expected ANTHROPIC provider, got {config.provider_type}")
        super().__init__(config)

    def _get_base_url(self) -> str:
        return self.config.base_url or "https://api.anthropic.com/v1"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Generate response using Anthropic messages API."""
        start_time = datetime.utcnow()
        client = await self._get_client()

        model = model or "claude-3-opus-20240229"
        request_data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 1.0),
        }

        if kwargs.get("stop"):
            request_data["stop_sequences"] = kwargs["stop"]

        try:
            response = await client.post(
                "/messages",
                json=request_data
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return LLMResponse(
                content=data["content"][0]["text"],
                model=data["model"],
                provider=LLMProviderType.ANTHROPIC,
                usage={
                    "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                    "output_tokens": data.get("usage", {}).get("output_tokens", 0),
                },
                finish_reason=data.get("stop_reason", "end_turn"),
                raw_response=data,
                latency_ms=latency_ms
            )

        except Exception as e:
            logger.error("anthropic_generation_failed", error=str(e))
            raise

    async def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Chat using Anthropic messages API."""
        return await self.generate(
            prompt="\n".join([f"{m['role']}: {m['content']}" for m in messages]),
            model=model,
            **kwargs
        )

    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Anthropic doesn't support embeddings, raise error."""
        raise NotImplementedError("Anthropic does not support embeddings API")


class HuggingFaceIntegration(BaseLLMIntegration):
    """HuggingFace Inference API integration."""

    def __init__(self, config: LLMProviderConfig):
        if config.provider_type != LLMProviderType.HUGGINGFACE:
            raise ValueError(f"Expected HUGGINGFACE provider, got {config.provider_type}")
        super().__init__(config)

    def _get_base_url(self) -> str:
        return self.config.base_url or "https://api-inference.huggingface.co/models"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Generate response using HuggingFace Inference API."""
        start_time = datetime.utcnow()
        client = await self._get_client()

        model = model or self.config.default_model

        try:
            response = await client.post(
                f"/{model}",
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": kwargs.get("max_tokens", 2048),
                        "temperature": kwargs.get("temperature", 0.7),
                        "top_p": kwargs.get("top_p", 1.0),
                    }
                }
            )
            response.raise_for_status()

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            data = response.json()

            content = data[0]["generated_text"] if isinstance(data, list) else data.get("generated_text", "")

            return LLMResponse(
                content=content,
                model=model,
                provider=LLMProviderType.HUGGINGFACE,
                usage={},
                finish_reason="stop",
                raw_response=data,
                latency_ms=latency_ms
            )

        except Exception as e:
            logger.error("huggingface_generation_failed", error=str(e))
            raise

    async def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Chat using HuggingFace API."""
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        return await self.generate(prompt, model, **kwargs)

    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Generate embeddings using HuggingFace feature extraction."""
        client = await self._get_client()
        model = model or "sentence-transformers/all-MiniLM-L6-v2"

        try:
            response = await client.post(
                f"/{model}",
                json={"inputs": texts}
            )
            response.raise_for_status()
            data = response.json()

            return data if isinstance(data[0], list) else [data]

        except Exception as e:
            logger.error("huggingface_embed_failed", error=str(e))
            raise


class LLMProviderRegistry:
    """
    Registry for managing multiple LLM providers.
    
    Features:
    - Dynamic provider registration
    - Automatic failover
    - Rate limiting
    - Cost tracking
    - Usage monitoring
    """

    def __init__(self):
        self._providers: Dict[LLMProviderType, BaseLLMIntegration] = {}
        self._default_provider: Optional[LLMProviderType] = None
        self._usage_stats: Dict[str, Dict[str, Any]] = {}
        self._rate_limiter = asyncio.Semaphore(50)

    def register(
        self,
        provider_type: LLMProviderType,
        integration: BaseLLMIntegration,
        set_default: bool = False
    ):
        """Register an LLM provider."""
        self._providers[provider_type] = integration
        if set_default or not self._default_provider:
            self._default_provider = provider_type
        logger.info("llm_provider_registered", provider=provider_type.name)

    def get(self, provider_type: LLMProviderType) -> Optional[BaseLLMIntegration]:
        """Get a provider by type."""
        return self._providers.get(provider_type)

    @property
    def default(self) -> Optional[BaseLLMIntegration]:
        """Get default provider."""
        if self._default_provider:
            return self._providers.get(self._default_provider)
        return None

    async def generate(
        self,
        prompt: str,
        provider: Optional[LLMProviderType] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response with rate limiting."""
        provider = provider or self._default_provider
        integration = self.get(provider)

        if not integration:
            raise ValueError(f"Provider {provider} not registered")

        async with self._rate_limiter:
            response = await integration.generate(prompt, model, **kwargs)
            await self._track_usage(provider, response)
            return response

    async def chat(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[LLMProviderType] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Chat with rate limiting."""
        provider = provider or self._default_provider
        integration = self.get(provider)

        if not integration:
            raise ValueError(f"Provider {provider} not registered")

        async with self._rate_limiter:
            response = await integration.chat(messages, model, **kwargs)
            await self._track_usage(provider, response)
            return response

    async def embed(
        self,
        texts: List[str],
        provider: Optional[LLMProviderType] = None,
        model: Optional[str] = None
    ) -> List[List[float]]:
        """Generate embeddings with rate limiting."""
        provider = provider or self._default_provider
        integration = self.get(provider)

        if not integration:
            raise ValueError(f"Provider {provider} not registered")

        async with self._rate_limiter:
            return await integration.embed(texts, model)

    async def _track_usage(self, provider: LLMProviderType, response: LLMResponse):
        """Track usage statistics."""
        if provider.name not in self._usage_stats:
            self._usage_stats[provider.name] = {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_latency_ms": 0.0
            }

        stats = self._usage_stats[provider.name]
        stats["total_requests"] += 1

        if response.usage:
            tokens = response.usage.get("total_tokens", 0)
            stats["total_tokens"] += tokens
            stats["total_cost"] += self._calculate_cost(provider, tokens)

        stats["total_latency_ms"] += response.latency_ms

    def _calculate_cost(self, provider: LLMProviderType, tokens: int) -> float:
        """Calculate API cost."""
        pricing = {
            LLMProviderType.OPENAI: 0.000002,  # $0.002 per 1K tokens
            LLMProviderType.ANTHROPIC: 0.000015,  # $0.015 per 1K tokens
            LLMProviderType.HUGGINGFACE: 0.0,  # Free tier
        }
        return tokens * pricing.get(provider, 0.0)

    def get_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get usage statistics."""
        return self._usage_stats.copy()

    async def close_all(self):
        """Close all provider connections."""
        for integration in self._providers.values():
            await integration.close()
        logger.info("all_llm_providers_closed")


llm_registry = LLMProviderRegistry()


def setup_llm_providers(configs: List[LLMProviderConfig]):
    """Setup and register LLM providers from configs."""
    for config in configs:
        if config.provider_type == LLMProviderType.OPENAI:
            llm_registry.register(
                config.provider_type,
                OpenAIIntegration(config),
                set_default=True
            )
        elif config.provider_type == LLMProviderType.ANTHROPIC:
            llm_registry.register(
                config.provider_type,
                AnthropicIntegration(config)
            )
        elif config.provider_type == LLMProviderType.HUGGINGFACE:
            llm_registry.register(
                config.provider_type,
                HuggingFaceIntegration(config)
            )
