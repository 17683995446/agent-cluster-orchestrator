"""
Phase 2: Agent智能路由与能力发现机制
提供智能的Agent选择、能力匹配和负载均衡
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
import structlog

from app.models.agent_data_model import Agent, AgentStatus
from app.models.task_data_model import Task
from app.repositories.agent_persistence_repository import AgentRepository
from app.core.structured_logging_config import get_structured_logger

logger = get_structured_logger(__name__)


# ============== 能力定义 ==============

class AgentCapability(str, Enum):
    """代理能力枚举"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DATA_ANALYSIS = "data_analysis"
    TEXT_GENERATION = "text_generation"
    TEXT_TRANSLATION = "text_translation"
    TEXT_SUMMARIZATION = "text_summarization"
    QUESTION_ANSWERING = "question_answering"
    IMAGE_PROCESSING = "image_processing"
    REASONING = "reasoning"
    GENERAL = "general"


@dataclass
class CapabilityMatch:
    """能力匹配结果"""
    capability: AgentCapability
    score: float
    is_primary: bool = False
    confidence: float = 1.0


# ============== 评分配置 ==============

@dataclass
class AgentScoreWeights:
    """代理评分权重配置"""
    capability_match: float = 0.4
    performance_history: float = 0.25
    current_load: float = 0.2
    response_time: float = 0.1
    availability: float = 0.05


@dataclass
class AgentScore:
    """代理评分结果"""
    agent_id: str
    total_score: float
    components: Dict[str, float]
    capability_matches: List[CapabilityMatch]
    recommended: bool


# ============== Agent能力发现器 ==============

class AgentCapabilityDiscoverer:
    """
    代理能力发现器
    
    根据任务描述自动识别所需能力
    """
    
    # 关键词映射
    KEYWORDS = {
        AgentCapability.CODE_GENERATION: [
            "代码", "编程", "编写代码", "生成代码", "实现", "开发", "开发代码", "写代码",
            "code", "programming", "implement", "write code", "develop", "coding"
        ],
        AgentCapability.CODE_REVIEW: [
            "代码审查", "审查代码", "代码评审", "评审", "review code", "code review"
        ],
        AgentCapability.DATA_ANALYSIS: [
            "分析", "数据", "统计", "数据处理", "data", "analysis", "statistics"
        ],
        AgentCapability.TEXT_GENERATION: [
            "生成", "写作", "写", "创作", "generate", "write", "create"
        ],
        AgentCapability.TEXT_TRANSLATION: [
            "翻译", "translate", "translation"
        ],
        AgentCapability.TEXT_SUMMARIZATION: [
            "总结", "摘要", "概括", "summarize", "summary"
        ],
        AgentCapability.QUESTION_ANSWERING: [
            "回答", "问答", "解答", "answer", "qa", "question answering"
        ],
        AgentCapability.REASONING: [
            "推理", "思考", "逻辑", "reasoning", "thinking", "logic"
        ]
    }
    
    def __init__(self):
        self._capability_patterns: Dict[str, Set[str]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """编译关键词模式"""
        for capability, keywords in self.KEYWORDS.items():
            self._capability_patterns[capability] = set(keywords)
    
    def discover_capabilities(self, task_description: str) -> List[CapabilityMatch]:
        """
        从任务描述中发现所需能力
        
        Args:
            task_description: 任务描述文本
            
        Returns:
            能力匹配结果列表，按分数降序排列
        """
        if not task_description:
            return [CapabilityMatch(capability=AgentCapability.GENERAL, score=1.0)]
        
        description = task_description.lower()
        matches: List[CapabilityMatch] = []
        
        for capability, keywords in self.KEYWORDS.items():
            score = 0.0
            match_count = 0
            
            for keyword in keywords:
                if keyword in description:
                    match_count += 1
                    score += 1.0 / len(keywords)
            
            if score > 0:
                matches.append(CapabilityMatch(
                    capability=capability,
                    score=score,
                    is_primary=match_count >=2
                ))
        
        if not matches:
            return [CapabilityMatch(capability=AgentCapability.GENERAL, score=1.0)]
        
        # 按分数排序
        matches.sort(key=lambda x: x.score, reverse=True)
        return matches


# ============== Agent评分器 ==============

class AgentScorer:
    """
    代理评分器
    
    根据多种因素对代理进行评分和排序
    """
    
    def __init__(self, weights: Optional[AgentScoreWeights] = None):
        self.weights = weights or AgentScoreWeights()
    
    def score_agent(
        self,
        agent: Agent,
        required_capabilities: List[CapabilityMatch],
        performance_history: Optional[Dict[str, Any]] = None
    ) -> AgentScore:
        """
        对单个代理进行评分
        
        Args:
            agent: 代理实例
            required_capabilities: 所需能力
            performance_history: 历史性能数据
            
        Returns:
            代理评分结果
        """
        components: Dict[str, float] = {}
        
        # 1. 能力匹配评分
        capability_score = self._calculate_capability_score(agent, required_capabilities)
        components["capability_match"] = capability_score
        
        # 2. 历史性能评分
        performance_score = self._calculate_performance_score(agent, performance_history)
        components["performance_history"] = performance_score
        
        # 3. 当前负载评分
        load_score = self._calculate_load_score(agent)
        components["current_load"] = load_score
        
        # 4. 响应时间评分
        response_time_score = self._calculate_response_time_score(agent)
        components["response_time"] = response_time_score
        
        # 5. 可用性评分
        availability_score = self._calculate_availability_score(agent)
        components["availability"] = availability_score
        
        # 计算总分
        total_score = (
            components["capability_match"] * self.weights.capability_match +
            components["performance_history"] * self.weights.performance_history +
            components["current_load"] * self.weights.current_load +
            components["response_time"] * self.weights.response_time +
            components["availability"] * self.weights.availability
        )
        
        # 确定主要能力匹配
        capability_matches = self._match_agent_capabilities(agent, required_capabilities)
        
        return AgentScore(
            agent_id=str(agent.id),
            total_score=total_score,
            components=components,
            capability_matches=capability_matches,
            recommended=total_score >= 0.6  # 阈值
        )
    
    def _calculate_capability_score(
        self,
        agent: Agent,
        required_capabilities: List[CapabilityMatch]
    ) -> float:
        """计算能力匹配分数"""
        if not agent.capabilities:
            return 0.3  # 基础分数
        
        agent_capabilities = set(str(cap) for cap in agent.capabilities)
        total_score = 0.0
        
        for required in required_capabilities:
            if required.capability in agent_capabilities:
                total_score += required.score
            else:
                total_score += required.score * 0.3  # 部分分数
        
        return min(total_score, 1.0)
    
    def _calculate_performance_score(
        self,
        agent: Agent,
        history: Optional[Dict[str, Any]] = None
    ) -> float:
        """计算历史性能分数"""
        success_rate = getattr(agent, "success_rate", 0.8)
        
        if history:
            success_rate = history.get("success_rate", success_rate)
        
        return success_rate
    
    def _calculate_load_score(self, agent: Agent) -> float:
        """计算当前负载分数"""
        if agent.status == AgentStatus.IDLE:
            return 1.0
        elif agent.status == AgentStatus.BUSY:
            return 0.5
        elif agent.status == AgentStatus.OFFLINE:
            return 0.0
        return 0.3
    
    def _calculate_response_time_score(self, agent: Agent) -> float:
        """计算响应时间分数"""
        avg_response_time = getattr(agent, "avg_response_time", 2.0)
        
        if avg_response_time <= 1.0:
            return 1.0
        elif avg_response_time <= 3.0:
            return 0.8
        elif avg_response_time <= 5.0:
            return 0.6
        elif avg_response_time <= 10.0:
            return 0.4
        return 0.2
    
    def _calculate_availability_score(self, agent: Agent) -> float:
        """计算可用性分数"""
        if agent.status == AgentStatus.IDLE:
            return 1.0
        elif agent.status == AgentStatus.BUSY:
            return 0.7
        return 0.0
    
    def _match_agent_capabilities(
        self,
        agent: Agent,
        required: List[CapabilityMatch]
    ) -> List[CapabilityMatch]:
        """匹配代理能力"""
        agent_capabilities = set(str(cap) for cap in agent.capabilities or [])
        matches = []
        
        for req in required:
            matches.append(CapabilityMatch(
                capability=req.capability,
                score=req.score if req.capability in agent_capabilities else 0.0,
                is_primary=req.is_primary and req.capability in agent_capabilities
            ))
        
        return matches


# ============== 智能路由器 ==============

class IntelligentRouter:
    """
    智能代理路由器
    
    根据任务特征智能选择最佳代理
    """
    
    def __init__(
        self,
        agent_repo: AgentRepository,
        scorer: Optional[AgentScorer] = None,
        discoverer: Optional[AgentCapabilityDiscoverer] = None
    ):
        self.agent_repo = agent_repo
        self.scorer = scorer or AgentScorer()
        self.discoverer = discoverer or AgentCapabilityDiscoverer()
        self._routing_history: List[Dict[str, Any]] = []
        
        # 代理选择策略
        self._strategies: Dict[str, Callable[[List[AgentScore]], List[AgentScore]]] = {
            "best_score": self._strategy_best_score,
            "load_balancing": self._strategy_load_balancing,
            "best_fit": self._strategy_best_fit
        }
    
    async def select_agent(
        self,
        task: Task,
        strategy: str = "best_score",
        count: int = 1
    ) -> List[AgentScore]:
        """
        选择最佳代理
        
        Args:
            task: 任务实例
            strategy: 选择策略
            count: 返回代理数量
            
        Returns:
            按分数排序的代理评分列表
        """
        logger.info(
            "selecting_agent_for_task",
            task_id=str(task.id),
            strategy=strategy
        )
        
        # 1. 发现任务所需能力
        required_capabilities = self.discoverer.discover_capabilities(task.description)
        logger.debug(
            "discovered_capabilities",
            task_id=str(task.id),
            capabilities=[str(c.capability) for c in required_capabilities]
        )
        
        # 2. 获取可用代理
        available_agents = await self.agent_repo.get_idle_agents()
        
        if not available_agents:
            logger.warning("no_idle_agents_available", task_id=str(task.id))
            return []
        
        # 3. 评分每个代理
        scores: List[AgentScore] = []
        for agent in available_agents:
            score = self.scorer.score_agent(agent, required_capabilities)
            scores.append(score)
        
        # 4. 应用策略排序
        strategy_fn = self._strategies.get(strategy, self._strategies["best_score"])
        sorted_scores = strategy_fn(scores)
        
        # 5. 记录路由决策
        self._routing_history.append({
            "task_id": str(task.id),
            "timestamp": datetime.utcnow().isoformat(),
            "strategy": strategy,
            "candidates": [
                {"agent_id": s.agent_id, "score": s.total_score}
                for s in sorted_scores
            ]
        })
        
        logger.info(
            "agent_selection_complete",
            task_id=str(task.id),
            selected_count=min(count, len(sorted_scores))
        )
        
        return sorted_scores[:count]
    
    def _strategy_best_score(self, scores: List[AgentScore]) -> List[AgentScore]:
        """策略：选择分数最高的代理"""
        return sorted(scores, key=lambda x: x.total_score, reverse=True)
    
    def _strategy_load_balancing(self, scores: List[AgentScore]) -> List[AgentScore]:
        """策略：负载均衡"""
        # 混合考虑分数和历史选择频率
        selected_agents = [h["agent_id"] for h in self._routing_history[-20:]]
        
        def load_balance_key(score: AgentScore) -> float:
            # 优先考虑没有被选择过的
            if score.agent_id not in selected_agents:
                return score.total_score + 1.0
            # 最近选择次数越少越好
            select_count = selected_agents.count(score.agent_id)
            return score.total_score - (select_count * 0.1)
        
        return sorted(scores, key=load_balance_key, reverse=True)
    
    def _strategy_best_fit(self, scores: List[AgentScore]) -> List[AgentScore]:
        """策略：最佳能力匹配"""
        return sorted(
            scores,
            key=lambda x: max(
                [c.score for c in x.capability_matches],
                default=0
            ),
            reverse=True
        )
    
    async def get_routing_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取路由历史记录"""
        return self._routing_history[-limit:]


# ============== Agent池管理器 ==============

class AgentPoolManager:
    """
    Agent池管理器
    
    管理代理的生命周期、健康检查和负载均衡
    """
    
    def __init__(
        self,
        agent_repo: AgentRepository,
        router: Optional[IntelligentRouter] = None
    ):
        self.agent_repo = agent_repo
        self.router = router or IntelligentRouter(agent_repo)
        self._last_health_check: Dict[str, datetime] = {}
        self._agent_load_history: Dict[str, List[float]] = {}
    
    async def initialize_agents(self) -> None:
        """初始化代理池"""
        all_agents = await self.agent_repo.get_all()
        logger.info(
            "agent_pool_initialized",
            agent_count=len(all_agents)
        )
    
    async def get_agent_for_task(
        self,
        task: Task,
        strategy: str = "best_score"
    ) -> Optional[Agent]:
        """
        获取执行任务的代理
        
        Args:
            task: 任务实例
            strategy: 选择策略
            
        Returns:
            选择的代理实例
        """
        scores = await self.router.select_agent(task, strategy, count=1)
        
        if not scores:
            return None
        
        best_score = scores[0]
        agent = await self.agent_repo.get_by_id(best_score.agent_id)
        
        logger.info(
            "agent_selected_for_task",
            task_id=str(task.id),
            agent_id=str(agent.id) if agent else None,
            score=best_score.total_score
        )
        
        return agent
    
    async def record_agent_performance(
        self,
        agent_id: str,
        success: bool,
        response_time: float
    ) -> None:
        """记录代理性能"""
        if agent_id not in self._agent_load_history:
            self._agent_load_history[agent_id] = []
        
        self._agent_load_history[agent_id].append(response_time)
        
        if len(self._agent_load_history[agent_id]) > 100:
            self._agent_load_history[agent_id] = self._agent_load_history[agent_id][-100:]
        
        logger.debug(
            "agent_performance_recorded",
            agent_id=agent_id,
            success=success,
            response_time=response_time
        )
    
    async def get_agent_stats(self) -> Dict[str, Any]:
        """获取代理池统计"""
        all_agents = await self.agent_repo.get_all()
        idle_agents = await self.agent_repo.get_idle_agents()
        
        return {
            "total_agents": len(all_agents),
            "idle_agents": len(idle_agents),
            "busy_agents": len(all_agents) - len(idle_agents),
            "routing_history_count": len(self.router._routing_history),
            "agent_load_stats": {
                agent_id: {
                    "count": len(history),
                    "avg_response_time": sum(history) / len(history) if history else 0
                }
                for agent_id, history in self._agent_load_history.items()
            }
        }


# 全局实例
router_instance: Optional[IntelligentRouter] = None
pool_manager_instance: Optional[AgentPoolManager] = None


def initialize_intelligent_routing(agent_repo: AgentRepository) -> None:
    """初始化智能路由系统"""
    global router_instance, pool_manager_instance
    
    router_instance = IntelligentRouter(agent_repo)
    pool_manager_instance = AgentPoolManager(agent_repo, router_instance)
    
    logger.info("intelligent_routing_initialized")
