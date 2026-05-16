"""
Phase 3: 元学习与快速适应 - 史诗级创新

实现MAML、Reptile等元学习算法，让模型能够快速适应新任务
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4
import structlog
import numpy as np

from app.core.structured_logging_config import get_structured_logger

logger = get_structured_logger(__name__)


# ============== 元学习类型定义 ==============

class MetaLearningAlgorithm(str, Enum):
    """元学习算法"""
    MAML = "maml"
    REPTILE = "reptile"
    FOMAML = "fomaml"
    PROTOTYPICAL = "prototypical"


@dataclass
class Task:
    """任务数据"""
    task_id: str = field(default_factory=lambda: str(uuid4()))
    task_type: str = ""
    support_data: Dict[str, Any] = field(default_factory=dict)
    query_data: Dict[str, Any] = field(default_factory=dict)
    num_shot: int = 5
    num_way: int = 10
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MetaParameters:
    """元参数"""
    weights: Dict[str, List[float]] = field(default_factory=dict)
    version: int = 0
    step_size: float = 0.01
    meta_step_size: float = 0.001
    metadata: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ============== 基础模型类 ==============

class BaseMetaModel(ABC):
    """基础元学习模型"""
    
    def __init__(self, input_dim: int, output_dim: int):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.weights: Dict[str, np.ndarray] = {}
        self.biases: Dict[str, np.ndarray] = {}
        self._initialize_weights()
    
    def _initialize_weights(self):
        """初始化权重"""
        self.weights["layer1"] = np.random.randn(self.input_dim, 64) * 0.01
        self.biases["layer1"] = np.zeros(64)
        self.weights["layer2"] = np.random.randn(64, self.output_dim) * 0.01
        self.biases["layer2"] = np.zeros(self.output_dim)
    
    def forward(self, x: np.ndarray) -> np.ndarray:
        """前向传播"""
        h = np.dot(x, self.weights["layer1"]) + self.biases["layer1"]
        h = np.maximum(0, h)
        logits = np.dot(h, self.weights["layer2"]) + self.biases["layer2"]
        return logits
    
    def compute_loss(self, x: np.ndarray, y: np.ndarray) -> Tuple[float, Dict[str, np.ndarray]]:
        """计算损失和梯度"""
        logits = self.forward(x)
        probs = self._softmax(logits)
        loss = -np.mean(np.sum(y * np.log(probs + 1e-8), axis=1))
        
        # 计算梯度
        d_logits = probs - y
        d_w2 = np.dot(self._relu(np.dot(x, self.weights["layer1"]) + self.biases["layer1"]).T, d_logits)
        d_b2 = np.sum(d_logits, axis=0)
        
        d_h = np.dot(d_logits, self.weights["layer2"].T)
        d_h[self._relu(np.dot(x, self.weights["layer1"]) + self.biases["layer1"]) <= 0] = 0
        d_w1 = np.dot(x.T, d_h)
        d_b1 = np.sum(d_h, axis=0)
        
        gradients = {
            "layer1": d_w1,
            "layer2": d_w2,
            "bias1": d_b1,
            "bias2": d_b2
        }
        
        return float(loss), gradients
    
    def _relu(self, x: np.ndarray) -> np.ndarray:
        return np.maximum(0, x)
    
    def _softmax(self, x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x, axis=1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=1, keepdims=True)
    
    def get_parameters(self) -> MetaParameters:
        """获取参数"""
        return MetaParameters(
            weights={
                k: v.tolist()
                for k, v in {**self.weights, **{f"bias_{k}": v for k, v in self.biases.items()}}.items()
            }
        )
    
    def set_parameters(self, params: MetaParameters):
        """设置参数"""
        for key in self.weights:
            if key in params.weights:
                self.weights[key] = np.array(params.weights[key])
        
        for key in self.biases:
            param_key = f"bias_{key}"
            if param_key in params.weights:
                self.biases[key] = np.array(params.weights[param_key])


# ============== MAML 算法 ==============

class MAML:
    """MAML (Model-Agnostic Meta-Learning)"""
    
    def __init__(
        self,
        model: BaseMetaModel,
        inner_lr: float = 0.01,
        outer_lr: float = 0.001,
        num_inner_steps: int = 1
    ):
        self.model = model
        self.inner_lr = inner_lr
        self.outer_lr = outer_lr
        self.num_inner_steps = num_inner_steps
        self.meta_parameters: Optional[MetaParameters] = None
        
        logger.info("maml_initialized")
    
    def inner_loop(
        self,
        model: BaseMetaModel,
        task: Task,
        num_steps: Optional[int] = None
    ) -> BaseMetaModel:
        """内循环：在任务上快速适应"""
        num_steps = num_steps or self.num_inner_steps
        
        adapted_model = copy.deepcopy(model)
        
        # 准备支持集数据
        x_support = np.array(task.support_data.get("inputs", []))
        y_support = np.array(task.support_data.get("targets", []))
        
        for _ in range(num_steps):
            if len(x_support) > 0 and len(y_support) > 0:
                loss, gradients = adapted_model.compute_loss(x_support, y_support)
                
                # 更新参数
                adapted_model.weights["layer1"] -= self.inner_lr * gradients["layer1"]
                adapted_model.weights["layer2"] -= self.inner_lr * gradients["layer2"]
                adapted_model.biases["layer1"] -= self.inner_lr * gradients["bias1"]
                adapted_model.biases["layer2"] -= self.inner_lr * gradients["bias2"]
        
        return adapted_model
    
    def meta_train(
        self,
        tasks: List[Task],
        num_epochs: int = 100
    ) -> Dict[str, Any]:
        """元训练"""
        history = []
        
        for epoch in range(num_epochs):
            total_meta_loss = 0.0
            meta_gradients: Dict[str, np.ndarray] = {
                "layer1": np.zeros_like(self.model.weights["layer1"]),
                "layer2": np.zeros_like(self.model.weights["layer2"]),
                "bias1": np.zeros_like(self.model.biases["layer1"]),
                "bias2": np.zeros_like(self.model.biases["layer2"])
            }
            
            # 在任务批次上训练
            for task in tasks:
                # 内循环适应
                adapted_model = self.inner_loop(self.model, task)
                
                # 在外循环评估
                x_query = np.array(task.query_data.get("inputs", []))
                y_query = np.array(task.query_data.get("targets", []))
                
                if len(x_query) > 0 and len(y_query) > 0:
                    meta_loss, gradients = adapted_model.compute_loss(x_query, y_query)
                    total_meta_loss += meta_loss
                    
                    # 累积梯度
                    meta_gradients["layer1"] += gradients["layer1"]
                    meta_gradients["layer2"] += gradients["layer2"]
                    meta_gradients["bias1"] += gradients["bias1"]
                    meta_gradients["bias2"] += gradients["bias2"]
            
            # 更新元参数
            self.model.weights["layer1"] -= self.outer_lr * meta_gradients["layer1"] / len(tasks)
            self.model.weights["layer2"] -= self.outer_lr * meta_gradients["layer2"] / len(tasks)
            self.model.biases["layer1"] -= self.outer_lr * meta_gradients["bias1"] / len(tasks)
            self.model.biases["layer2"] -= self.outer_lr * meta_gradients["bias2"] / len(tasks)
            
            avg_meta_loss = total_meta_loss / len(tasks)
            history.append({"epoch": epoch, "meta_loss": avg_meta_loss})
            
            if epoch % 10 == 0:
                logger.info(f"MAML epoch {epoch}, meta loss: {avg_meta_loss:.4f}")
        
        self.meta_parameters = self.model.get_parameters()
        self.meta_parameters.version += 1
        
        return {
            "algorithm": "MAML",
            "num_epochs": num_epochs,
            "history": history,
            "final_meta_loss": history[-1]["meta_loss"] if history else 0
        }
    
    def fast_adapt(self, task: Task) -> BaseMetaModel:
        """快速适应新任务"""
        adapted_model = self.inner_loop(self.model, task, num_steps=1)
        return adapted_model


# ============== Reptile 算法 ==============

class Reptile:
    """Reptile 元学习算法"""
    
    def __init__(
        self,
        model: BaseMetaModel,
        step_size: float = 0.001,
        num_inner_steps: int = 3
    ):
        self.model = model
        self.step_size = step_size
        self.num_inner_steps = num_inner_steps
        self.meta_parameters: Optional[MetaParameters] = None
        
        logger.info("reptile_initialized")
    
    def meta_train(
        self,
        tasks: List[Task],
        num_epochs: int = 100
    ) -> Dict[str, Any]:
        """元训练"""
        history = []
        
        for epoch in range(num_epochs):
            # 保存初始参数
            initial_weights = copy.deepcopy(self.model.weights)
            initial_biases = copy.deepcopy(self.model.biases)
            
            avg_weights: Dict[str, np.ndarray] = {
                k: np.zeros_like(v)
                for k, v in self.model.weights.items()
            }
            avg_biases: Dict[str, np.ndarray] = {
                k: np.zeros_like(v)
                for k, v in self.model.biases.items()
            }
            
            total_loss = 0.0
            
            # 在任务上训练
            for task in tasks:
                # 重置参数
                self.model.weights = copy.deepcopy(initial_weights)
                self.model.biases = copy.deepcopy(initial_biases)
                
                # 内循环
                for _ in range(self.num_inner_steps):
                    x = np.array(task.support_data.get("inputs", []))
                    y = np.array(task.support_data.get("targets", []))
                    
                    if len(x) > 0 and len(y) > 0:
                        loss, gradients = self.model.compute_loss(x, y)
                        total_loss += loss
                        
                        self.model.weights["layer1"] -= self.step_size * gradients["layer1"]
                        self.model.weights["layer2"] -= self.step_size * gradients["layer2"]
                        self.model.biases["layer1"] -= self.step_size * gradients["bias1"]
                        self.model.biases["layer2"] -= self.step_size * gradients["bias2"]
                
                # 累积参数
                for key in avg_weights:
                    avg_weights[key] += self.model.weights[key]
                for key in avg_biases:
                    avg_biases[key] += self.model.biases[key]
            
            # 更新元参数
            for key in initial_weights:
                self.model.weights[key] = initial_weights[key] + self.step_size * (avg_weights[key] / len(tasks) - initial_weights[key])
            for key in initial_biases:
                self.model.biases[key] = initial_biases[key] + self.step_size * (avg_biases[key] / len(tasks) - initial_biases[key])
            
            avg_loss = total_loss / (len(tasks) * self.num_inner_steps) if tasks else 0
            history.append({"epoch": epoch, "loss": avg_loss})
            
            if epoch % 10 == 0:
                logger.info(f"Reptile epoch {epoch}, loss: {avg_loss:.4f}")
        
        self.meta_parameters = self.model.get_parameters()
        return {
            "algorithm": "Reptile",
            "num_epochs": num_epochs,
            "history": history
        }


# ============== 原型网络 ==============

class PrototypicalNetwork:
    """原型网络"""
    
    def __init__(self, embedding_dim: int = 128):
        self.embedding_dim = embedding_dim
        self.prototypes: Dict[str, List[float]] = {}
        self.embedding_model: Optional[Any] = None
        
        logger.info("prototypical_network_initialized")
    
    def compute_prototypes(
        self,
        support_set: Dict[str, List[List[float]]]
    ) -> Dict[str, List[float]]:
        """计算原型"""
        prototypes = {}
        
        for class_id, embeddings in support_set.items():
            emb_array = np.array(embeddings)
            prototype = np.mean(emb_array, axis=0)
            prototypes[class_id] = prototype.tolist()
        
        self.prototypes = prototypes
        return prototypes
    
    def classify(
        self,
        query_embedding: List[float]
    ) -> Tuple[str, float]:
        """分类"""
        distances = []
        
        for class_id, prototype in self.prototypes.items():
            dist = np.linalg.norm(np.array(query_embedding) - np.array(prototype))
            distances.append((class_id, float(dist)))
        
        distances.sort(key=lambda x: x[1])
        return distances[0][0], distances[0][1]


# ============== 元学习训练器 ==============

class MetaLearningTrainer:
    """元学习训练器"""
    
    def __init__(self, algorithm: MetaLearningAlgorithm = MetaLearningAlgorithm.MAML):
        self.algorithm = algorithm
        self.model: Optional[BaseMetaModel] = None
        self.trainer: Optional[Union[MAML, Reptile]] = None
        
        logger.info(f"meta_learning_trainer_initialized: {algorithm}")
    
    def initialize(
        self,
        input_dim: int,
        output_dim: int,
        **kwargs
    ):
        """初始化"""
        self.model = BaseMetaModel(input_dim, output_dim)
        
        if self.algorithm == MetaLearningAlgorithm.MAML:
            self.trainer = MAML(
                self.model,
                inner_lr=kwargs.get("inner_lr", 0.01),
                outer_lr=kwargs.get("outer_lr", 0.001)
            )
        elif self.algorithm == MetaLearningAlgorithm.REPTILE:
            self.trainer = Reptile(
                self.model,
                step_size=kwargs.get("step_size", 0.001)
            )
        
        return self
    
    async def train(
        self,
        tasks: List[Task],
        num_epochs: int = 100
    ) -> Dict[str, Any]:
        """训练"""
        if not self.trainer:
            raise ValueError("Trainer not initialized")
        
        result = self.trainer.meta_train(tasks, num_epochs)
        return result
    
    def adapt(self, task: Task) -> BaseMetaModel:
        """快速适应"""
        if not self.trainer or not isinstance(self.trainer, MAML):
            raise ValueError("Adaptation only supported with MAML")
        
        return self.trainer.fast_adapt(task)


# ============== 工具函数 ==============

def generate_synthetic_task(
    num_shot: int = 5,
    num_way: int = 5,
    input_dim: int = 10
) -> Task:
    """生成合成任务"""
    # 支持集
    support_inputs = np.random.randn(num_shot * num_way, input_dim)
    support_targets = np.zeros((num_shot * num_way, num_way))
    
    for i in range(num_way):
        support_targets[i * num_shot:(i + 1) * num_shot, i] = 1
    
    # 查询集
    query_inputs = np.random.randn(num_way, input_dim)
    query_targets = np.zeros((num_way, num_way))
    
    for i in range(num_way):
        query_targets[i, i] = 1
    
    return Task(
        task_type="classification",
        num_shot=num_shot,
        num_way=num_way,
        support_data={
            "inputs": support_inputs.tolist(),
            "targets": support_targets.tolist()
        },
        query_data={
            "inputs": query_inputs.tolist(),
            "targets": query_targets.tolist()
        }
    )


# ============== 全局实例 ==============

_global_meta_trainer: Optional[MetaLearningTrainer] = None


def initialize_meta_learning_system(
    algorithm: MetaLearningAlgorithm = MetaLearningAlgorithm.MAML
):
    """初始化元学习系统"""
    global _global_meta_trainer
    
    _global_meta_trainer = MetaLearningTrainer(algorithm)
    logger.info("meta_learning_system_initialized")


def get_meta_trainer() -> MetaLearningTrainer:
    """获取元学习训练器"""
    if not _global_meta_trainer:
        raise RuntimeError("Meta learning system not initialized")
    return _global_meta_trainer
