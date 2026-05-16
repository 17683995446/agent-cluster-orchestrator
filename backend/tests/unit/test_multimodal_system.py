"""
多模态系统测试
"""
import pytest
import asyncio
from datetime import datetime
from typing import List, Dict, Any

from app.services.multimodal_system import (
    ModalityType,
    TextData,
    ImageData,
    AudioData,
    EmbeddingData,
    RealEmbeddingModel,
    RealDifferentialPrivacy,
    MultiModalEngine,
    MultiModalAgent
)


# ============== Fixtures ==============

@pytest.fixture
def embedding_model():
    """嵌入模型fixture"""
    return RealEmbeddingModel(model_name="all-MiniLM-L6-v2")


@pytest.fixture
def dp_engine():
    """差分隐私引擎fixture"""
    return RealDifferentialPrivacy(epsilon=1.0, delta=1e-5)


@pytest.fixture
def multimodal_engine(embedding_model, dp_engine):
    """多模态引擎fixture"""
    return MultiModalEngine(
        embedding_model=embedding_model,
        dp_config={"epsilon": 1.0, "delta": 1e-5}
    )


@pytest.fixture
def sample_texts():
    """样本文本"""
    return [
        "Hello, world!",
        "This is a test sentence.",
        "Machine learning is amazing.",
        "Natural language processing is fun.",
        "Artificial intelligence will change the world."
    ]


# ============== 单元测试：数据类 ==============

class TestModalityData:
    """模态数据测试"""
    
    def test_text_data_creation(self):
        """测试文本数据创建"""
        text = TextData(text="Hello, world!")
        assert text.text == "Hello, world!"
        assert text.modality_type == ModalityType.TEXT
        assert text.language == "en"
        assert text.data_id is not None
    
    def test_text_data_chinese(self):
        """测试中文文本"""
        text = TextData(text="你好，世界！")
        assert text.language == "zh"
    
    def test_image_data_creation(self):
        """测试图像数据创建"""
        image_data = b"fake_image_data"
        image = ImageData(image_data=image_data)
        assert image.image_data == image_data
        assert image.modality_type == ModalityType.IMAGE
        assert image.data_id is not None
    
    def test_audio_data_creation(self):
        """测试音频数据创建"""
        audio_data = b"fake_audio_data"
        audio = AudioData(audio_data=audio_data)
        assert audio.audio_data == audio_data
        assert audio.modality_type == ModalityType.AUDIO
    
    def test_embedding_data_creation(self):
        """测试嵌入数据创建"""
        vector = [0.1, 0.2, 0.3, 0.4]
        embedding = EmbeddingData(vector=vector)
        assert embedding.vector == vector
        assert embedding.dimension == 4
        assert embedding.modality_type == ModalityType.EMBEDDING
    
    def test_modality_data_to_dict(self):
        """测试数据转换为字典"""
        text = TextData(text="Test")
        data_dict = text.to_dict()
        
        assert "data_id" in data_dict
        assert "modality_type" in data_dict
        assert data_dict["modality_type"] == "text"


# ============== 单元测试：差分隐私 ==============

class TestDifferentialPrivacy:
    """差分隐私测试"""
    
    def test_laplace_noise(self, dp_engine):
        """测试拉普拉斯噪声"""
        import numpy as np
        
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        original_sum = np.sum(data)
        
        noisy_data = dp_engine.add_laplace_noise(data, sensitivity=1.0)
        
        assert noisy_data.shape == data.shape
        # 噪声后的数据应该与原始数据有差异
        assert not np.allclose(noisy_data, data)
    
    def test_gaussian_noise(self, dp_engine):
        """测试高斯噪声"""
        import numpy as np
        
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        
        noisy_data = dp_engine.add_gaussian_noise(data, sensitivity=1.0)
        
        assert noisy_data.shape == data.shape
        assert not np.allclose(noisy_data, data)
    
    def test_privacy_preserves_distribution(self, dp_engine):
        """测试隐私保护保持分布"""
        import numpy as np
        
        # 多次运行验证统计特性
        means = []
        for _ in range(100):
            data = np.array([1.0, 2.0, 3.0])
            noisy_data = dp_engine.add_laplace_noise(data, sensitivity=1.0)
            means.append(np.mean(noisy_data))
        
        # 均值应该在合理范围内
        assert all(-10 < m < 10 for m in means)


# ============== 集成测试：嵌入模型 ==============

@pytest.mark.asyncio
class TestEmbeddingModel:
    """嵌入模型测试"""
    
    async def test_text_embedding(self, embedding_model):
        """测试文本嵌入"""
        text = "Hello, world!"
        embedding = await embedding_model.embed_text(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, (int, float)) for x in embedding)
    
    async def test_batch_embedding(self, embedding_model, sample_texts):
        """测试批量嵌入"""
        embeddings = await embedding_model.embed_batch(sample_texts)
        
        assert len(embeddings) == len(sample_texts)
        assert all(len(emb) == len(embeddings[0]) for emb in embeddings)
    
    async def test_embedding_consistency(self, embedding_model):
        """测试嵌入一致性"""
        text = "Consistency test"
        
        emb1 = await embedding_model.embed_text(text)
        emb2 = await embedding_model.embed_text(text)
        
        # 相同的文本应该产生相似的嵌入
        import numpy as np
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        assert similarity > 0.99
    
    async def test_image_embedding(self, embedding_model):
        """测试图像嵌入"""
        image_data = b"fake_image_content_for_testing"
        image = ImageData(image_data=image_data)
        
        embedding = await embedding_model.embed_image(image)
        
        assert isinstance(embedding, list)
        assert len(embedding) > 0


# ============== 集成测试：多模态引擎 ==============

@pytest.mark.asyncio
class TestMultiModalEngine:
    """多模态引擎测试"""
    
    async def test_embed_text(self, multimodal_engine):
        """测试文本嵌入"""
        text = TextData(text="Test text for embedding")
        embedding = await multimodal_engine.embed(text)
        
        assert isinstance(embedding, EmbeddingData)
        assert embedding.dimension > 0
        assert embedding.metadata["source_type"] == "text"
    
    async def test_embed_with_dp(self, multimodal_engine):
        """测试带差分隐私的嵌入"""
        text = TextData(text="Private text")
        
        embedding_without_dp = await multimodal_engine.embed(text, apply_dp=False)
        embedding_with_dp = await multimodal_engine.embed(text, apply_dp=True)
        
        # 带DP的嵌入应该有噪声
        assert embedding_without_dp.vector != embedding_with_dp.vector
    
    async def test_batch_embed(self, multimodal_engine, sample_texts):
        """测试批量嵌入"""
        texts = [TextData(text=t) for t in sample_texts]
        embeddings = await multimodal_engine.embed_batch(texts)
        
        assert len(embeddings) == len(sample_texts)
        assert all(isinstance(e, EmbeddingData) for e in embeddings)
    
    async def test_index_and_search(self, multimodal_engine):
        """测试索引和搜索"""
        texts = [
            TextData(text="Machine learning algorithms"),
            TextData(text="Deep learning neural networks"),
            TextData(text="Natural language processing")
        ]
        
        # 索引
        for text in texts:
            await multimodal_engine.index(text)
        
        stats = multimodal_engine.get_stats()
        assert stats["total_indexed"] == 3
        
        # 搜索
        results = await multimodal_engine.search("deep neural", top_k=2)
        
        assert len(results) <= 2
        assert all(isinstance(r[0], EmbeddingData) for r in results)
        assert all(isinstance(r[1], float) for r in results)
    
    async def test_search_by_string(self, multimodal_engine):
        """测试字符串搜索"""
        text = TextData(text="Searchable text content")
        await multimodal_engine.index(text)
        
        results = await multimodal_engine.search("search", top_k=1)
        
        assert len(results) >= 0  # 可能没有结果，但不应该报错


# ============== 集成测试：多模态Agent ==============

@pytest.mark.asyncio
class TestMultiModalAgent:
    """多模态Agent测试"""
    
    async def test_agent_initialization(self, multimodal_engine):
        """测试Agent初始化"""
        agent = MultiModalAgent(
            agent_id="test_agent",
            multimodal_engine=multimodal_engine
        )
        
        assert agent.agent_id == "test_agent"
        assert agent.engine == multimodal_engine
        assert len(agent.capabilities) > 0
    
    async def test_process_single_input(self, multimodal_engine):
        """测试处理单个输入"""
        agent = MultiModalAgent(
            agent_id="test_agent",
            multimodal_engine=multimodal_engine
        )
        
        text = TextData(text="Hello, agent!")
        response = await agent.process_input([text])
        
        assert "text" in response
        assert "modality" in response
        assert len(agent.conversation_history) == 1
    
    async def test_process_multiple_inputs(self, multimodal_engine):
        """测试处理多个输入"""
        agent = MultiModalAgent(
            agent_id="test_agent",
            multimodal_engine=multimodal_engine
        )
        
        inputs = [
            TextData(text="First text"),
            TextData(text="Second text")
        ]
        
        response = await agent.process_input(inputs)
        
        assert response["embeddings_generated"] == 2
        assert len(agent.conversation_history) == 1
    
    async def test_conversation_history(self, multimodal_engine):
        """测试对话历史"""
        agent = MultiModalAgent(
            agent_id="test_agent",
            multimodal_engine=multimodal_engine
        )
        
        for i in range(3):
            text = TextData(text=f"Message {i}")
            await agent.process_input([text])
        
        assert len(agent.conversation_history) == 3


# ============== 性能测试 ==============

@pytest.mark.asyncio
class TestPerformance:
    """性能测试"""
    
    @pytest.mark.timeout(30)
    async def test_embedding_speed(self, embedding_model):
        """测试嵌入速度"""
        import time
        
        texts = ["Test text"] * 100
        
        start = time.time()
        for text in texts:
            await embedding_model.embed_text(text)
        elapsed = time.time() - start
        
        # 应该能在合理时间内完成
        assert elapsed < 20, f"Embedding took too long: {elapsed}s"
    
    @pytest.mark.timeout(30)
    async def test_batch_embedding_speed(self, embedding_model):
        """测试批量嵌入速度"""
        import time
        
        texts = ["Test text"] * 100
        
        start = time.time()
        await embedding_model.embed_batch(texts)
        elapsed = time.time() - start
        
        # 批量应该比单独快
        assert elapsed < 10, f"Batch embedding took too long: {elapsed}s"
    
    @pytest.mark.timeout(60)
    async def test_search_speed(self, multimodal_engine):
        """测试搜索速度"""
        import time
        
        # 先索引大量数据
        for i in range(100):
            text = TextData(text=f"Indexed text number {i}")
            await multimodal_engine.index(text)
        
        # 然后搜索
        start = time.time()
        results = await multimodal_engine.search("test", top_k=10)
        elapsed = time.time() - start
        
        assert elapsed < 5, f"Search took too long: {elapsed}s"


# ============== 边界测试 ==============

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_text(self, embedding_model):
        """测试空文本"""
        import asyncio
        
        async def test():
            embedding = await embedding_model.embed_text("")
            return len(embedding) > 0
        
        result = asyncio.get_event_loop().run_until_complete(test())
        assert result
    
    def test_very_long_text(self, embedding_model):
        """测试非常长的文本"""
        import asyncio
        
        async def test():
            long_text = "word " * 10000
            embedding = await embedding_model.embed_text(long_text)
            return len(embedding) > 0
        
        result = asyncio.get_event_loop().run_until_complete(test())
        assert result
    
    def test_special_characters(self, embedding_model):
        """测试特殊字符"""
        import asyncio
        
        async def test():
            special_text = "!@#$%^&*()_+-=[]{}|;':\",./<>?\\`~\n\t"
            embedding = await embedding_model.embed_text(special_text)
            return len(embedding) > 0
        
        result = asyncio.get_event_loop().run_until_complete(test())
        assert result


# ============== 运行测试 ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.multimodal_system"])
