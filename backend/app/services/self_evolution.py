"""
Phase 4: 自我进化与自适应系统 - AI的终极进化

实现自我监控、自我优化、参数自动调整、策略进化
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4
import structlog

import numpy as np

from app.core.structured_logging_config import get_structured_logger

logger = get_structured_logger(__name__)


# ============== 进化类型和结构 ==============

class EvolutionStage(str, Enum):
    """进化阶段"""
    MONITORING = "monitoring"
    ANALYSIS = "analysis"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT = "experiment"
    ADOPTION = "adoption"
    CONSOLIDATION = "consolidation"


class OptimizationTarget(str, Enum):
    """优化目标"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ACCURACY = "accuracy"
    COST = "cost"
    RESOURCE_EFFICIENCY = "resource_efficiency"


@dataclass
class SystemMetric:
    """系统指标"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    trend: Optional[float] = None  # 趋势变化率


@dataclass
class ParameterConfig:
    """可配置参数"""
    param_name: str
    current_value: Any
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    step_size: Optional[Any] = None
    value_type: str = "float"
    optimization_weight: float = 1.0
    is_tunable: bool = True


@dataclass
class OptimizationExperiment:
    """优化实验"""
    experiment_id: str = field(default_factory=lambda: str(uuid4()))
    hypothesis: str
    parameter_changes: Dict[str, Any]
    target_metrics: List[str]
    status: str = "pending"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    results: Optional[Dict[str, Any]] = None
    success: Optional[bool] = None


@dataclass
class EvolutionStrategy:
    """进化策略"""
    strategy_id: str
    name: str
    description: str
    fitness_function: Callable[[Dict[str, float]], float]
    mutation_rate: float = 0.1
    crossover_rate: float = 0.5
    population_size: int = 10
    generation_count: int = 0


# ============== 自我监控系统 ==============

class SelfMonitoringSystem:
    """
    自我监控系统
    
    持续监控系统性能和状态
    """
    
    def __init__(self):
        self.metrics_history: Dict[str, List[SystemMetric]] = {}
        self.anomaly_thresholds: Dict[str, Tuple[float, float]] = {}
        self.alerts: List[Dict[str, Any]] = []
        
        self._monitoring = False
        self._last_check: Optional[datetime] = None
        
        logger.info("self_monitoring_system_initialized")
    
    def record_metric(
        self,
        name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录指标"""
        metric = SystemMetric(
            name=name,
            value=value,
            metadata=metadata or {}
        )
        
        if name not in self.metrics_history:
            self.metrics_history[name] = []
        
        self.metrics_history[name].append(metric)
        
        # 保持最近1000个记录
        if len(self.metrics_history[name]) > 1000:
            self.metrics_history[name].pop(0)
        
        # 计算趋势
        self._update_trend(name)
        
        # 检查异常
        self._check_anomaly(name, metric)
    
    def _update_trend(self, metric_name: str) -> None:
        """更新指标趋势"""
        history = self.metrics_history.get(metric_name, [])
        if len(history) < 10:
            return
        
        # 使用线性回归计算趋势
        recent = history[-20:]
        values = [m.value for m in recent]
        times = [(m.timestamp - recent[0].timestamp).total_seconds() for m in recent]
        
        if len(times) > 1:
            n = len(times)
            sum_x = sum(times)
            sum_y = sum(values)
            sum_xy = sum(x * y for x, y in zip(times, values))
            sum_x2 = sum(x * x for x in times)
            
            denominator = n * sum_x2 - sum_x * sum_x
            if denominator != 0:
                slope = (n * sum_xy - sum_x * sum_y) / denominator
                history[-1].trend = slope
    
    def _check_anomaly(self, metric_name: str, metric: SystemMetric) -> None:
        """检查异常值"""
        if metric_name not in self.anomaly_thresholds:
            # 自动设置阈值
            self._set_auto_threshold(metric_name)
        
        low, high = self.anomaly_thresholds.get(metric_name, (-float('inf'), float('inf')))
        
        if metric.value < low or metric.value > high:
            alert = {
                "type": "anomaly",
                "metric": metric_name,
                "value": metric.value,
                "threshold": (low, high),
                "timestamp": metric.timestamp.isoformat(),
                "severity": "high" if abs(metric.value - (low + high)/2) > (high - low) * 0.5 else "medium"
            }
            self.alerts.append(alert)
            logger.warning("anomaly_detected", **alert)
    
    def _set_auto_threshold(self, metric_name: str) -> None:
        """自动设置阈值"""
        history = self.metrics_history.get(metric_name, [])
        if len(history) < 20:
            return
        
        values = [m.value for m in history]
        mean = np.mean(values)
        std = np.std(values)
        
        # 使用3σ原则
        self.anomaly_thresholds[metric_name] = (mean - 3 * std, mean + 3 * std)
    
    def get_metric_statistics(self, metric_name: str, window: int = 100) -> Dict[str, Any]:
        """获取指标统计"""
        history = self.metrics_history.get(metric_name, [])[-window:]
        if not history:
            return {}
        
        values = [m.value for m in history]
        
        return {
            "name": metric_name,
            "count": len(values),
            "mean": np.mean(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "median": np.median(values),
            "p25": np.percentile(values, 25),
            "p75": np.percentile(values, 75),
            "latest": values[-1],
            "trend": history[-1].trend if history else None
        }
    
    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """获取所有指标统计"""
        return {
            name: self.get_metric_statistics(name)
            for name in self.metrics_history
        }


# ============== 自适应参数优化器 ==============

class AdaptiveParameterOptimizer:
    """
    自适应参数优化器
    
    使用多种算法自动调整系统参数
    """
    
    def __init__(self, monitor: SelfMonitoringSystem):
        self.monitor = monitor
        self.parameters: Dict[str, ParameterConfig] = {}
        self.experiments: Dict[str, OptimizationExperiment] = {}
        
        self._strategies: List[EvolutionStrategy] = []
        self._running_experiments: Set[str] = set()
        
        logger.info("adaptive_optimizer_initialized")
    
    def register_parameter(self, config: ParameterConfig) -> None:
        """注册可配置参数"""
        self.parameters[config.param_name] = config
        logger.info("parameter_registered", name=config.param_name, value=config.current_value)
    
    def get_current_value(self, param_name: str) -> Any:
        """获取当前参数值"""
        if param_name not in self.parameters:
            raise KeyError(f"Parameter not found: {param_name}")
        return self.parameters[param_name].current_value
    
    def propose_experiment(
        self,
        hypothesis: str,
        parameter_changes: Dict[str, Any],
        target_metrics: List[str]
    ) -> OptimizationExperiment:
        """提议优化实验"""
        experiment = OptimizationExperiment(
            hypothesis=hypothesis,
            parameter_changes=parameter_changes,
            target_metrics=target_metrics
        )
        
        self.experiments[experiment.experiment_id] = experiment
        logger.info("experiment_proposed", experiment_id=experiment.experiment_id, hypothesis=hypothesis)
        
        return experiment
    
    async def run_experiment(
        self,
        experiment_id: str,
        duration: timedelta = timedelta(minutes=5)
    ) -> Dict[str, Any]:
        """运行优化实验"""
        if experiment_id not in self.experiments:
            raise ValueError("Experiment not found")
        
        experiment = self.experiments[experiment_id]
        experiment.status = "running"
        experiment.start_time = datetime.utcnow()
        
        # 记录基准
        baseline = self._capture_baseline(experiment.target_metrics)
        
        # 应用参数变化
        original_values = {}
        for param_name, new_value in experiment.parameter_changes.items():
            if param_name in self.parameters:
                original_values[param_name] = self.parameters[param_name].current_value
                self.parameters[param_name].current_value = new_value
        
        # 等待
        await asyncio.sleep(duration.total_seconds())
        
        # 记录结果
        results = self._capture_baseline(experiment.target_metrics)
        
        # 恢复原始值
        for param_name, original_value in original_values.items():
            self.parameters[param_name].current_value = original_value
        
        # 分析结果
        improvement = self._analyze_improvement(baseline, results)
        
        experiment.status = "completed"
        experiment.end_time = datetime.utcnow()
        experiment.results = {
            "baseline": baseline,
            "results": results,
            "improvement": improvement
        }
        experiment.success = sum(improvement.values()) > 0
        
        # 如果成功，永久应用
        if experiment.success:
            for param_name, new_value in experiment.parameter_changes.items():
                if param_name in self.parameters:
                    self.parameters[param_name].current_value = new_value
        
        logger.info(
            "experiment_completed",
            experiment_id=experiment_id,
            success=experiment.success,
            improvement=improvement
        )
        
        return experiment.results
    
    def _capture_baseline(self, metrics: List[str]) -> Dict[str, float]:
        """捕获基准数据"""
        baseline = {}
        for metric in metrics:
            stats = self.monitor.get_metric_statistics(metric)
            if stats:
                baseline[metric] = stats.get("mean", 0)
        return baseline
    
    def _analyze_improvement(
        self,
        baseline: Dict[str, float],
        results: Dict[str, float]
    ) -> Dict[str, float]:
        """分析改进"""
        improvement = {}
        for metric in baseline:
            if metric in results and baseline[metric] != 0:
                # 假设我们想要降低延迟、提高吞吐量
                if "latency" in metric.lower() or "time" in metric.lower():
                    improvement[metric] = (baseline[metric] - results[metric]) / baseline[metric]
                else:
                    improvement[metric] = (results[metric] - baseline[metric]) / baseline[metric]
            else:
                improvement[metric] = 0.0
        return improvement
    
    def optimize_with_gradient_descent(
        self,
        target_metric: str,
        learning_rate: float = 0.01,
        epochs: int = 10
    ) -> Dict[str, Any]:
        """使用梯度下降优化"""
        history = []
        
        for epoch in range(epochs):
            # 估计梯度
            gradient = self._estimate_gradient(target_metric)
            
            # 更新参数
            for param_name, grad in gradient.items():
                if param_name in self.parameters:
                    param = self.parameters[param_name]
                    if param.is_tunable:
                        if param.value_type == "float":
                            new_value = param.current_value - learning_rate * grad
                            if param.min_value is not None:
                                new_value = max(new_value, param.min_value)
                            if param.max_value is not None:
                                new_value = min(new_value, param.max_value)
                            param.current_value = new_value
            
            # 记录
            current_value = self.monitor.get_metric_statistics(target_metric).get("mean", 0)
            history.append({"epoch": epoch, "value": current_value})
        
        return {
            "target_metric": target_metric,
            "epochs": epochs,
            "history": history,
            "final_value": history[-1]["value"] if history else None
        }
    
    def _estimate_gradient(self, target_metric: str) -> Dict[str, float]:
        """估计梯度"""
        gradient = {}
        epsilon = 0.01
        
        for param_name, param in self.parameters.items():
            if not param.is_tunable or param.value_type != "float":
                continue
            
            original = param.current_value
            
            # 正向扰动
            param.current_value = original + epsilon
            # 这里应该等待系统稳定并测量
            # 简化实现
            val_plus = self.monitor.get_metric_statistics(target_metric).get("mean", 0)
            
            # 负向扰动
            param.current_value = original - epsilon
            val_minus = self.monitor.get_metric_statistics(target_metric).get("mean", 0)
            
            # 恢复
            param.current_value = original
            
            # 计算梯度
            gradient[param_name] = (val_plus - val_minus) / (2 * epsilon)
        
        return gradient


# ============== 遗传算法进化引擎 ==============

class GeneticEvolutionEngine:
    """
    遗传算法进化引擎
    
    基于自然选择原理优化系统配置
    """
    
    def __init__(self, optimizer: AdaptiveParameterOptimizer):
        self.optimizer = optimizer
        self.population: List[Dict[str, Any]] = []
        self.fitness_history: List[float] = []
        
        self.population_size = 20
        self.mutation_rate = 0.1
        self.crossover_rate = 0.7
        self.elite_size = 2
        
        logger.info("genetic_evolution_engine_initialized")
    
    def initialize_population(self) -> None:
        """初始化种群"""
        self.population = []
        
        for _ in range(self.population_size):
            individual = {}
            for param_name, param in self.optimizer.parameters.items():
                if param.is_tunable:
                    individual[param_name] = self._random_value(param)
            self.population.append(individual)
        
        logger.info("population_initialized", size=self.population_size)
    
    def _random_value(self, param: ParameterConfig) -> Any:
        """生成随机参数值"""
        if param.value_type == "float":
            min_val = param.min_value or 0.0
            max_val = param.max_value or 1.0
            return random.uniform(min_val, max_val)
        elif param.value_type == "int":
            min_val = param.min_value or 0
            max_val = param.max_value or 100
            return random.randint(min_val, max_val)
        elif param.value_type == "bool":
            return random.random() > 0.5
        else:
            return param.current_value
    
    def evaluate_fitness(self, individual: Dict[str, Any]) -> float:
        """评估适应度"""
        # 应用个体的参数
        original_values = {}
        for param_name, value in individual.items():
            if param_name in self.optimizer.parameters:
                original_values[param_name] = self.optimizer.parameters[param_name].current_value
                self.optimizer.parameters[param_name].current_value = value
        
        # 这里应该测量真实的系统性能
        # 简化的适应度函数
        fitness = 0.0
        stats = self.optimizer.monitor.get_all_statistics()
        
        for metric_name, metric_stats in stats.items():
            if "latency" in metric_name.lower() or "time" in metric_name.lower():
                # 越低越好
                fitness -= metric_stats.get("mean", 0)
            else:
                # 越高越好
                fitness += metric_stats.get("mean", 0)
        
        # 恢复
        for param_name, original_value in original_values.items():
            self.optimizer.parameters[param_name].current_value = original_value
        
        return fitness
    
    def select_parents(self, fitness_scores: List[float]) -> List[int]:
        """选择父母"""
        # 轮盘赌选择
        total_fitness = sum(fitness_scores)
        if total_fitness == 0:
            return list(range(min(2, len(fitness_scores))))
        
        selection_probs = [f / total_fitness for f in fitness_scores]
        parents = np.random.choice(
            len(fitness_scores),
            size=2,
            p=selection_probs,
            replace=False
        )
        return list(parents)
    
    def crossover(
        self,
        parent1: Dict[str, Any],
        parent2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """交叉"""
        child = {}
        for param_name in parent1:
            if random.random() < 0.5:
                child[param_name] = parent1[param_name]
            else:
                child[param_name] = parent2[param_name]
        return child
    
    def mutate(self, individual: Dict[str, Any]) -> Dict[str, Any]:
        """变异"""
        mutated = individual.copy()
        
        for param_name, param in self.optimizer.parameters.items():
            if param.is_tunable and param_name in mutated and random.random() < self.mutation_rate:
                if param.value_type == "float":
                    mutation = random.normalvariate(0, 0.1)
                    new_value = mutated[param_name] + mutation
                    if param.min_value is not None:
                        new_value = max(new_value, param.min_value)
                    if param.max_value is not None:
                        new_value = min(new_value, param.max_value)
                    mutated[param_name] = new_value
                elif param.value_type == "int":
                    if random.random() < 0.5:
                        mutated[param_name] += 1
                    else:
                        mutated[param_name] -= 1
        
        return mutated
    
    async def evolve(self, generations: int = 50) -> Dict[str, Any]:
        """执行进化"""
        if not self.population:
            self.initialize_population()
        
        best_individual = None
        best_fitness = -float('inf')
        
        for generation in range(generations):
            # 评估适应度
            fitness_scores = []
            for individual in self.population:
                fitness = self.evaluate_fitness(individual)
                fitness_scores.append(fitness)
                
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_individual = individual.copy()
            
            self.fitness_history.append(best_fitness)
            
            # 选择精英
            elite_indices = np.argsort(fitness_scores)[-self.elite_size:]
            new_population = [self.population[i].copy() for i in elite_indices]
            
            # 生成后代
            while len(new_population) < self.population_size:
                parent_indices = self.select_parents(fitness_scores)
                parent1 = self.population[parent_indices[0]]
                parent2 = self.population[parent_indices[1]]
                
                child = self.crossover(parent1, parent2)
                child = self.mutate(child)
                new_population.append(child)
            
            self.population = new_population
            
            logger.info(
                "generation_completed",
                generation=generation,
                best_fitness=best_fitness
            )
            
            await asyncio.sleep(0.1)
        
        # 应用最佳个体
        if best_individual:
            for param_name, value in best_individual.items():
                if param_name in self.optimizer.parameters:
                    self.optimizer.parameters[param_name].current_value = value
        
        return {
            "best_individual": best_individual,
            "best_fitness": best_fitness,
            "fitness_history": self.fitness_history,
            "generations": generations
        }


# ============== 完整的自我进化系统 ==============

class SelfEvolvingSystem:
    """
    完整的自我进化系统
    
    整合监控、优化和进化
    """
    
    def __init__(self):
        self.monitor = SelfMonitoringSystem()
        self.optimizer = AdaptiveParameterOptimizer(self.monitor)
        self.evolution_engine = GeneticEvolutionEngine(self.optimizer)
        
        self._running = False
        self._stage: EvolutionStage = EvolutionStage.MONITORING
        
        logger.info("self_evolving_system_initialized")
    
    async def start(self) -> None:
        """启动自我进化循环"""
        self._running = True
        logger.info("self_evolving_system_started")
        
        while self._running:
            await self._evolution_cycle()
            await asyncio.sleep(60)  # 每分钟一个周期
    
    async def _evolution_cycle(self) -> None:
        """执行一个进化周期"""
        # 1. 监控阶段
        self._stage = EvolutionStage.MONITORING
        # 监控在record_metric时持续进行
        
        # 2. 分析阶段
        self._stage = EvolutionStage.ANALYSIS
        needs_optimization = self._analyze_status()
        
        if needs_optimization:
            # 3. 假设阶段
            self._stage = EvolutionStage.HYPOTHESIS
            hypothesis = self._generate_hypothesis()
            
            if hypothesis:
                # 4. 实验阶段
                self._stage = EvolutionStage.EXPERIMENT
                # 可以在这里运行实验
                
                # 5. 采用阶段
                self._stage = EvolutionStage.ADOPTION
                # 应用成功的改进
                
                # 6. 巩固阶段
                self._stage = EvolutionStage.CONSOLIDATION
                # 巩固和记录
    
    def _analyze_status(self) -> bool:
        """分析状态，决定是否需要优化"""
        stats = self.monitor.get_all_statistics()
        
        for metric_name, metric_stats in stats.items():
            trend = metric_stats.get("trend", 0)
            
            # 如果有明显的坏趋势
            if "latency" in metric_name.lower() and trend and trend > 0.1:
                return True
            if "throughput" in metric_name.lower() and trend and trend < -0.1:
                return True
        
        return False
    
    def _generate_hypothesis(self) -> Optional[OptimizationExperiment]:
        """生成优化假设"""
        # 简单的假设生成
        tunable_params = [
            name for name, p in self.optimizer.parameters.items()
            if p.is_tunable
        ]
        
        if not tunable_params:
            return None
        
        # 选择一个参数进行优化
        target_param = random.choice(tunable_params)
        param = self.optimizer.parameters[target_param]
        
        if param.value_type == "float":
            change = {target_param: param.current_value * 1.1}
        else:
            return None
        
        return self.optimizer.propose_experiment(
            hypothesis=f"Trying to increase {target_param}",
            parameter_changes=change,
            target_metrics=list(self.monitor.metrics_history.keys())[:3]
        )
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "stage": self._stage,
            "metrics": self.monitor.get_all_statistics(),
            "parameters": {
                name: p.current_value
                for name, p in self.optimizer.parameters.items()
            },
            "running": self._running
        }


# ============== 全局实例 ==============

_global_evolving_system: Optional[SelfEvolvingSystem] = None


def initialize_self_evolution() -> None:
    """初始化自我进化系统"""
    global _global_evolving_system
    _global_evolving_system = SelfEvolvingSystem()
    logger.info("self_evolution_system_initialized")


def get_evolving_system() -> SelfEvolvingSystem:
    """获取自我进化系统"""
    if not _global_evolving_system:
        raise RuntimeError("Self evolution system not initialized")
    return _global_evolving_system
