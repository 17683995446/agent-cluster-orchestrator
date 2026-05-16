"""
SiliconFlow LLM Provider Integration
Free LLM models from SiliconFlow platform.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.llm.base_llm_provider_interface import BaseLLMProvider
from app.llm.llm_provider_manager import LLMResponse

logger = structlog.get_logger()


class SiliconFlowModel(Enum):
    """Available SiliconFlow models."""
    QWEN_7B = "Qwen/Qwen2.5-7B-Instruct"
    DEEPSEEK_V25 = "deepseek-ai/DeepSeek-V2.5"
    GLM4_9B = "THUDM/glm-4-9b-chat"
    BAICHUAN_7B = "baichuan-inc/Baichuan2-7B-Chat"
    MISTRAL_7B = "mistralai/Mistral-7B-Instruct-v0.3"
    LLAMA3_8B = "meta-llama/Llama-3-8B-Instruct"


@dataclass
class SiliconFlowProviderConfig:
    """SiliconFlow provider configuration."""
    api_key: str
    base_url: str = "https://api.siliconflow.cn/v1"
    default_model: str = SiliconFlowModel.QWEN_7B.value
    timeout: float = 120.0
    max_retries: int = 3


class SiliconFlowProvider(BaseLLMProvider):
    """
    SiliconFlow API provider.
    
    SiliconFlow provides free access to multiple open-source LLM models.
    
    Available Models:
    - Qwen/Qwen2.5-7B-Instruct (通义千问)
    - deepseek-ai/DeepSeek-V2.5 (深度求索)
    - THUDM/glm-4-9b-chat (智谱GLM-4)
    - baichuan-inc/Baichuan2-7B-Chat (百川)
    - mistralai/Mistral-7B-Instruct-v0.3
    - meta-llama/Llama-3-8B-Instruct
    
    Features:
    - Multiple open-source models
    - Chat completion API
    - Embeddings support
    - Streaming responses
    """
    
    def __init__(
        self,
        api_key: str,
        default_model: str = SiliconFlowModel.QWEN_7B.value,
        base_url: str = "https://api.siliconflow.cn/v1",
        timeout: float = 120.0
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(
            "siliconflow_provider_initialized",
            default_model=self.default_model,
            base_url=self.base_url
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=httpx.Timeout(self.timeout)
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def is_available(self) -> bool:
        """Check if provider is available (has API key)."""
        return bool(self.api_key and len(self.api_key) > 0)
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using SiliconFlow chat API.
        
        Args:
            prompt: Input prompt text
            model: Model ID (defaults to self.default_model)
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with generated content
        """
        start_time = datetime.utcnow()
        model = model or self.default_model
        client = await self._get_client()
        
        messages = [{"role": "user", "content": prompt}]
        
        request_data = {
            "model": model,
            "messages": messages,
            "stream": False,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
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
            
            content = data["choices"][0]["message"]["content"]
            finish_reason = data["choices"][0].get("finish_reason", "stop")
            
            usage = data.get("usage", {})
            
            logger.info(
                "siliconflow_generation_success",
                model=model,
                latency_ms=latency_ms,
                tokens_used=usage.get("total_tokens", 0)
            )
            
            return LLMResponse(
                content=content,
                model=model,
                provider="siliconflow",
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                },
                finish_reason=finish_reason,
                latency_ms=latency_ms,
                raw_response=data
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"SiliconFlow API error: {e.response.status_code} - {e.response.text}"
            logger.error(
                "siliconflow_api_error",
                status=e.response.status_code,
                detail=e.response.text
            )
            raise Exception(error_msg)
            
        except Exception as e:
            error_msg = f"SiliconFlow generation failed: {str(e)}"
            logger.error(
                "siliconflow_generation_failed",
                error=str(e)
            )
            raise
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Chat completion using SiliconFlow API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model ID (defaults to self.default_model)
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with generated content
        """
        start_time = datetime.utcnow()
        model = model or self.default_model
        client = await self._get_client()
        
        request_data = {
            "model": model,
            "messages": messages,
            "stream": False,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
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
            
            content = data["choices"][0]["message"]["content"]
            finish_reason = data["choices"][0].get("finish_reason", "stop")
            
            usage = data.get("usage", {})
            
            logger.info(
                "siliconflow_chat_success",
                model=model,
                latency_ms=latency_ms,
                tokens_used=usage.get("total_tokens", 0)
            )
            
            return LLMResponse(
                content=content,
                model=model,
                provider="siliconflow",
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                },
                finish_reason=finish_reason,
                latency_ms=latency_ms,
                raw_response=data
            )
            
        except Exception as e:
            error_msg = f"SiliconFlow chat failed: {str(e)}"
            logger.error(
                "siliconflow_chat_failed",
                error=str(e)
            )
            raise
    
    async def embed(
        self,
        texts: List[str],
        model: str = "BAAI/bge-m3"
    ) -> List[List[float]]:
        """
        Generate embeddings using SiliconFlow API.
        
        Args:
            texts: List of input texts
            model: Embedding model ID
            
        Returns:
            List of embedding vectors
        """
        client = await self._get_client()
        
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
            logger.error(
                "siliconflow_embed_failed",
                error=str(e)
            )
            raise
    
    def get_available_models(self) -> List[str]:
        """Get list of available model IDs."""
        return [model.value for model in SiliconFlowModel]
    
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get model information."""
        model_map = {
            SiliconFlowModel.QWEN_7B.value: {
                "name": "Qwen 2.5 7B",
                "provider": "Alibaba",
                "description": "通义千问2.5 7B指令模型",
                "max_tokens": 8192
            },
            SiliconFlowModel.DEEPSEEK_V25.value: {
                "name": "DeepSeek V2.5",
                "provider": "DeepSeek",
                "description": "深度求索V2.5模型",
                "max_tokens": 8192
            },
            SiliconFlowModel.GLM4_9B.value: {
                "name": "GLM-4 9B",
                "provider": "Zhipu AI",
                "description": "智谱GLM-4 9B模型",
                "max_tokens": 8192
            },
            SiliconFlowModel.BAICHUAN_7B.value: {
                "name": "Baichuan 2 7B",
                "provider": "Baichuan AI",
                "description": "百川智能Chat模型",
                "max_tokens": 4096
            },
            SiliconFlowModel.MISTRAL_7B.value: {
                "name": "Mistral 7B",
                "provider": "Mistral AI",
                "description": "Mistral 7B指令模型",
                "max_tokens": 8192
            },
            SiliconFlowModel.LLAMA3_8B.value: {
                "name": "Llama 3 8B",
                "provider": "Meta",
                "description": "Meta Llama 3 8B指令模型",
                "max_tokens": 8192
            }
        }
        return model_map.get(model_id, {"name": "Unknown", "description": ""})
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test API connection with a simple request.
        
        Returns:
            Dict with test results
        """
        try:
            test_prompt = "请回复'连接成功'，以确认API正常工作。"
            
            response = await self.generate(
                prompt=test_prompt,
                max_tokens=50,
                temperature=0.1
            )
            
            return {
                "success": True,
                "model": response.model,
                "response": response.content,
                "latency_ms": response.latency_ms,
                "provider": "siliconflow"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": "siliconflow"
            }


# Global SiliconFlow provider instance
_siliconflow_provider: Optional[SiliconFlowProvider] = None


def get_siliconflow_provider() -> SiliconFlowProvider:
    """Get or create global SiliconFlow provider."""
    global _siliconflow_provider
    if _siliconflow_provider is None:
        raise ValueError(
            "SiliconFlow provider not initialized. "
            "Call init_siliconflow_provider(api_key) first."
        )
    return _siliconflow_provider


def init_siliconflow_provider(
    api_key: str,
    default_model: str = SiliconFlowModel.QWEN_7B.value
) -> SiliconFlowProvider:
    """
    Initialize global SiliconFlow provider.
    
    Args:
        api_key: SiliconFlow API key
        default_model: Default model to use
        
    Returns:
        Initialized SiliconFlowProvider
    """
    global _siliconflow_provider
    
    _siliconflow_provider = SiliconFlowProvider(
        api_key=api_key,
        default_model=default_model
    )
    
    logger.info(
        "siliconflow_provider_registered",
        default_model=default_model
    )
    
    return _siliconflow_provider


def is_siliconflow_available() -> bool:
    """Check if SiliconFlow provider is available."""
    global _siliconflow_provider
    return _siliconflow_provider is not None and _siliconflow_provider.is_available()
