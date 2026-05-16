"""
系统集成和测试模块

整合所有功能并进行测试
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

from app.services.agent_orchestrator import (
    initialize_agent_orchestration,
    get_orchestrator,
    get_workflow_system,
    ChainBuilder,
    ExecutionEngine
)
from app.services.distributed_scheduler import (
    initialize_distributed_system,
    get_scheduler,
    get_rl_optimizer,
    WorkerNode,
    WorkerStatus,
    DistributedTask,
    DistributedTaskStatus
)
from app.services.cognitive_system import (
    initialize_cognitive_system,
    get_memory_system,
    get_knowledge_graph,
    get_reasoning_engine,
    MemoryType
)
from app.services.self_evolution import (
    initialize_self_evolution,
    get_evolving_system,
    ParameterConfig
)

from app.core.structured_logging_config import get_structured_logger

logger = get_structured_logger(__name__)


@dataclass
class TestResult:
    """测试结果"""
    test_name: str
    success: bool
    duration: float
    error: Optional[str] = None
    metrics: Dict[str, Any] = None


class IntegrationTester:
    """集成测试器"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time: Optional[datetime] = None
    
    async def run_all_tests(self) -> List[TestResult]:
        """运行所有测试"""
        self.start_time = datetime.utcnow()
        logger.info("starting_integration_tests")
        
        # 测试1: 记忆系统
        await self.test_memory_system()
        
        # 测试2: 知识图谱
        await self.test_knowledge_graph()
        
        # 测试3: Agent编排
        await self.test_agent_orchestration()
        
        # 测试4: 分布式调度
        await self.test_distributed_scheduling()
        
        # 测试5: 自我监控
        await self.test_self_monitoring()
        
        # 测试6: 端到端集成
        await self.test_end_to_end()
        
        return self.results
    
    async def test_memory_system(self) -> TestResult:
        """测试记忆系统"""
        test_name = "Memory System Test"
        start = datetime.utcnow()
        
        try:
            memory = get_memory_system()
            
            # 存储一些记忆
            memory.store(
                "The quick brown fox jumps over the lazy dog",
                MemoryType.SHORT_TERM,
                importance=0.7,
                tags=["test", "example"]
            )
            
            memory.store(
                "Machine learning is a subset of artificial intelligence",
                MemoryType.LONG_TERM,
                importance=0.9,
                tags=["AI", "ML"]
            )
            
            memory.store(
                "Paris is the capital of France",
                MemoryType.SEMANTIC,
                importance=0.6
            )
            
            # 检索
            results = memory.retrieve("capital city in France", top_k=3)
            
            # 标签检索
            tag_results = memory.retrieve_by_tags(["AI"])
            
            success = len(results) > 0 and len(tag_results) > 0
            
            duration = (datetime.utcnow() - start).total_seconds()
            
            result = TestResult(
                test_name=test_name,
                success=success,
                duration=duration,
                metrics={
                    "memories_stored": 3,
                    "retrieval_results": len(results),
                    "tag_results": len(tag_results)
                }
            )
            
            self.results.append(result)
            logger.info("test_completed", test=test_name, success=success)
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds()
            result = TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )
            self.results.append(result)
            logger.error("test_failed", test=test_name, error=str(e))
            return result
    
    async def test_knowledge_graph(self) -> TestResult:
        """测试知识图谱"""
        test_name = "Knowledge Graph Test"
        start = datetime.utcnow()
        
        try:
            graph = get_knowledge_graph()
            
            # 添加实体
            id1 = graph.add_entity("Alice", "Person", {"age": 30})
            id2 = graph.add_entity("Bob", "Person", {"age": 35})
            id3 = graph.add_entity("Company XYZ", "Company")
            
            # 添加关系
            graph.add_relation(id1, id2, "friend_of", weight=0.8)
            graph.add_relation(id1, id3, "works_at", weight=1.0)
            
            # 搜索
            entities = graph.find_entities("Alice")
            
            # 邻居
            neighbors = graph.get_neighbors(id1)
            
            # 导出
            export = graph.export_graph()
            
            success = len(entities) > 0 and len(export["entities"]) == 3
            
            duration = (datetime.utcnow() - start).total_seconds()
            
            result = TestResult(
                test_name=test_name,
                success=success,
                duration=duration,
                metrics={
                    "entities_created": 3,
                    "relations_created": 2,
                    "search_results": len(entities)
                }
            )
            
            self.results.append(result)
            logger.info("test_completed", test=test_name, success=success)
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds()
            result = TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )
            self.results.append(result)
            logger.error("test_failed", test=test_name, error=str(e))
            return result
    
    async def test_agent_orchestration(self) -> TestResult:
        """测试Agent编排"""
        test_name = "Agent Orchestration Test"
        start = datetime.utcnow()
        
        try:
            orchestrator = get_orchestrator()
            workflow = get_workflow_system()
            
            # 注册Agent
            class DummyLLMManager:
                async def generate(self, text: str, model: str = None) -> str:
                    return f"Response to: {text}"
            
            # （实际中需要初始化正确）
            # 这里简化测试
            
            # 构建链
            builder = ChainBuilder("Test Chain")
            builder.agent_node(
                "test_agent",
                input_template="Test input",
                description="Test agent"
            )
            chain = builder.build()
            
            # 保存链
            chain_id = workflow.save_chain(chain)
            
            success = chain_id is not None
            
            duration = (datetime.utcnow() - start).total_seconds()
            
            result = TestResult(
                test_name=test_name,
                success=success,
                duration=duration,
                metrics={
                    "chain_created": True,
                    "chain_id": chain_id
                }
            )
            
            self.results.append(result)
            logger.info("test_completed", test=test_name, success=success)
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds()
            result = TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )
            self.results.append(result)
            logger.error("test_failed", test=test_name, error=str(e))
            return result
    
    async def test_distributed_scheduling(self) -> TestResult:
        """测试分布式调度"""
        test_name = "Distributed Scheduling Test"
        start = datetime.utcnow()
        
        try:
            scheduler = get_scheduler()
            
            # 注册Worker
            worker1 = WorkerNode(
                node_id="worker_1",
                worker_type="compute",
                host="localhost",
                port=8001,
                status=WorkerStatus.IDLE,
                capabilities=["task1", "task2"]
            )
            
            worker2 = WorkerNode(
                node_id="worker_2",
                worker_type="compute",
                host="localhost",
                port=8002,
                status=WorkerStatus.IDLE,
                capabilities=["task1"]
            )
            
            scheduler.register_worker(worker1)
            scheduler.register_worker(worker2)
            
            # 提交任务
            task = DistributedTask(
                task_type="task1",
                priority=1
            )
            task_id = scheduler.submit_task(task)
            
            # 获取指标
            metrics = scheduler.get_metrics()
            
            success = task_id is not None and "registered_workers" in metrics
            
            duration = (datetime.utcnow() - start).total_seconds()
            
            result = TestResult(
                test_name=test_name,
                success=success,
                duration=duration,
                metrics=metrics
            )
            
            self.results.append(result)
            logger.info("test_completed", test=test_name, success=success)
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds()
            result = TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )
            self.results.append(result)
            logger.error("test_failed", test=test_name, error=str(e))
            return result
    
    async def test_self_monitoring(self) -> TestResult:
        """测试自我监控"""
        test_name = "Self Monitoring Test"
        start = datetime.utcnow()
        
        try:
            system = get_evolving_system()
            
            # 记录一些指标
            for i in range(10):
                system.monitor.record_metric("test_latency", float(100 + i * 10))
                system.monitor.record_metric("test_throughput", float(1000 - i * 50))
            
            # 获取统计
            stats = system.monitor.get_all_statistics()
            
            # 注册参数
            param = ParameterConfig(
                param_name="test_param",
                current_value=0.5,
                min_value=0.0,
                max_value=1.0,
                value_type="float"
            )
            system.optimizer.register_parameter(param)
            
            success = "test_latency" in stats
            
            duration = (datetime.utcnow() - start).total_seconds()
            
            result = TestResult(
                test_name=test_name,
                success=success,
                duration=duration,
                metrics={
                    "metrics_recorded": 20,
                    "stats_available": len(stats)
                }
            )
            
            self.results.append(result)
            logger.info("test_completed", test=test_name, success=success)
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds()
            result = TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )
            self.results.append(result)
            logger.error("test_failed", test=test_name, error=str(e))
            return result
    
    async def test_end_to_end(self) -> TestResult:
        """端到端集成测试"""
        test_name = "End-to-End Integration Test"
        start = datetime.utcnow()
        
        try:
            # 整合多个系统
            memory = get_memory_system()
            graph = get_knowledge_graph()
            
            # 1. 存储知识
            memory.store(
                "Integration testing combines multiple components",
                MemoryType.LONG_TERM,
                importance=0.8
            )
            
            # 2. 构建知识图谱
            alice_id = graph.add_entity("Alice", "Person")
            test_id = graph.add_entity("Test", "Concept")
            graph.add_relation(alice_id, test_id, "performs")
            
            # 3. 检索和推理
            results = memory.retrieve("integration")
            
            success = len(results) > 0
            
            duration = (datetime.utcnow() - start).total_seconds()
            
            result = TestResult(
                test_name=test_name,
                success=success,
                duration=duration,
                metrics={
                    "components_tested": 3,
                    "retrieval_success": len(results) > 0
                }
            )
            
            self.results.append(result)
            logger.info("test_completed", test=test_name, success=success)
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds()
            result = TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )
            self.results.append(result)
            logger.error("test_failed", test=test_name, error=str(e))
            return result
    
    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        failed = total - successful
        avg_duration = sum(r.duration for r in self.results) / total if total > 0 else 0
        
        return {
            "total_tests": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "average_duration": avg_duration,
            "test_results": [
                {
                    "name": r.test_name,
                    "success": r.success,
                    "duration": r.duration,
                    "error": r.error
                }
                for r in self.results
            ]
        }


def initialize_entire_system() -> None:
    """初始化整个系统"""
    logger.info("initializing_entire_system")
    
    # 初始化各个子系统
    class DummyLLMManager:
        async def generate(self, text: str, model: str = None) -> str:
            return f"Generated: {text}"
    
    # 注意：实际使用需要正确的初始化顺序
    initialize_agent_orchestration(DummyLLMManager())
    initialize_distributed_system()
    initialize_cognitive_system()
    initialize_self_evolution()
    
    logger.info("entire_system_initialized")
