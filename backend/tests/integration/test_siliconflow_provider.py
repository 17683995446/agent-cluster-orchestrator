"""
Phase 1: 深度测试体系完善
Integration Tests for SiliconFlow Provider
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import httpx

from app.llm.siliconflow_provider import (
    SiliconFlowProvider,
    SiliconFlowModel,
    init_siliconflow_provider,
    SiliconFlowProviderConfig
)


class TestSiliconFlowProvider:
    """Tests for SiliconFlowProvider."""

    @pytest.fixture
    def provider(self):
        """Create provider with test API key."""
        return SiliconFlowProvider(
            api_key="test-api-key",
            default_model=SiliconFlowModel.QWEN_7B.value
        )

    def test_initialization(self, provider):
        """Test provider initialization."""
        assert provider.api_key == "test-api-key"
        assert provider.default_model == SiliconFlowModel.QWEN_7B.value
        assert provider.base_url == "https://api.siliconflow.cn/v1"
        assert provider.timeout == 120.0

    def test_is_available(self, provider):
        """Test is_available check."""
        assert provider.is_available() is True

    def test_is_available_without_key(self):
        """Test is_available with empty API key."""
        provider = SiliconFlowProvider(api_key="")
        assert provider.is_available() is False

    def test_get_headers(self, provider):
        """Test request headers generation."""
        headers = provider._get_headers()
        assert headers["Authorization"] == "Bearer test-api-key"
        assert headers["Content-Type"] == "application/json"

    def test_get_available_models(self, provider):
        """Test getting available models."""
        models = provider.get_available_models()
        assert len(models) == 6
        assert SiliconFlowModel.QWEN_7B.value in models
        assert SiliconFlowModel.DEEPSEEK_V25.value in models

    def test_get_model_info(self, provider):
        """Test getting model information."""
        info = provider.get_model_info(SiliconFlowModel.QWEN_7B.value)
        assert info["name"] == "Qwen 2.5 7B"
        assert info["provider"] == "Alibaba"
        assert info["max_tokens"] == 8192

    def test_get_model_info_unknown(self, provider):
        """Test getting info for unknown model."""
        info = provider.get_model_info("unknown-model")
        assert info["name"] == "Unknown"


class TestSiliconFlowGenerate:
    """Tests for SiliconFlow generate method."""

    @pytest.fixture
    def provider(self):
        """Create provider with test API key."""
        return SiliconFlowProvider(
            api_key="test-api-key",
            default_model=SiliconFlowModel.QWEN_7B.value
        )

    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        """Test successful generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Test response content"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            response = await provider.generate("Test prompt")

            assert response.content == "Test response content"
            assert response.model == SiliconFlowModel.QWEN_7B.value
            assert response.provider == "siliconflow"
            assert response.usage["total_tokens"] == 30
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_with_custom_model(self, provider):
        """Test generation with custom model."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Response"},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 10}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            response = await provider.generate(
                "Test prompt",
                model=SiliconFlowModel.DEEPSEEK_V25.value
            )

            assert response.model == SiliconFlowModel.DEEPSEEK_V25.value
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["model"] == SiliconFlowModel.DEEPSEEK_V25.value

    @pytest.mark.asyncio
    async def test_generate_with_parameters(self, provider):
        """Test generation with custom parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Response"},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 10}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            response = await provider.generate(
                "Test prompt",
                max_tokens=1000,
                temperature=0.5,
                top_p=0.8
            )

            call_args = mock_client.post.call_args
            request_data = call_args[1]["json"]
            assert request_data["max_tokens"] == 1000
            assert request_data["temperature"] == 0.5
            assert request_data["top_p"] == 0.8

    @pytest.mark.asyncio
    async def test_generate_api_error(self, provider):
        """Test handling API errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        def raise_error():
            raise httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response
            )
        
        mock_response.raise_for_status = raise_error

        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await provider.generate("Test prompt")
            
            assert "401" in str(exc_info.value)


class TestSiliconFlowChat:
    """Tests for SiliconFlow chat method."""

    @pytest.fixture
    def provider(self):
        """Create provider with test API key."""
        return SiliconFlowProvider(
            api_key="test-api-key",
            default_model=SiliconFlowModel.QWEN_7B.value
        )

    @pytest.mark.asyncio
    async def test_chat_success(self, provider):
        """Test successful chat."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Hello! How can I help you?"},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 50}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            response = await provider.chat(messages)

            assert response.content == "Hello! How can I help you?"
            assert response.provider == "siliconflow"
            
            call_args = mock_client.post.call_args
            request_data = call_args[1]["json"]
            assert request_data["messages"] == messages


class TestSiliconFlowEmbed:
    """Tests for SiliconFlow embed method."""

    @pytest.fixture
    def provider(self):
        """Create provider with test API key."""
        return SiliconFlowProvider(
            api_key="test-api-key",
            default_model=SiliconFlowModel.QWEN_7B.value
        )

    @pytest.mark.asyncio
    async def test_embed_success(self, provider):
        """Test successful embedding."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            embeddings = await provider.embed(["text1", "text2"])

            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2, 0.3]
            assert embeddings[1] == [0.4, 0.5, 0.6]


class TestSiliconFlowConnection:
    """Tests for connection testing."""

    @pytest.fixture
    def provider(self):
        """Create provider with test API key."""
        return SiliconFlowProvider(
            api_key="test-api-key",
            default_model=SiliconFlowModel.QWEN_7B.value
        )

    @pytest.mark.asyncio
    async def test_connection_success(self, provider):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "连接成功"},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 10}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await provider.test_connection()

            assert result["success"] is True
            assert result["provider"] == "siliconflow"
            assert result["response"] == "连接成功"

    @pytest.mark.asyncio
    async def test_connection_failure(self, provider):
        """Test failed connection test."""
        with patch.object(provider, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection failed")
            mock_get_client.return_value = mock_client

            result = await provider.test_connection()

            assert result["success"] is False
            assert "Connection failed" in result["error"]


class TestSiliconFlowGlobalProvider:
    """Tests for global provider management."""

    def test_init_siliconflow_provider(self):
        """Test initializing global provider."""
        from app.llm.siliconflow_provider import _siliconflow_provider
        
        provider = init_siliconflow_provider(
            api_key="global-test-key",
            default_model=SiliconFlowModel.GLM4_9B.value
        )

        assert provider.api_key == "global-test-key"
        assert provider.default_model == SiliconFlowModel.GLM4_9B.value

    def test_is_siliconflow_available(self):
        """Test checking SiliconFlow availability."""
        from app.llm.siliconflow_provider import is_siliconflow_available
        
        init_siliconflow_provider(api_key="test-key")
        assert is_siliconflow_available() is True


class TestSiliconFlowModels:
    """Tests for SiliconFlow model enum."""

    def test_all_models_defined(self):
        """Test all expected models are defined."""
        assert SiliconFlowModel.QWEN_7B.value == "Qwen/Qwen2.5-7B-Instruct"
        assert SiliconFlowModel.DEEPSEEK_V25.value == "deepseek-ai/DeepSeek-V2.5"
        assert SiliconFlowModel.GLM4_9B.value == "THUDM/glm-4-9b-chat"
        assert SiliconFlowModel.BAICHUAN_7B.value == "baichuan-inc/Baichuan2-7B-Chat"
        assert SiliconFlowModel.MISTRAL_7B.value == "mistralai/Mistral-7B-Instruct-v0.3"
        assert SiliconFlowModel.LLAMA3_8B.value == "meta-llama/Llama-3-8B-Instruct"

    def test_model_count(self):
        """Test total number of models."""
        assert len(SiliconFlowModel) == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
