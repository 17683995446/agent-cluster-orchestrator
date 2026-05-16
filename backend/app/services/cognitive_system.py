"""
Phase 3: 记忆系统与知识图谱 - AI系统的大脑

实现多层记忆系统、知识图谱构建、语义搜索和推理
"""
from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4
import structlog

import numpy as np

from app.core.structured_logging_config import get_structured_logger

logger = get_structured_logger(__name__)


# ============== 记忆类型和结构 ==============

class MemoryType(str, Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class MemoryItem:
    """记忆条目"""
    memory_id: str = field(default_factory=lambda: str(uuid4()))
    memory_type: MemoryType
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    decay_factor: float = 0.99
    tags: List[str] = field(default_factory=list)
    source: Optional[str] = None


@dataclass
class KnowledgeEntity:
    """知识图谱中的实体"""
    entity_id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    entity_type: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KnowledgeRelation:
    """知识图谱中的关系"""
    relation_id: str = field(default_factory=lambda: str(uuid4()))
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class EmbeddingModel(ABC):
    """嵌入模型基类"""
    
    @abstractmethod
    def encode(self, text: str) -> List[float]:
        """将文本编码为向量"""
        pass


class SimpleEmbeddingModel(EmbeddingModel):
    """简单的嵌入模型（用于演示）"""
    
    def encode(self, text: str) -> List[float]:
        """生成简单的哈希嵌入"""
        # 这是一个简单的示例，实际中应使用真实的嵌入模型
        hash_bytes = hashlib.sha256(text.encode()).digest()
        hash_ints = [b for b in hash_bytes]
        
        # 归一化到 [-1, 1]
        embedding = [(x / 127.5 - 1.0) for x in hash_ints[:32]]
        return embedding


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """计算余弦相似度"""
    if len(v1) != len(v2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


# ============== 多层记忆系统 ==============

class MemorySystem:
    """
    多层记忆系统
    
    包含短时记忆、长时记忆、情景记忆、语义记忆等
    """
    
    def __init__(self, embedding_model: EmbeddingModel):
        self.embedding_model = embedding_model
        
        # 不同类型的记忆存储
        self.short_term: Dict[str, MemoryItem] = {}
        self.long_term: Dict[str, MemoryItem] = {}
        self.episodic: Dict[str, MemoryItem] = {}
        self.semantic: Dict[str, MemoryItem] = {}
        
        # 索引
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._source_index: Dict[str, Set[str]] = defaultdict(set)
        
        # 短时记忆容量
        self.short_term_capacity = 50
        self.short_term_duration = timedelta(minutes=30)
        
        logger.info("memory_system_initialized")
    
    def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        存储记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性 (0.0 - 1.0)
            tags: 标签
            source: 来源
            metadata: 元数据
            
        Returns:
            记忆ID
        """
        # 生成嵌入
        embedding = self.embedding_model.encode(content)
        
        # 创建记忆项
        item = MemoryItem(
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            importance=importance,
            tags=tags or [],
            source=source,
            metadata=metadata or {}
        )
        
        # 根据类型存储
        if memory_type == MemoryType.SHORT_TERM:
            self.short_term[item.memory_id] = item
            self._prune_short_term()
        elif memory_type == MemoryType.EPISODIC:
            self.episodic[item.memory_id] = item
        elif memory_type == MemoryType.SEMANTIC:
            self.semantic[item.memory_id] = item
        else:
            self.long_term[item.memory_id] = item
        
        # 更新索引
        for tag in item.tags:
            self._tag_index[tag].add(item.memory_id)
        if item.source:
            self._source_index[item.source].add(item.memory_id)
        
        logger.debug(
            "memory_stored",
            memory_id=item.memory_id,
            memory_type=memory_type,
            content_length=len(content)
        )
        
        return item.memory_id
    
    def retrieve(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        top_k: int = 10,
        threshold: float = 0.0
    ) -> List[Tuple[MemoryItem, float]]:
        """
        检索记忆
        
        Args:
            query: 查询文本
            memory_type: 限制记忆类型
            top_k: 返回前K个
            threshold: 相似度阈值
            
        Returns:
            记忆项和相似度列表
        """
        query_embedding = self.embedding_model.encode(query)
        
        candidates: List[Tuple[MemoryItem, float]] = []
        
        # 确定要搜索的记忆集合
        memory_collections = []
        if memory_type == MemoryType.SHORT_TERM:
            memory_collections = [self.short_term]
        elif memory_type == MemoryType.LONG_TERM:
            memory_collections = [self.long_term]
        elif memory_type == MemoryType.EPISODIC:
            memory_collections = [self.episodic]
        elif memory_type == MemoryType.SEMANTIC:
            memory_collections = [self.semantic]
        else:
            memory_collections = [
                self.short_term,
                self.long_term,
                self.episodic,
                self.semantic
            ]
        
        # 搜索所有相关记忆
        for collection in memory_collections:
            for item in collection.values():
                if item.embedding:
                    similarity = cosine_similarity(query_embedding, item.embedding)
                    
                    # 应用衰减因子
                    time_decay = item.decay_factor ** item.access_count
                    recency = 1.0 - min(1.0, (datetime.utcnow() - item.accessed_at).total_seconds() / (3600 * 24))
                    
                    # 综合评分
                    score = similarity * item.importance * recency
                    
                    if score >= threshold:
                        candidates.append((item, score))
        
        # 排序和返回
        candidates.sort(key=lambda x: x[1], reverse=True)
        results = candidates[:top_k]
        
        # 更新访问记录
        for item, _ in results:
            item.accessed_at = datetime.utcnow()
            item.access_count += 1
        
        logger.debug(
            "memory_retrieved",
            query=query[:50],
            result_count=len(results)
        )
        
        return results
    
    def retrieve_by_tags(
        self,
        tags: List[str],
        memory_type: Optional[MemoryType] = None
    ) -> List[MemoryItem]:
        """通过标签检索"""
        result_ids: Set[str] = set()
        for tag in tags:
            result_ids.update(self._tag_index.get(tag, set()))
        
        return self._get_items_by_ids(result_ids, memory_type)
    
    def _get_items_by_ids(
        self,
        memory_ids: Set[str],
        memory_type: Optional[MemoryType] = None
    ) -> List[MemoryItem]:
        items = []
        for memory_id in memory_ids:
            if memory_id in self.short_term:
                items.append(self.short_term[memory_id])
            if memory_id in self.long_term:
                items.append(self.long_term[memory_id])
            if memory_id in self.episodic:
                items.append(self.episodic[memory_id])
            if memory_id in self.semantic:
                items.append(self.semantic[memory_id])
        
        if memory_type:
            items = [i for i in items if i.memory_type == memory_type]
        
        return items
    
    def _prune_short_term(self) -> None:
        """清理短时记忆"""
        # 移除过期的
        now = datetime.utcnow()
        expired = [
            id for id, item in self.short_term.items()
            if (now - item.created_at) > self.short_term_duration
        ]
        for id in expired:
            del self.short_term[id]
        
        # 超过容量时移除最不重要的
        if len(self.short_term) > self.short_term_capacity:
            sorted_items = sorted(
                self.short_term.items(),
                key=lambda x: x[1].importance * (1.0 - x[1].access_count * 0.1)
            )
            to_remove = sorted_items[:len(self.short_term) - self.short_term_capacity]
            for id, _ in to_remove:
                # 可能的话，转移到长时记忆
                item = self.short_term[id]
                if item.importance > 0.3:
                    item.memory_type = MemoryType.LONG_TERM
                    self.long_term[id] = item
                del self.short_term[id]
    
    def consolidate(self) -> int:
        """
        记忆巩固
        
        将重要的短时记忆转移到长时记忆
        """
        consolidated = 0
        
        for id, item in list(self.short_term.items()):
            if item.importance > 0.7 and item.access_count > 2:
                # 转移到长时记忆
                item.memory_type = MemoryType.LONG_TERM
                self.long_term[id] = item
                del self.short_term[id]
                consolidated += 1
        
        logger.info("memory_consolidated", count=consolidated)
        return consolidated


# ============== 知识图谱 ==============

class KnowledgeGraph:
    """
    知识图谱
    
    存储实体和关系，支持推理和查询
    """
    
    def __init__(self, embedding_model: EmbeddingModel):
        self.embedding_model = embedding_model
        
        self.entities: Dict[str, KnowledgeEntity] = {}
        self.relations: Dict[str, KnowledgeRelation] = {}
        
        # 索引
        self._entity_name_index: Dict[str, List[str]] = defaultdict(list)
        self._entity_type_index: Dict[str, List[str]] = defaultdict(list)
        self._outgoing_relations: Dict[str, List[str]] = defaultdict(list)
        self._incoming_relations: Dict[str, List[str]] = defaultdict(list)
        
        logger.info("knowledge_graph_initialized")
    
    def add_entity(
        self,
        name: str,
        entity_type: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> str:
        """添加实体"""
        entity = KnowledgeEntity(
            name=name,
            entity_type=entity_type,
            attributes=attributes or {},
            embedding=self.embedding_model.encode(name)
        )
        
        self.entities[entity.entity_id] = entity
        
        # 更新索引
        self._entity_name_index[name].append(entity.entity_id)
        self._entity_type_index[entity_type].append(entity.entity_id)
        
        logger.debug("entity_added", entity_id=entity.entity_id, name=name)
        return entity.entity_id
    
    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """添加关系"""
        if source_id not in self.entities or target_id not in self.entities:
            raise ValueError("Source or target entity not found")
        
        relation = KnowledgeRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
            metadata=metadata or {}
        )
        
        self.relations[relation.relation_id] = relation
        
        # 更新索引
        self._outgoing_relations[source_id].append(relation.relation_id)
        self._incoming_relations[target_id].append(relation.relation_id)
        
        logger.debug(
            "relation_added",
            relation_id=relation.relation_id,
            source=source_id,
            target=target_id,
            type=relation_type
        )
        
        return relation.relation_id
    
    def find_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        top_k: int = 10
    ) -> List[Tuple[KnowledgeEntity, float]]:
        """搜索实体"""
        query_embedding = self.embedding_model.encode(query)
        
        candidates: List[Tuple[KnowledgeEntity, float]] = []
        
        for entity in self.entities.values():
            if entity_type and entity.entity_type != entity_type:
                continue
            
            if entity.embedding:
                similarity = cosine_similarity(query_embedding, entity.embedding)
                candidates.append((entity, similarity))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]
    
    def get_neighbors(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
        max_depth: int = 1
    ) -> Dict[str, List[Tuple[KnowledgeEntity, KnowledgeRelation]]]:
        """获取邻居"""
        if entity_id not in self.entities:
            return {}
        
        result = defaultdict(list)
        visited = set()
        queue = [(entity_id, 0)]
        
        while queue:
            current_id, depth = queue.pop(0)
            
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            
            # 查找出边
            for rel_id in self._outgoing_relations.get(current_id, []):
                rel = self.relations[rel_id]
                if relation_type and rel.relation_type != relation_type:
                    continue
                
                if rel.target_id in self.entities:
                    target = self.entities[rel.target_id]
                    result[current_id].append((target, rel))
                    
                    if depth < max_depth:
                        queue.append((rel.target_id, depth + 1))
        
        return result
    
    def infer_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3
    ) -> Optional[List[KnowledgeRelation]]:
        """
        推理路径
        
        使用BFS找到源到目标的路径
        """
        if source_id not in self.entities or target_id not in self.entities:
            return None
        
        queue = [(source_id, [])]
        visited = set([source_id])
        
        while queue:
            current_id, path = queue.pop(0)
            
            if current_id == target_id:
                return path
            
            if len(path) >= max_depth:
                continue
            
            for rel_id in self._outgoing_relations.get(current_id, []):
                rel = self.relations[rel_id]
                if rel.target_id not in visited:
                    visited.add(rel.target_id)
                    queue.append((rel.target_id, path + [rel]))
        
        return None
    
    def export_graph(self) -> Dict[str, Any]:
        """导出图谱"""
        return {
            "entities": [
                {
                    "id": e.entity_id,
                    "name": e.name,
                    "type": e.entity_type,
                    "attributes": e.attributes
                }
                for e in self.entities.values()
            ],
            "relations": [
                {
                    "id": r.relation_id,
                    "source": r.source_id,
                    "target": r.target_id,
                    "type": r.relation_type,
                    "weight": r.weight
                }
                for r in self.relations.values()
            ]
        }


# ============== 推理引擎 ==============

class ReasoningEngine:
    """
    推理引擎
    
    基于记忆和知识图谱进行推理
    """
    
    def __init__(self, memory: MemorySystem, graph: KnowledgeGraph):
        self.memory = memory
        self.graph = graph
        
        self._inference_rules: List[Callable] = []
        logger.info("reasoning_engine_initialized")
    
    def reason(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行推理
        
        Args:
            query: 查询
            context: 上下文
            
        Returns:
            推理结果
        """
        # 1. 检索相关记忆
        related_memories = self.memory.retrieve(query, top_k=5)
        
        # 2. 搜索知识图谱
        related_entities = self.graph.find_entities(query, top_k=5)
        
        # 3. 应用推理规则
        inferences = []
        for rule in self._inference_rules:
            try:
                result = rule(query, related_memories, related_entities, context)
                if result:
                    inferences.append(result)
            except Exception as e:
                logger.error("inference_rule_failed", error=str(e))
        
        # 4. 综合结果
        return {
            "query": query,
            "related_memories": [(m.content, s) for m, s in related_memories],
            "related_entities": [(e.name, s) for e, s in related_entities],
            "inferences": inferences
        }
    
    def add_rule(self, rule: Callable) -> None:
        """添加推理规则"""
        self._inference_rules.append(rule)


# ============== 全局实例 ==============

_global_memory: Optional[MemorySystem] = None
_global_graph: Optional[KnowledgeGraph] = None
_global_reasoning: Optional[ReasoningEngine] = None


def initialize_cognitive_system() -> None:
    """初始化认知系统"""
    global _global_memory, _global_graph, _global_reasoning
    
    embedding_model = SimpleEmbeddingModel()
    
    _global_memory = MemorySystem(embedding_model)
    _global_graph = KnowledgeGraph(embedding_model)
    _global_reasoning = ReasoningEngine(_global_memory, _global_graph)
    
    logger.info("cognitive_system_initialized")


def get_memory_system() -> MemorySystem:
    """获取记忆系统"""
    if not _global_memory:
        raise RuntimeError("Cognitive system not initialized")
    return _global_memory


def get_knowledge_graph() -> KnowledgeGraph:
    """获取知识图谱"""
    if not _global_graph:
        raise RuntimeError("Cognitive system not initialized")
    return _global_graph


def get_reasoning_engine() -> ReasoningEngine:
    """获取推理引擎"""
    if not _global_reasoning:
        raise RuntimeError("Cognitive system not initialized")
    return _global_reasoning
