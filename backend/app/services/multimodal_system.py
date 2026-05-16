"""
Phase 1: 多模态智能系统 - 使用真实开源工具优化

使用sentence-transformers进行真实嵌入，diffprivlib进行差分隐私
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4
import structlog
import numpy as np

# 使用真实的开源工具
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

try:
    from diffprivlib.mechanisms import Gaussian, Laplace
    HAS_DIFFPRIVLIB = True
except ImportError:
    HAS_DIFFPRIVLIB = False

from app.core.structured_logging_config import get_structured_logger

logger = get_structured_logger(__name__)


# ============== 模态类型定义 ==============

class ModalityType(str, Enum):
    """模态类型"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TABULAR = "tabular"
    EMBEDDING = "embedding"


class ImageFormat(str, Enum):
    """图像格式"""
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    WEBP = "webp"


class AudioFormat(str, Enum):
    """音频格式"""
    MP3 = "mp3"
    WAV = "wav"
    FLAC = "flac"
    OGG = "ogg"
    AAC = "aac"


# ============== 数据类定义 ==============

@dataclass
class ModalityData:
    """基础模态数据"""
    modality_type: ModalityType
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data_id: str = field(default_factory=lambda: str(uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_id": self.data_id,
            "modality_type": self.modality_type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class TextData(ModalityData):
    """文本数据"""
    text: str = ""
    language: Optional[str] = None
    tokens: Optional[List[int]] = None
    
    def __init__(self, text: str, **kwargs):
        super().__init__(modality_type=ModalityType.TEXT, **kwargs)
        self.text = text
        self.language = self._detect_language()
    
    def _detect_language(self) -> Optional[str]:
        """简单的语言检测"""
        chinese_chars = sum(1 for c in self.text if '\u4e00' <= c <= '\u9fff')
        if chinese_chars / max(len(self.text), 1) > 0.3:
            return "zh"
        return "en"


@dataclass
class ImageData(ModalityData):
    """图像数据"""
    image_data: bytes = b""
    width: int = 0
    height: int = 0
    channels: int = 3
    format: ImageFormat = ImageFormat.PNG
    
    def __init__(self, image_data: bytes, **kwargs):
        super().__init__(modality_type=ModalityType.IMAGE, **kwargs)
        self.image_data = image_data
    
    def to_base64(self) -> str:
        return base64.b64encode(self.image_data).decode('utf-8')


@dataclass
class AudioData(ModalityData):
    """音频数据"""
    audio_data: bytes = b""
    duration: float = 0.0
    sample_rate: int = 16000
    channels: int = 1
    format: AudioFormat = AudioFormat.WAV
    
    def __init__(self, audio_data: bytes, **kwargs):
        super().__init__(modality_type=ModalityType.AUDIO, **kwargs)
        self.audio_data = audio_data
    
    def to_base64(self) -> str:
        return base64.b64encode(self.audio_data).decode('utf-8')


@dataclass
class EmbeddingData(ModalityData):
    """嵌入数据"""
    vector: List[float] = field(default_factory=list)
    dimension: int = 0
    model_name: Optional[str] = None
    
    def __init__(self, vector: List[float], **kwargs):
        super().__init__(modality_type=ModalityType.EMBEDDING, **kwargs)
        self.vector = vector
        self.dimension = len(vector)
    
    def to_numpy(self) -> np.ndarray:
        return np.array(self.vector)


# ============== 使用真实开源工具的嵌入模型 ==============

class RealEmbeddingModel:
    """使用sentence-transformers的真实嵌入模型"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._initialized = False
        
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                self.model = SentenceTransformer(model_name)
                self._initialized = True
                logger.info(f"Real embedding model loaded: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to load model, using fallback: {e}")
                self._initialized = False
        else:
            logger.warning("sentence-transformers not installed, using fallback")
    
    async def embed_text(self, text: str) -> List[float]:
        """文本嵌入"""
        if self._initialized and HAS_SENTENCE_TRANSFORMERS:
            try:
                embedding = self.model.encode(text, convert_to_numpy=True)
                return embedding.tolist()
            except Exception as e:
                logger.error(f"Embedding failed: {e}")
        
        # Fallback: 简单哈希嵌入
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        vector = [rng.gauss(0, 1) for _ in range(384)]
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector]
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入"""
        if self._initialized and HAS_SENTENCE_TRANSFORMERS:
            try:
                embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
        
        return [await self.embed_text(t) for t in texts]
    
    async def embed_image(self, image: ImageData) -> List[float]:
        """图像嵌入（模拟）"""
        # 在实际应用中，可以使用CLIP或其他视觉模型
        seed = int(hashlib.sha256(image.image_data).hexdigest()[:8], 16)
        rng = random.Random(seed)
        vector = [rng.gauss(0, 1) for _ in range(384)]
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector]


# ============== 差分隐私（使用真实库） ==============

class RealDifferentialPrivacy:
    """使用diffprivlib的真实差分隐私"""
    
    def __init__(self, epsilon: float = 1.0, delta: float = 1e-5):
        self.epsilon = epsilon
        self.delta = delta
        self._initialized = HAS_DIFFPRIVLIB
    
    def add_laplace_noise(self, data: np.ndarray, sensitivity: float) -> np.ndarray:
        """添加拉普拉斯噪声"""
        if self._initialized and HAS_DIFFPRIVLIB:
            try:
                mechanism = Laplace(epsilon=self.epsilon, sensitivity=sensitivity)
                noisy_data = np.array([mechanism.randomise(float(x)) for x in data.flatten()])
                return noisy_data.reshape(data.shape)
            except Exception as e:
                logger.warning(f"Laplace mechanism failed: {e}")
        
        # Fallback
        scale = sensitivity / self.epsilon
        noise = np.random.laplace(0, scale, data.shape)
        return data + noise
    
    def add_gaussian_noise(self, data: np.ndarray, sensitivity: float) -> np.ndarray:
        """添加高斯噪声"""
        if self._initialized and HAS_DIFFPRIVLIB:
            try:
                mechanism = Gaussian(epsilon=self.epsilon, delta=self.delta, sensitivity=sensitivity)
                noisy_data = np.array([mechanism.randomise(float(x)) for x in data.flatten()])
                return noisy_data.reshape(data.shape)
            except Exception as e:
                logger.warning(f"Gaussian mechanism failed: {e}")
        
        # Fallback
        scale = sensitivity * math.sqrt(2 * math.log(1.25 / self.delta)) / self.epsilon
        noise = np.random.normal(0, scale, data.shape)
        return data + noise


# ============== 多模态引擎 ==============

class MultiModalEngine:
    """多模态引擎（优化版）"""
    
    def __init__(
        self,
        embedding_model: Optional[RealEmbeddingModel] = None,
        dp_config: Optional[Dict[str, float]] = None
    ):
        self.embedding_model = embedding_model or RealEmbeddingModel()
        self.dp_engine = RealDifferentialPrivacy(
            epsilon=dp_config.get("epsilon", 1.0) if dp_config else 1.0,
            delta=dp_config.get("delta", 1e-5) if dp_config else 1e-5
        )
        
        self._vector_index: Dict[str, EmbeddingData] = {}
        self._semantic_cache: Dict[str, EmbeddingData] = {}
        
        logger.info("optimized_multimodal_engine_initialized")
    
    async def embed(self, data: ModalityData, apply_dp: bool = False) -> EmbeddingData:
        """嵌入数据"""
        if isinstance(data, TextData):
            vector = await self.embedding_model.embed_text(data.text)
        elif isinstance(data, ImageData):
            vector = await self.embedding_model.embed_image(data)
        elif isinstance(data, EmbeddingData):
            vector = data.vector
        else:
            vector = [random.random() for _ in range(384)]
        
        # 应用差分隐私（可选）
        if apply_dp:
            vector = self.dp_engine.add_laplace_noise(
                np.array(vector),
                sensitivity=1.0
            ).tolist()
        
        embedding = EmbeddingData(vector)
        embedding.metadata = data.metadata.copy()
        embedding.metadata["source_type"] = data.modality_type.value
        embedding.metadata["model_name"] = self.embedding_model.model_name
        
        return embedding
    
    async def embed_batch(
        self,
        data_list: List[ModalityData],
        apply_dp: bool = False
    ) -> List[EmbeddingData]:
        """批量嵌入"""
        embeddings = []
        
        if all(isinstance(d, TextData) for d in data_list):
            texts = [d.text for d in data_list]
            vectors = await self.embedding_model.embed_batch(texts)
            
            for i, vector in enumerate(vectors):
                if apply_dp:
                    vector = self.dp_engine.add_laplace_noise(
                        np.array(vector),
                        sensitivity=1.0
                    ).tolist()
                
                emb = EmbeddingData(vector)
                emb.metadata = data_list[i].metadata.copy()
                emb.metadata["source_type"] = data_list[i].modality_type.value
                embeddings.append(emb)
        else:
            for data in data_list:
                emb = await self.embed(data, apply_dp)
                embeddings.append(emb)
        
        return embeddings
    
    async def index(self, data: ModalityData, apply_dp: bool = False) -> str:
        """索引数据"""
        embedding = await self.embed(data, apply_dp)
        self._vector_index[data.data_id] = embedding
        
        cache_key = f"{data.modality_type.value}:{hash(data) if hasattr(data, '__hash__') else data.data_id}"
        self._semantic_cache[cache_key] = embedding
        
        return data.data_id
    
    async def search(
        self,
        query: Union[ModalityData, str],
        top_k: int = 10,
        threshold: float = 0.0
    ) -> List[Tuple[EmbeddingData, float]]:
        """搜索相似数据"""
        if isinstance(query, str):
            query_data = TextData(text=query)
        else:
            query_data = query
        
        query_embedding = await self.embed(query_data)
        query_vector = np.array(query_embedding.vector)
        
        results: List[Tuple[EmbeddingData, float]] = []
        
        for embedding in self._vector_index.values():
            vector = np.array(embedding.vector)
            similarity = float(np.dot(query_vector, vector))
            
            if similarity >= threshold:
                results.append((embedding, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_indexed": len(self._vector_index),
            "cache_size": len(self._semantic_cache),
            "embedding_model": self.embedding_model.model_name,
            "dp_enabled": self.dp_engine._initialized
        }


# ============== 多模态Agent ==============

class MultiModalAgent:
    """多模态Agent（优化版）"""
    
    def __init__(
        self,
        agent_id: str,
        multimodal_engine: MultiModalEngine,
        capabilities: Optional[List[str]] = None
    ):
        self.agent_id = agent_id
        self.engine = multimodal_engine
        self.capabilities = capabilities or [
            "text_generation",
            "image_understanding",
            "cross_modal_retrieval"
        ]
        self.conversation_history: List[Dict[str, Any]] = []
        
        logger.info(f"optimized_multimodal_agent_initialized: {agent_id}")
    
    async def process_input(
        self,
        inputs: List[ModalityData],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理多模态输入"""
        results = {}
        embeddings = []
        
        for inp in inputs:
            embedding = await self.engine.embed(inp)
            embeddings.append(embedding)
            results[inp.data_id] = {
                "data": inp,
                "embedding": embedding,
                "dimension": embedding.dimension
            }
        
        response = await self._generate_response(inputs, embeddings, context or {})
        
        self.conversation_history.append({
            "inputs": [inp.to_dict() for inp in inputs],
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return response
    
    async def _generate_response(
        self,
        inputs: List[ModalityData],
        embeddings: List[EmbeddingData],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成响应"""
        modalities = [inp.modality_type.value for inp in inputs]
        
        return {
            "text": f"Processed {len(modalities)} modalities: {', '.join(modalities)}",
            "modality": ModalityType.TEXT,
            "processing_time": 0.05,
            "embeddings_generated": len(embeddings),
            "context": context
        }


# ============== 全局实例 ==============

_global_multimodal_engine: Optional[MultiModalEngine] = None


def initialize_multimodal_system(
    embedding_model_name: str = "all-MiniLM-L6-v2",
    dp_epsilon: float = 1.0
):
    """初始化多模态系统"""
    global _global_multimodal_engine
    
    embedding_model = RealEmbeddingModel(embedding_model_name)
    dp_config = {"epsilon": dp_epsilon, "delta": 1e-5}
    
    _global_multimodal_engine = MultiModalEngine(
        embedding_model=embedding_model,
        dp_config=dp_config
    )
    
    logger.info("optimized_multimodal_system_initialized")


def get_multimodal_engine() -> MultiModalEngine:
    """获取多模态引擎"""
    if not _global_multimodal_engine:
        raise RuntimeError("Multimodal system not initialized")
    return _global_multimodal_engine
