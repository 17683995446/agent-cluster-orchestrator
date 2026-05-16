from typing import Dict, Any, Optional, List
import os
from app.llm.base_llm_provider_interface import BaseLLMProvider
from app.core.custom_exceptions_handler import LLMProviderError
import structlog

logger = structlog.get_logger()

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        from openai import AsyncOpenAI
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def generate(self, prompt: str, model: str = "gpt-4", **kwargs) -> Dict[str, Any]:
        if not self.is_available():
            raise LLMProviderError("openai", "API key not configured")
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "model": model,
                "provider": "openai"
            }
        except Exception as e:
            logger.error("openai_generate_error", error=str(e))
            raise LLMProviderError("openai", str(e))
    
    async def chat(self, messages: List[Dict[str, str]], model: str = "gpt-4", **kwargs) -> Dict[str, Any]:
        if not self.is_available():
            raise LLMProviderError("openai", "API key not configured")
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "model": model,
                "provider": "openai"
            }
        except Exception as e:
            logger.error("openai_chat_error", error=str(e))
            raise LLMProviderError("openai", str(e))
