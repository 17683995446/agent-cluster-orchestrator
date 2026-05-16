from typing import Dict, Optional, List
from app.llm.base_llm_provider_interface import BaseLLMProvider
from app.llm.openai_llm_provider import OpenAIProvider
from app.llm.anthropic_llm_provider import AnthropicProvider
from app.llm.siliconflow_provider import SiliconFlowProvider, init_siliconflow_provider, SiliconFlowModel
from app.core.custom_exceptions_handler import LLMProviderError
import structlog

logger = structlog.get_logger()


class LLMResponse:
    """Standard LLM response format."""
    def __init__(
        self,
        content: str,
        model: str,
        provider: str,
        usage: Dict[str, int],
        finish_reason: str = "stop",
        latency_ms: float = 0.0,
        raw_response: Optional[Dict] = None
    ):
        self.content = content
        self.model = model
        self.provider = provider
        self.usage = usage
        self.finish_reason = finish_reason
        self.latency_ms = latency_ms
        self.raw_response = raw_response or {}

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage,
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms
        }


class LLMManager:
    """Manages multiple LLM providers."""
    
    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
        self._init_providers()
    
    def _init_providers(self):
        """Initialize available providers."""
        openai = OpenAIProvider()
        if openai.is_available():
            self.providers["openai"] = openai
            logger.info("provider_registered", provider="openai")
        
        anthropic = AnthropicProvider()
        if anthropic.is_available():
            self.providers["anthropic"] = anthropic
            logger.info("provider_registered", provider="anthropic")
        
        if not self.providers:
            logger.warning("no_llm_providers_available")
    
    def register_siliconflow(self, api_key: str, default_model: str = SiliconFlowModel.QWEN_7B.value):
        """Register SiliconFlow provider."""
        provider = init_siliconflow_provider(api_key, default_model)
        self.providers["siliconflow"] = provider
        logger.info("provider_registered", provider="siliconflow", model=default_model)
    
    def get_provider(self, name: str) -> Optional[BaseLLMProvider]:
        """Get provider by name."""
        return self.providers.get(name)
    
    def list_providers(self) -> List[str]:
        """List available provider names."""
        return list(self.providers.keys())
    
    async def generate(
        self,
        prompt: str,
        provider: str,
        model: str,
        **kwargs
    ) -> Dict:
        """Generate content using specified provider."""
        provider_obj = self.get_provider(provider)
        if not provider_obj:
            raise LLMProviderError(provider, f"Provider '{provider}' not available")
        
        return await provider_obj.generate(prompt, model, **kwargs)
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        provider: str,
        model: str,
        **kwargs
    ) -> Dict:
        """Chat using specified provider."""
        provider_obj = self.get_provider(provider)
        if not provider_obj:
            raise LLMProviderError(provider, f"Provider '{provider}' not available")
        
        return await provider_obj.chat(messages, model, **kwargs)


llm_manager = LLMManager()
