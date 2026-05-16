from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Generate content from a prompt."""
        pass
    
    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Chat completion."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and configured."""
        pass
