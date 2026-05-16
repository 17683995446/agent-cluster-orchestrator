from typing import Dict, Any, Optional, List
import os
from app.llm.base_llm_provider_interface import BaseLLMProvider
from app.core.custom_exceptions_handler import LLMProviderError
import structlog

logger = structlog.get_logger()

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        from anthropic import AsyncAnthropic
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = AsyncAnthropic(api_key=self.api_key)
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Convert messages to Anthropic format."""
        if not messages:
            return ""
        
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            else:
                parts.append(f"Human: {content}" if role == "user" else f"Assistant: {content}")
        
        return "\n\n".join(parts)
    
    async def generate(self, prompt: str, model: str = "claude-3-5-sonnet-20241022", **kwargs) -> Dict[str, Any]:
        if not self.is_available():
            raise LLMProviderError("anthropic", "API key not configured")
        
        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=kwargs.get("max_tokens", 1024),
                messages=[{"role": "user", "content": prompt}]
            )
            return {
                "content": response.content[0].text,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                },
                "model": model,
                "provider": "anthropic"
            }
        except Exception as e:
            logger.error("anthropic_generate_error", error=str(e))
            raise LLMProviderError("anthropic", str(e))
    
    async def chat(self, messages: List[Dict[str, str]], model: str = "claude-3-5-sonnet-20241022", **kwargs) -> Dict[str, Any]:
        if not self.is_available():
            raise LLMProviderError("anthropic", "API key not configured")
        
        formatted = self._format_messages(messages)
        return await self.generate(formatted, model, **kwargs)
