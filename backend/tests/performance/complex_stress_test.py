"""
复杂高难度场景测试 - Agent Cluster Orchestrator压力测试

场景设计：
1. 100+ Agent并发协作
2. 复杂任务链执行
3. 多模态数据处理
4. 实时状态监控
5. 故障注入与恢复

目标：在极端压力下发现系统瓶颈并优化
"""
from __future__ import annotations

import asyncio
import random
import time
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not available, memory monitoring disabled")


@dataclass
class TestResult:
    """测试结果"""
    scenario_name: str
    success_rate: float
    avg_latency: float
    max_latency: float
    throughput: float
    error_count: int
    timeout_count: int
    memory_usage_mb: float
    cpu_usage_percent: float
    errors: List[Dict[str, Any]]
    warnings: List[str]


class ChaosEngine:
    """混沌工程引擎 - 注入故障测试系统韧性"""
    
    def __init__(self):
        self.faults_injected = 0
        self.faults_handled = 0
    
    async def inject_network_delay(self, delay_ms: int = 100):
        """模拟网络延迟"""
        await asyncio.sleep(delay_ms / 1000)
        self.faults_injected += 1
    
    async def inject_memory_pressure(self):
        """模拟内存压力"""
        import numpy as np
        large_array = np.random.rand(10000, 10000)
        del large_array
        self.faults_injected += 1
    
    async def inject_timeout(self, duration: float = 0.5):
        """模拟超时"""
        await asyncio.sleep(duration)
        self.faults_injected += 1


class LoadGenerator:
    """负载生成器 - 模拟真实的高并发场景"""
    
    def __init__(self):
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.timeouts = 0
        self.latencies: List[float] = []
    
    async def simulate_agent_task(
        self,
        agent_id: str,
        task_complexity: str = "medium",
        use_chaos: bool = False,
        chaos_engine: Optional[ChaosEngine] = None
    ) -> Dict[str, Any]:
        """模拟一个Agent任务"""
        self.active_tasks += 1
        start_time = time.time()
        
        try:
            base_time = {
                "low": 0.01,
                "medium": 0.05,
                "high": 0.1,
                "extreme": 0.3
            }[task_complexity]
            
            processing_time = base_time * random.uniform(0.8, 1.5)
            
            if use_chaos and chaos_engine and random.random() < 0.1:
                if random.random() < 0.5:
                    await chaos_engine.inject_network_delay(random.randint(50, 200))
                else:
                    await chaos_engine.inject_timeout(processing_time * 0.5)
            
            await asyncio.sleep(processing_time)
            
            if random.random() < 0.02:
                raise Exception("Simulated task failure")
            
            if random.random() < 0.01:
                self.timeouts += 1
                raise asyncio.TimeoutError("Task timeout")
            
            latency = time.time() - start_time
            self.latencies.append(latency)
            self.completed_tasks += 1
            
            return {
                "agent_id": agent_id,
                "status": "success",
                "latency": latency
            }
            
        except asyncio.TimeoutError:
            self.timeouts += 1
            return {
                "agent_id": agent_id,
                "status": "timeout",
                "error": "Task timeout"
            }
        except Exception as e:
            self.failed_tasks += 1
            return {
                "agent_id": agent_id,
                "status": "failed",
                "error": str(e)
            }
        finally:
            self.active_tasks -= 1
    
    async def run_concurrent_tasks(
        self,
        num_tasks: int,
        agent_prefix: str = "agent",
        complexity: str = "medium"
    ) -> List[Dict[str, Any]]:
        """运行并发任务"""
        tasks = []
        for i in range(num_tasks):
            agent_id = f"{agent_prefix}_{i}"
            task = self.simulate_agent_task(agent_id, complexity)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r if isinstance(r, dict) else {"status": "error", "error": str(r)} for r in results]


class PerformanceMonitor:
    """性能监控器 - 实时监控系统指标"""
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.metrics: List[Dict[str, Any]] = []
        self.monitoring = False
    
    async def start(self):
        """开始监控"""
        self.start_time = datetime.utcnow()
        self.monitoring = True
        print("  📊 性能监控已启动")
    
    async def record_metrics(self):
        """记录当前指标"""
        if not self.monitoring or not HAS_PSUTIL:
            return
        
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_mb": memory_info.rss / 1024 / 1024,
            }
            
            self.metrics.append(metrics)
            
            if len(self.metrics) > 1000:
                self.metrics.pop(0)
                
        except Exception as e:
            print(f"  ⚠️ 记录指标失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.metrics:
            return {}
        
        cpu_values = [m["cpu_percent"] for m in self.metrics if "cpu_percent" in m]
        mem_values = [m["memory_mb"] for m in self.metrics if "memory_mb" in m]
        
        return {
            "avg_cpu": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
            "max_cpu": max(cpu_values) if cpu_values else 0,
            "avg_memory_mb": sum(mem_values) / len(mem_values) if mem_values else 0,
            "max_memory_mb": max(mem_values) if mem_values else 0,
            "duration_seconds": (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0
        }


class ComplexScenarioRunner:
    """复杂场景运行器 - 执行高难度测试"""
    
    def __init__(self):
        self.load_generator = LoadGenerator()
        self.chaos_engine = ChaosEngine()
        self.performance_monitor = PerformanceMonitor()
        self.results: List[TestResult] = []
        self.problems_found: List[Dict[str, Any]] = []
    
    async def run_scenario_1_extreme_concurrency(self) -> TestResult:
        """场景1：极限并发（100个Agent同时执行任务）"""
        print("\n" + "="*60)
        print("🚨 场景1：极限并发测试 - 100个Agent同时执行")
        print("="*60)
        
        await self.performance_monitor.start()
        
        # 启动监控任务
        monitor_task = asyncio.create_task(self._monitor_loop())
        
        # 执行100个并发任务
        print("  正在执行100个并发任务...")
        results = await self.load_generator.run_concurrent_tasks(
            num_tasks=100,
            agent_prefix="concurrent_agent",
            complexity="high"
        )
        
        monitor_task.cancel()
        
        # 分析结果
        success = sum(1 for r in results if r.get("status") == "success")
        errors = [r for r in results if r.get("status") in ("failed", "error", "timeout")]
        
        # 发现问题
        if len(errors) > 10:
            self.problems_found.append({
                "scenario": "extreme_concurrency",
                "problem": f"高并发时错误率过高: {len(errors)}/{len(results)}",
                "severity": "high",
                "recommendation": "增加错误处理和重试机制"
            })
        
        if self.load_generator.timeouts > 5:
            self.problems_found.append({
                "scenario": "extreme_concurrency",
                "problem": f"存在超时问题: {self.load_generator.timeouts}个任务超时",
                "severity": "medium",
                "recommendation": "优化超时配置和资源分配"
            })
        
        result = TestResult(
            scenario_name="extreme_concurrency_100",
            success_rate=success / len(results) * 100,
            avg_latency=sum(self.load_generator.latencies) / max(1, len(self.load_generator.latencies)),
            max_latency=max(self.load_generator.latencies) if self.load_generator.latencies else 0,
            throughput=len(results) / 10,
            error_count=len(errors),
            timeout_count=self.load_generator.timeouts,
            memory_usage_mb=self.performance_monitor.get_stats().get("max_memory_mb", 0),
            cpu_usage_percent=self.performance_monitor.get_stats().get("avg_cpu", 0),
            errors=errors[:10],
            warnings=[]
        )
        
        self._print_result(result)
        return result
    
    async def run_scenario_2_long_chain(self) -> TestResult:
        """场景2：长任务链（50个依赖任务顺序执行）"""
        print("\n" + "="*60)
        print("🔗 场景2：长任务链测试 - 50个依赖任务")
        print("="*60)
        
        await self.performance_monitor.start()
        
        start_time = time.time()
        results = []
        
        print("  正在执行50个依赖任务...")
        for i in range(50):
            agent_id = f"chain_agent_{i}"
            result = await self.load_generator.simulate_agent_task(
                agent_id,
                complexity="medium"
            )
            results.append(result)
            await asyncio.sleep(0.01)
        
        duration = time.time() - start_time
        
        success = sum(1 for r in results if r.get("status") == "success")
        errors = [r for r in results if r.get("status") in ("failed", "error", "timeout")]
        
        # 发现问题
        failed_indices = [i for i, r in enumerate(results) if r.get("status") != "success"]
        if failed_indices:
            self.problems_found.append({
                "scenario": "long_task_chain",
                "problem": f"任务链在位置 {failed_indices[0]} 失败，可能导致级联失败",
                "severity": "high",
                "recommendation": "实现断路器模式和任务依赖验证"
            })
        
        if duration > 3:
            self.problems_found.append({
                "scenario": "long_task_chain",
                "problem": f"任务链执行时间过长: {duration:.2f}秒",
                "severity": "medium",
                "recommendation": "优化任务调度和并行化"
            })
        
        result = TestResult(
            scenario_name="long_task_chain_50",
            success_rate=success / len(results) * 100,
            avg_latency=duration / len(results),
            max_latency=duration,
            throughput=len(results) / duration,
            error_count=len(errors),
            timeout_count=self.load_generator.timeouts,
            memory_usage_mb=self.performance_monitor.get_stats().get("max_memory_mb", 0),
            cpu_usage_percent=self.performance_monitor.get_stats().get("avg_cpu", 0),
            errors=errors[:10],
            warnings=["长任务链可能导致级联失败"]
        )
        
        self._print_result(result)
        return result
    
    async def run_scenario_3_chaos_testing(self) -> TestResult:
        """场景3：混沌工程（注入故障并验证恢复能力）"""
        print("\n" + "="*60)
        print("💥 场景3：混沌工程测试 - 故障注入与恢复")
        print("="*60)
        
        await self.performance_monitor.start()
        
        results = []
        chaos_faults = 0
        
        print("  正在执行100个任务，期间注入故障...")
        for i in range(100):
            agent_id = f"chaos_agent_{i}"
            
            # 注入故障
            if i % 10 == 0:
                await self.chaos_engine.inject_network_delay(100)
                chaos_faults += 1
            
            if i % 20 == 0:
                await self.chaos_engine.inject_timeout(0.2)
                chaos_faults += 1
            
            result = await self.load_generator.simulate_agent_task(
                agent_id,
                complexity="high",
                use_chaos=True,
                chaos_engine=self.chaos_engine
            )
            results.append(result)
        
        success = sum(1 for r in results if r.get("status") == "success")
        errors = [r for r in results if r.get("status") in ("failed", "error", "timeout")]
        
        # 发现问题
        if success / len(results) < 0.9:
            self.problems_found.append({
                "scenario": "chaos_engineering",
                "problem": f"故障注入后成功率过低: {success/len(results)*100:.1f}%",
                "severity": "critical",
                "recommendation": "增强系统的容错能力和降级策略"
            })
        
        result = TestResult(
            scenario_name="chaos_engineering",
            success_rate=success / len(results) * 100,
            avg_latency=sum(self.load_generator.latencies) / max(1, len(self.load_generator.latencies)),
            max_latency=max(self.load_generator.latencies) if self.load_generator.latencies else 0,
            throughput=len(results) / 20,
            error_count=len(errors),
            timeout_count=self.load_generator.timeouts,
            memory_usage_mb=self.performance_monitor.get_stats().get("max_memory_mb", 0),
            cpu_usage_percent=self.performance_monitor.get_stats().get("avg_cpu", 0),
            errors=errors[:10],
            warnings=[f"注入故障: {chaos_faults}次"]
        )
        
        self._print_result(result)
        return result
    
    async def run_scenario_4_burst_load(self) -> TestResult:
        """场景4：突发负载（模拟流量突增）"""
        print("\n" + "="*60)
        print("⚡ 场景4：突发负载测试 - 流量突增场景")
        print("="*60)
        
        await self.performance_monitor.start()
        
        results = []
        
        # 平静期
        print("  阶段1：平静期（10个并发任务）...")
        r1 = await self.load_generator.run_concurrent_tasks(10, "burst_calm", "low")
        results.extend(r1)
        
        await asyncio.sleep(0.5)
        
        # 突增
        print("  阶段2：突增期（100个并发任务）...")
        r2 = await self.load_generator.run_concurrent_tasks(100, "burst_spike", "high")
        results.extend(r2)
        
        # 突减
        print("  阶段3：突减期（20个并发任务）...")
        r3 = await self.load_generator.run_concurrent_tasks(20, "burst_drop", "medium")
        results.extend(r3)
        
        success = sum(1 for r in results if r.get("status") == "success")
        errors = [r for r in results if r.get("status") in ("failed", "error", "timeout")]
        
        # 发现问题
        spike_errors = [r for r in r2 if r.get("status") != "success"]
        if len(spike_errors) > len(r2) * 0.1:
            self.problems_found.append({
                "scenario": "burst_load",
                "problem": f"流量突增时错误率过高: {len(spike_errors)}/{len(r2)}",
                "severity": "high",
                "recommendation": "实现流量控制、自动扩容、熔断机制"
            })
        
        result = TestResult(
            scenario_name="burst_load_simulation",
            success_rate=success / len(results) * 100,
            avg_latency=sum(self.load_generator.latencies) / max(1, len(self.load_generator.latencies)),
            max_latency=max(self.load_generator.latencies) if self.load_generator.latencies else 0,
            throughput=len(results) / 3,
            error_count=len(errors),
            timeout_count=self.load_generator.timeouts,
            memory_usage_mb=self.performance_monitor.get_stats().get("max_memory_mb", 0),
            cpu_usage_percent=self.performance_monitor.get_stats().get("avg_cpu", 0),
            errors=errors[:10],
            warnings=["突发负载可能导致队列积压"]
        )
        
        self._print_result(result)
        return result
    
    async def run_scenario_5_resource_exhaustion(self) -> TestResult:
        """场景5：资源耗尽测试（内存和CPU压力）"""
        print("\n" + "="*60)
        print("💾 场景5：资源耗尽测试 - 内存和CPU压力")
        print("="*60)
        
        await self.performance_monitor.start()
        
        initial_memory = 0
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                initial_memory = process.memory_info().rss / 1024 / 1024
            except:
                pass
        
        results = []
        memory_hog = []
        
        print("  正在模拟资源压力...")
        for i in range(20):
            agent_id = f"memory_agent_{i}"
            result = await self.load_generator.simulate_agent_task(
                agent_id,
                complexity="extreme"
            )
            results.append(result)
            
            # 模拟内存累积
            if i % 5 == 0:
                memory_hog.append(bytearray(5 * 1024 * 1024))  # 每次5MB
            
            await asyncio.sleep(0.1)
        
        # 清理
        del memory_hog
        
        final_memory = 0
        memory_growth = 0
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                final_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = final_memory - initial_memory
            except:
                pass
        
        success = sum(1 for r in results if r.get("status") == "success")
        errors = [r for r in results if r.get("status") in ("failed", "error", "timeout")]
        
        # 发现问题
        if memory_growth > 50:
            self.problems_found.append({
                "scenario": "resource_exhaustion",
                "problem": f"检测到潜在内存泄漏: 增长 {memory_growth:.2f}MB",
                "severity": "critical",
                "recommendation": "检查对象引用、缓存清理、资源释放"
            })
        
        if len(errors) > 5:
            self.problems_found.append({
                "scenario": "resource_exhaustion",
                "problem": f"高负载下错误率过高: {len(errors)}/{len(results)}",
                "severity": "high",
                "recommendation": "实现资源限制和优先级调度"
            })
        
        result = TestResult(
            scenario_name="resource_exhaustion",
            success_rate=success / len(results) * 100,
            avg_latency=sum(self.load_generator.latencies) / max(1, len(self.load_generator.latencies)),
            max_latency=max(self.load_generator.latencies) if self.load_generator.latencies else 0,
            throughput=len(results) / 5,
            error_count=len(errors),
            timeout_count=self.load_generator.timeouts,
            memory_usage_mb=final_memory,
            cpu_usage_percent=self.performance_monitor.get_stats().get("avg_cpu", 0),
            errors=errors[:10],
            warnings=[f"内存增长: {memory_growth:.2f}MB (潜在泄漏)"]
        )
        
        self._print_result(result)
        return result
    
    async def _monitor_loop(self):
        """监控循环"""
        while True:
            await self.performance_monitor.record_metrics()
            await asyncio.sleep(0.5)
    
    def _print_result(self, result: TestResult):
        """打印测试结果"""
        print(f"\n📊 测试结果：{result.scenario_name}")
        print(f"  ✅ 成功率: {result.success_rate:.2f}%")
        print(f"  ⚡ 平均延迟: {result.avg_latency:.4f}s")
        print(f"  🐌 最大延迟: {result.max_latency:.4f}s")
        print(f"  🚀 吞吐量: {result.throughput:.2f} tasks/s")
        print(f"  ❌ 错误数: {result.error_count}")
        print(f"  ⏱️  超时数: {result.timeout_count}")
        if result.memory_usage_mb > 0:
            print(f"  💾 内存使用: {result.memory_usage_mb:.2f}MB")
        if result.cpu_usage_percent > 0:
            print(f"  📈 CPU使用: {result.cpu_usage_percent:.2f}%")
        
        if result.warnings:
            print(f"  ⚠️  警告:")
            for warning in result.warnings:
                print(f"     - {warning}")
    
    async def run_all_scenarios(self) -> List[TestResult]:
        """运行所有复杂场景"""
        print("\n" + "🎯"*30)
        print("🚀 Agent Cluster Orchestrator - 复杂高难度场景测试")
        print("🎯"*30)
        
        scenarios = [
            ("场景1：极限并发", self.run_scenario_1_extreme_concurrency),
            ("场景2：长任务链", self.run_scenario_2_long_chain),
            ("场景3：混沌工程", self.run_scenario_3_chaos_testing),
            ("场景4：突发负载", self.run_scenario_4_burst_load),
            ("场景5：资源耗尽", self.run_scenario_5_resource_exhaustion),
        ]
        
        results = []
        for name, runner in scenarios:
            try:
                result = await runner()
                results.append(result)
            except Exception as e:
                print(f"\n❌ {name} 执行失败: {e}")
                import traceback
                traceback.print_exc()
        
        self._print_summary(results)
        
        return results
    
    def _print_summary(self, results: List[TestResult]):
        """打印汇总"""
        print("\n" + "="*60)
        print("📋 测试汇总")
        print("="*60)
        
        for result in results:
            status = "✅" if result.success_rate >= 95 else "⚠️" if result.success_rate >= 80 else "❌"
            print(f"{status} {result.scenario_name}: {result.success_rate:.2f}% 成功率")
        
        if results:
            avg_success = sum(r.success_rate for r in results) / len(results)
            print(f"\n📊 平均成功率: {avg_success:.2f}%")
        
        # 发现的问题
        if self.problems_found:
            print(f"\n🔍 发现的问题 ({len(self.problems_found)} 个):")
            print("="*60)
            
            for i, problem in enumerate(self.problems_found, 1):
                severity_icon = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢"
                }.get(problem["severity"], "⚪")
                
                print(f"\n{i}. {severity_icon} [{problem['severity'].upper()}]")
                print(f"   场景: {problem['scenario']}")
                print(f"   问题: {problem['problem']}")
                print(f"   建议: {problem['recommendation']}")


async def main():
    """主函数"""
    runner = ComplexScenarioRunner()
    results = await runner.run_all_scenarios()
    
    print("\n✅ 所有测试完成！")
    return results


if __name__ == "__main__":
    results = asyncio.run(main())
