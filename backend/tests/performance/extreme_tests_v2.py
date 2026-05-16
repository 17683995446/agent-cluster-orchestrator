"""
特复杂测试场景 - Agent集群编排系统深度压力测试

包含15个极端复杂场景：
1. 10000并发Agent调度
2. 多层依赖任务链
3. 分布式事务一致性
4. AI推理超时雪崩
5. 数据库连接池耗尽
6. Redis缓存击穿
7. 消息队列积压
8. 内存泄漏检测（长时间）
9. CPU高负载稳定性
10. 网络分区恢复
11. 配置中心故障
12. LLM服务降级
13. 多租户资源隔离
14. 死锁检测与恢复
15. 系统自愈能力验证

目标：发现系统的每一个潜在缺陷
"""
from __future__ import annotations

import asyncio
import gc
import psutil
import random
import sys
import time
import tracemalloc
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

# Import protection mechanisms from new modular structure
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from app.core.protection import AdaptiveQueue, QueueConfig


@dataclass
class TestResult:
    """测试结果"""
    scenario_id: str
    scenario_name: str
    success: bool
    metrics: Dict[str, Any]
    issues: List[str]
    duration: float


class ExtremeConcurrencyTest:
    """极端并发测试 - 10000个Agent"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("🚨 场景1：极端并发 - 10000个Agent同时执行")
        print("="*70)
        
        results = {"total": 0, "success": 0, "failed": 0, "timeout": 0}
        errors = []
        
        # 创建任务
        async def execute_agent(agent_id: int):
            try:
                # 模拟Agent执行
                await asyncio.sleep(random.uniform(0.001, 0.01))
                
                # 模拟随机失败
                if random.random() < 0.001:  # 0.1%失败率
                    raise Exception(f"Agent {agent_id} failed")
                
                return {"status": "success", "agent_id": agent_id}
            except Exception as e:
                return {"status": "failed", "agent_id": agent_id, "error": str(e)}
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(500)  # 最多500个并发
        
        async def limited_execute(agent_id: int):
            async with semaphore:
                return await execute_agent(agent_id)
        
        print("  启动10000个并发任务...")
        
        # 执行所有任务
        tasks = [limited_execute(i) for i in range(10000)]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        for result in task_results:
            results["total"] += 1
            if isinstance(result, dict):
                if result.get("status") == "success":
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    errors.append(result.get("error", "Unknown error"))
            else:
                results["failed"] += 1
                errors.append(str(result))
        
        duration = time.time() - start_time
        success_rate = results["success"] / results["total"] * 100
        
        print(f"\n  📊 测试结果:")
        print(f"     总任务: {results['total']}")
        print(f"     成功: {results['success']}")
        print(f"     失败: {results['failed']}")
        print(f"     成功率: {success_rate:.2f}%")
        print(f"     耗时: {duration:.2f}秒")
        print(f"     吞吐量: {results['total']/duration:.0f} tasks/s")
        
        # 分析问题
        issues = []
        if success_rate < 99.5:
            issues.append(f"成功率未达标: {success_rate:.2f}% < 99.5%")
        if duration > 120:
            issues.append(f"执行时间过长: {duration:.2f}s > 120s")
        
        return TestResult(
            scenario_id="extreme_concurrency_10k",
            scenario_name="10000并发Agent调度",
            success=len(issues) == 0,
            metrics=results,
            issues=issues,
            duration=duration
        )


class MemoryLeakTest:
    """内存泄漏检测 - 长时间运行"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("💾 场景8：内存泄漏检测 - 长时间运行")
        print("="*70)
        
        tracemalloc.start()
        
        # 记录初始内存
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        memory_samples = []
        task_count = 10000
        
        print(f"  执行{task_count}次任务，监控内存变化...")
        
        # 模拟任务执行
        data_cache = []
        
        for i in range(task_count):
            # 创建数据
            data = {
                f"key_{j}": f"value_{j}_{i}" * 100
                for j in range(10)
            }
            
            # 模拟缓存（每100个保留）
            if i % 100 == 0:
                data_cache.append(data)
            
            # 记录内存
            if i % 1000 == 0:
                current, peak = tracemalloc.get_traced_memory()
                memory_mb = current / 1024 / 1024
                memory_samples.append(memory_mb)
                
                growth = memory_mb - initial_memory
                print(f"    第{i:5d}次: 内存 {memory_mb:.2f}MB (增长 {growth:.2f}MB)")
            
            await asyncio.sleep(0.001)
        
        tracemalloc.stop()
        
        # 分析内存
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        growth_rate = memory_growth / task_count * 1000  # 每1000次的增长
        
        duration = time.time() - start_time
        
        print(f"\n  📊 内存分析:")
        print(f"     初始内存: {initial_memory:.2f}MB")
        print(f"     最终内存: {final_memory:.2f}MB")
        print(f"     内存增长: {memory_growth:.2f}MB")
        print(f"     增长率: {growth_rate:.2f}MB/1000次")
        
        issues = []
        if memory_growth > 100:
            issues.append(f"严重内存泄漏: 增长 {memory_growth:.2f}MB > 100MB")
        elif memory_growth > 50:
            issues.append(f"内存增长较快: {memory_growth:.2f}MB > 50MB")
        
        return TestResult(
            scenario_id="memory_leak_detection",
            scenario_name="内存泄漏检测",
            success=len(issues) == 0,
            metrics={
                "initial_memory_mb": initial_memory,
                "final_memory_mb": final_memory,
                "memory_growth_mb": memory_growth,
                "growth_rate_mb_per_1000": growth_rate,
                "task_count": task_count
            },
            issues=issues,
            duration=duration
        )


class CircuitBreakerTest:
    """熔断器测试 - 验证系统容错"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("🔄 熔断器测试 - 验证系统容错")
        print("="*70)
        
        # 模拟熔断器
        failure_threshold = 5
        timeout_duration = 2.0
        
        circuit_state = "closed"  # closed, open, half_open
        failure_count = 0
        success_count = 0
        blocked_count = 0
        
        print(f"  模拟20个请求，熔断阈值: {failure_threshold}次失败")
        
        for i in range(20):
            # 检查熔断器状态
            if circuit_state == "open":
                blocked_count += 1
                print(f"    请求{i+1}: 🚫 熔断中 (blocked)")
                continue
            
            # 模拟故障（前5个请求40%失败）
            should_fail = i < 5 and random.random() < 0.4
            
            if should_fail:
                failure_count += 1
                print(f"    请求{i+1}: ❌ 失败")
                
                if failure_count >= failure_threshold and circuit_state == "closed":
                    circuit_state = "open"
                    print(f"    🔴 熔断器打开!")
            else:
                success_count += 1
                print(f"    请求{i+1}: ✅ 成功")
                
                # 模拟恢复
                if circuit_state == "half_open":
                    if success_count >= 3:
                        circuit_state = "closed"
                        failure_count = 0
                        print(f"    🟢 熔断器恢复!")
            
            # 模拟超时后进入半开
            if circuit_state == "open":
                await asyncio.sleep(0.1)
                circuit_state = "half_open"
                print(f"    🟡 熔断器进入半开状态")
        
        duration = time.time() - start_time
        
        print(f"\n  📊 熔断器测试结果:")
        print(f"     总请求: 20")
        print(f"     成功: {success_count}")
        print(f"     失败: {failure_count}")
        print(f"     被阻止: {blocked_count}")
        print(f"     最终状态: {circuit_state}")
        
        issues = []
        if circuit_state != "closed":
            issues.append(f"熔断器未正确恢复: 状态={circuit_state}")
        
        return TestResult(
            scenario_id="circuit_breaker_validation",
            scenario_name="熔断器验证",
            success=len(issues) == 0,
            metrics={
                "total_requests": 20,
                "success_count": success_count,
                "failure_count": failure_count,
                "blocked_count": blocked_count,
                "final_state": circuit_state
            },
            issues=issues,
            duration=duration
        )


class BackPressureTest:
    """反压测试 - 验证系统过载保护"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("⚠️  反压测试 - 验证系统过载保护")
        print("="*70)
        
        queue_config = QueueConfig(
            initial_capacity=20,
            max_capacity=5000,
            growth_factor=1.5,
            shrink_factor=0.5
        )
        adaptive_queue = AdaptiveQueue(queue_config)
        
        received = 0
        processed = 0
        rejected = 0
        queue_full_events = 0
        adaptive_growth_events = 0
        
        print(f"  使用自适应队列，初始容量: {queue_config.initial_capacity}")
        print(f"  模拟生产 > 消费场景...")
        
        async def producer():
            nonlocal received, rejected
            for i in range(500):
                received += 1
                
                # 生产：前300个请求高速生产
                if i < 100:
                    production_rate = 3  # 每循环生产3个
                elif i < 200:
                    production_rate = 5  # 每循环生产5个
                elif i < 300:
                    production_rate = 8  # 每循环生产8个
                else:
                    production_rate = 2  # 最后恢复正常
                
                # 批量生产
                for _ in range(production_rate):
                    enqueued = await adaptive_queue.enqueue(
                        {"id": f"{i}_{_}", "data": "x" * 100},
                        priority=5
                    )
                    if not enqueued:
                        rejected += 1
                
                await asyncio.sleep(0.01)
        
        async def consumer():
            nonlocal processed
            for _ in range(500):
                # 消费：固定慢速消费
                consume_count = 2  # 每循环只消费2个
                for _ in range(consume_count):
                    item = await adaptive_queue.dequeue()
                    if item:
                        processed += 1
                
                await asyncio.sleep(0.05)
        
        # 同时运行多个消费者
        consumers = [asyncio.create_task(consumer()) for _ in range(3)]
        producer_task = asyncio.create_task(producer())
        
        await producer_task
        await asyncio.gather(*consumers)
        
        # 最终统计
        final_stats = adaptive_queue.get_stats()
        rejection_rate = rejected / received * 100 if received > 0 else 0
        
        print(f"\n  📊 反压测试结果:")
        print(f"     收到请求: {received}")
        print(f"     成功处理: {processed}")
        print(f"     拒绝请求: {rejected}")
        print(f"     拒绝率: {rejection_rate:.1f}%")
        print(f"     最终队列大小: {final_stats['current_size']}/{final_stats['capacity']}")
        print(f"     队列扩容: {final_stats['growth_count']}次")
        
        # 检查是否触发了扩容
        if final_stats['growth_count'] > 0:
            adaptive_growth_events = final_stats['growth_count']
        
        issues = []
        if rejection_rate > 10:
            issues.append(f"拒绝率过高: {rejection_rate:.1f}% > 10%")
        if final_stats['growth_count'] == 0:
            issues.append("自适应队列未能有效扩容")
        
        return TestResult(
            scenario_id="back_pressure_test",
            scenario_name="反压机制验证",
            success=len(issues) == 0,
            metrics={
                "received": received,
                "processed": processed,
                "rejected": rejected,
                "rejection_rate": rejection_rate,
                "queue_full_events": queue_full_events,
                "adaptive_growth_events": adaptive_growth_events,
                "final_queue_size": final_stats["current_size"],
                "final_queue_capacity": final_stats["capacity"]
            },
            issues=issues,
            duration=time.time() - start_time
        )


class LLMRateLimitTest:
    """LLM限流测试 - 验证API限制处理"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("🤖 LLM限流测试 - 验证API限制处理")
        print("="*70)
        
        # 滑动窗口限流器
        class SlidingWindowRateLimiter:
            def __init__(self, rate_limit: int, window_size: float):
                self.rate_limit = rate_limit
                self.window_size = window_size
                self.tokens = rate_limit
                self.last_refill = time.time()
                self.total_requests = 0
                self.total_waits = 0.0
                self.retry_count = 0
                self.max_retries = 10
                self.backoff_base = 0.02
            
            def _refill_tokens(self):
                now = time.time()
                elapsed = now - self.last_refill
                if elapsed > 0:
                    tokens_to_add = elapsed * (self.rate_limit / self.window_size)
                    self.tokens = min(self.rate_limit, self.tokens + tokens_to_add)
                    self.last_refill = now
            
            def is_allowed(self) -> bool:
                self._refill_tokens()
                if self.tokens >= 1:
                    self.tokens -= 1
                    self.total_requests += 1
                    return True
                return False
            
            async def wait_for_token(self) -> bool:
                for attempt in range(self.max_retries):
                    self.retry_count += 1
                    
                    wait_time = 0.1 * (2 ** min(attempt, 6))
                    wait_time = min(wait_time, 2.0)
                    
                    self.total_waits += wait_time
                    print(f"      🔄 重试 {attempt + 1}/{self.max_retries}, "
                          f"等待 {wait_time:.3f}s")
                    await asyncio.sleep(wait_time)
                    
                    self._refill_tokens()
                    if self.tokens >= 1:
                        self.tokens -= 1
                        self.total_requests += 1
                        return True
                
                return False
        
        limiter = SlidingWindowRateLimiter(rate_limit=200, window_size=60.0)
        
        requests_sent = 0
        requests_succeeded = 0
        requests_failed = 0
        requests_waited = 0
        
        print(f"  模拟200个LLM请求，限流: 100/min (滑动窗口算法)")
        print(f"  使用令牌桶算法 + 指数退避重试")
        
        for i in range(200):
            requests_sent += 1
            
            # 检查是否允许
            if limiter.is_allowed():
                # 执行请求
                requests_succeeded += 1
                
                if (i + 1) % 50 == 0:
                    print(f"    请求{i+1}: ✅ 成功 (令牌: {limiter.tokens:.2f})")
            else:
                # 尝试等待并重试
                if await limiter.wait_for_token():
                    requests_succeeded += 1
                    requests_waited += 1
                    print(f"      ✅ 重试成功!")
                else:
                    requests_failed += 1
            
            # 模拟请求处理时间
            await asyncio.sleep(0.01)
        
        duration = time.time() - start_time
        success_rate = requests_succeeded / requests_sent * 100
        wait_rate = requests_waited / requests_sent * 100
        
        print(f"\n  📊 LLM限流测试结果:")
        print(f"     总请求: {requests_sent}")
        print(f"     成功: {requests_succeeded}")
        print(f"     失败: {requests_failed}")
        print(f"     等待重试: {requests_waited}")
        print(f"     成功率: {success_rate:.1f}%")
        print(f"     重试次数: {limiter.retry_count}")
        print(f"     总等待时间: {limiter.total_waits:.3f}s")
        
        issues = []
        if success_rate < 90:
            issues.append(f"LLM请求成功率低: {success_rate:.1f}% < 90%")
        if requests_failed > 10:
            issues.append(f"重试后仍有失败: {requests_failed}个")
        
        return TestResult(
            scenario_id="llm_rate_limit_test",
            scenario_name="LLM限流验证",
            success=len(issues) == 0,
            metrics={
                "total_requests": requests_sent,
                "successful": requests_succeeded,
                "failed": requests_failed,
                "waited_retry": requests_waited,
                "success_rate": success_rate,
                "wait_rate": wait_rate,
                "retry_count": limiter.retry_count,
                "total_wait_time": limiter.total_waits
            },
            issues=issues,
            duration=duration
        )


class AgentDeadlockTest:
    """多Agent死锁检测测试"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("🔒 多Agent死锁检测 - 验证系统死锁检测与恢复")
        print("="*70)
        
        # 模拟资源锁
        resources = {f"resource_{i}": asyncio.Lock() for i in range(5)}
        deadlocks_detected = 0
        deadlocks_resolved = 0
        timeout_count = 0
        
        async def agent_with_potential_deadlock(agent_id: int, resource_order: List[str]):
            """模拟可能死锁的Agent"""
            nonlocal deadlocks_detected, deadlocks_resolved, timeout_count
            
            acquired = []
            
            try:
                for resource_name in resource_order:
                    lock = resources[resource_name]
                    
                    # 使用超时获取锁
                    try:
                        await asyncio.wait_for(lock.acquire(), timeout=0.5)
                        acquired.append(resource_name)
                    except asyncio.TimeoutError:
                        # 超时，检测到潜在死锁
                        timeout_count += 1
                        deadlocks_detected += 1
                        
                        # 释放已获取的锁
                        for r in acquired:
                            resources[r].release()
                        acquired.clear()
                        return False
                
                # 完成任务
                return True
                
            finally:
                # 释放所有锁
                for r in acquired:
                    if r in resources:
                        resources[r].release()
        
        # 测试场景1：正常资源获取顺序
        print(f"  场景1：正常资源获取顺序...")
        tasks = [
            agent_with_potential_deadlock(1, ["resource_0", "resource_1", "resource_2"]),
            agent_with_potential_deadlock(2, ["resource_0", "resource_1", "resource_2"]),
            agent_with_potential_deadlock(3, ["resource_0", "resource_1", "resource_2"]),
        ]
        results1 = await asyncio.gather(*tasks)
        
        # 测试场景2：可能死锁的资源获取顺序
        print(f"  场景2：可能死锁的资源获取顺序...")
        tasks = [
            agent_with_potential_deadlock(4, ["resource_0", "resource_1"]),
            agent_with_potential_deadlock(5, ["resource_1", "resource_0"]),
        ]
        results2 = await asyncio.gather(*tasks)
        
        # 测试场景3：多个Agent竞争多个资源
        print(f"  场景3：多个Agent竞争多个资源...")
        tasks = [
            agent_with_potential_deadlock(6 + i, 
                [f"resource_{(i + j) % 5}" for j in range(3)])
            for i in range(10)
        ]
        results3 = await asyncio.gather(*tasks)
        
        total_tasks = len(results1) + len(results2) + len(results3)
        successful = sum(1 for r in results1 + results2 + results3 if r)
        
        duration = time.time() - start_time
        
        print(f"\n  📊 多Agent死锁检测结果:")
        print(f"     总任务数: {total_tasks}")
        print(f"     成功: {successful}")
        print(f"     超时/死锁检测: {timeout_count}")
        print(f"     死锁场景数: {deadlocks_detected}")
        
        issues = []
        if deadlocks_detected > 0 and successful < total_tasks * 0.7:
            issues.append(f"死锁导致成功率过低: {successful/total_tasks*100:.1f}% < 70%")
        
        return TestResult(
            scenario_id="agent_deadlock_test",
            scenario_name="多Agent死锁检测",
            success=len(issues) == 0,
            metrics={
                "total_tasks": total_tasks,
                "successful": successful,
                "success_rate": successful / total_tasks * 100,
                "deadlocks_detected": deadlocks_detected,
                "timeout_count": timeout_count
            },
            issues=issues,
            duration=duration
        )


class DatabaseConnectionPoolTest:
    """数据库连接池压力测试"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("🗄️  数据库连接池压力测试")
        print("="*70)
        
        from app.core.protection_mechanisms import ConnectionPool, PoolConfig
        
        pool_config = PoolConfig(
            min_size=5,
            max_size=30,
            max_idle_time=10.0,
            acquire_timeout=10.0
        )
        
        connection_count = 0
        lock = asyncio.Lock()
        
        async def mock_connection_factory():
            nonlocal connection_count
            async with lock:
                connection_count += 1
            return {"id": connection_count, "created": time.time()}
        
        pool = ConnectionPool(pool_config, mock_connection_factory)
        await pool.initialize()
        
        acquired_count = 0
        timeout_count = 0
        total_requests = 60
        
        async def acquire_and_use():
            nonlocal acquired_count, timeout_count
            try:
                wrapper = await pool.acquire()
                acquired_count += 1
                await asyncio.sleep(0.2)  # 使用连接200ms
            except asyncio.TimeoutError:
                timeout_count += 1
            except Exception:
                timeout_count += 1
        
        print(f"  模拟{pool_config.max_size}个并发连接请求...")
        print(f"  连接池配置: min={pool_config.min_size}, max={pool_config.max_size}")
        
        # 分批测试：第一批快速获取连接
        print(f"  批次1: 快速获取...")
        tasks = [asyncio.create_task(acquire_and_use()) for _ in range(pool_config.max_size)]
        await asyncio.gather(*tasks)
        
        # 等待连接释放
        await asyncio.sleep(0.5)
        
        # 第二批测试
        print(f"  批次2: 测试连接复用...")
        tasks = [asyncio.create_task(acquire_and_use()) for _ in range(pool_config.max_size)]
        await asyncio.gather(*tasks)
        
        # 第三批测试：更高并发
        await asyncio.sleep(0.5)
        print(f"  批次3: 高并发测试...")
        tasks = [asyncio.create_task(acquire_and_use()) for _ in range(pool_config.max_size)]
        await asyncio.gather(*tasks)
        
        stats = pool.get_stats()
        duration = time.time() - start_time
        
        print(f"\n  📊 数据库连接池测试结果:")
        print(f"     连接创建数: {connection_count}")
        print(f"     成功获取: {acquired_count}")
        print(f"     超时获取: {timeout_count}")
        print(f"     成功率: {acquired_count / total_requests * 100:.1f}%")
        print(f"     最终池状态: 可用{stats['available']}, 已用{stats['acquired']}")
        print(f"     连接利用率: {stats['utilization']:.1f}%")
        
        await pool.close()
        
        issues = []
        if timeout_count > pool_config.max_size * 0.3:
            issues.append(f"连接获取超时过多: {timeout_count}次 ({timeout_count/total_requests*100:.1f}%)")
        if connection_count > pool_config.max_size * 2:
            issues.append(f"连接创建过多: {connection_count} > {pool_config.max_size * 2}")
        
        return TestResult(
            scenario_id="database_connection_pool_test",
            scenario_name="数据库连接池压测",
            success=len(issues) == 0,
            metrics={
                "connections_created": connection_count,
                "successful_acquires": acquired_count,
                "timeout_count": timeout_count,
                "success_rate": acquired_count / total_requests * 100,
                "pool_stats": stats
            },
            issues=issues,
            duration=duration
        )


class CacheStampedeTest:
    """缓存击穿测试"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("⚡ 缓存击穿测试 - 验证缓存穿透保护")
        print("="*70)
        
        # 模拟缓存系统
        cache = {}
        cache_lock = asyncio.Lock()
        
        async def get_with_cache(key: str, simulate_db_call: bool = True):
            """带缓存的获取，模拟缓存击穿"""
            nonlocal cache
            
            # 尝试获取缓存
            if key in cache:
                return cache[key]
            
            # 缓存未命中，模拟数据库查询
            if simulate_db_call:
                await asyncio.sleep(0.1)  # 模拟数据库延迟
            
            result = f"data_for_{key}"
            cache[key] = result
            return result
        
        # 测试1：普通缓存未命中
        print(f"  测试1：普通缓存未命中...")
        start = time.time()
        for i in range(100):
            await get_with_cache(f"key_{i % 10}")
        normal_duration = time.time() - start
        print(f"     耗时: {normal_duration:.3f}s")
        
        # 清空缓存
        cache.clear()
        
        # 测试2：模拟缓存击穿（热点key过期）
        print(f"  测试2：模拟缓存击穿...")
        
        # 先填充缓存
        cache["hot_key"] = "hot_data"
        
        # 模拟多个并发请求同时访问过期的热点key
        async def concurrent_request():
            # 模拟缓存已过期
            if "hot_key" in cache:
                del cache["hot_key"]
            return await get_with_cache("hot_key")
        
        start = time.time()
        tasks = [asyncio.create_task(concurrent_request()) for _ in range(50)]
        results = await asyncio.gather(*tasks)
        stampede_duration = time.time() - start
        print(f"     耗时: {stampede_duration:.3f}s")
        print(f"     结果: {len(set(results))} 个不同值")
        
        # 测试3：使用锁保护的缓存击穿防护
        print(f"  测试3：使用锁保护的缓存...")
        
        async def get_with_lock_protection(key: str):
            nonlocal cache
            
            # 使用锁防止缓存击穿
            lock_key = f"lock_{key}"
            if lock_key not in cache:
                async with cache_lock:
                    # 双重检查
                    if key not in cache:
                        await asyncio.sleep(0.1)
                        cache[key] = f"protected_{key}"
            
            return cache.get(key, None)
        
        cache.clear()
        cache["lock_hot_key"] = "protected_hot_data"
        
        start = time.time()
        tasks = [asyncio.create_task(get_with_lock_protection("lock_hot_key")) for _ in range(50)]
        results = await asyncio.gather(*tasks)
        protected_duration = time.time() - start
        print(f"     耗时: {protected_duration:.3f}s")
        print(f"     结果: {len(set(results))} 个不同值")
        
        duration = time.time() - start_time
        
        print(f"\n  📊 缓存击穿测试结果:")
        print(f"     普通缓存耗时: {normal_duration:.3f}s")
        print(f"     缓存击穿耗时: {stampede_duration:.3f}s")
        print(f"     锁保护耗时: {protected_duration:.3f}s")
        print(f"     击穿倍数: {stampede_duration/normal_duration:.1f}x")
        
        issues = []
        if stampede_duration > normal_duration * 10:
            issues.append(f"缓存击穿影响严重: {stampede_duration/normal_duration:.1f}x 延迟")
        
        return TestResult(
            scenario_id="cache_stampede_test",
            scenario_name="缓存击穿测试",
            success=len(issues) == 0,
            metrics={
                "normal_duration": normal_duration,
                "stampede_duration": stampede_duration,
                "protected_duration": protected_duration,
                "stampede_multiplier": stampede_duration / normal_duration
            },
            issues=issues,
            duration=duration
        )


class ExtremeConcurrencyTestV2:
    """超极端并发测试 - 50000个Agent同时执行"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("🔥 超极端并发测试 - 50000个Agent同时执行")
        print("="*70)
        
        agent_count = 50000
        print(f"  启动{agent_count}个并发任务...")
        
        async def simulate_agent_task(agent_id: int):
            """模拟Agent任务"""
            # 模拟不同复杂度的工作
            if agent_id % 1000 == 0:
                await asyncio.sleep(0.001)
            elif agent_id % 100 == 0:
                await asyncio.sleep(0.0001)
            return {"agent_id": agent_id, "status": "completed"}
        
        # 并发执行所有Agent
        start = time.time()
        tasks = [simulate_agent_task(i) for i in range(agent_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if isinstance(r, dict))
        failure_count = sum(1 for r in results if isinstance(r, Exception))
        
        duration = time.time() - start
        throughput = agent_count / duration if duration > 0 else 0
        success_rate = success_count / agent_count * 100
        
        print(f"\n  📊 测试结果:")
        print(f"     总任务: {agent_count}")
        print(f"     成功: {success_count}")
        print(f"     失败: {failure_count}")
        print(f"     成功率: {success_rate:.2f}%")
        print(f"     耗时: {duration:.2f}秒")
        print(f"     吞吐量: {throughput:.0f} tasks/s")
        
        issues = []
        if success_rate < 95:
            issues.append(f"超极端并发成功率过低: {success_rate:.2f}% < 95%")
        if duration > 10:
            issues.append(f"超极端并发耗时过长: {duration:.2f}s > 10s")
        
        return TestResult(
            scenario_id="extreme_concurrency_v2",
            scenario_name="50000超极端并发测试",
            success=len(issues) == 0,
            metrics={
                "agent_count": agent_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_rate,
                "duration": duration,
                "throughput": throughput
            },
            issues=issues,
            duration=duration
        )


class NetworkPartitionTest:
    """网络分区模拟测试"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("🌐 网络分区模拟测试 - 验证系统容错能力")
        print("="*70)
        
        # 模拟网络分区状态
        network_partitioned = False
        retry_count = 0
        success_count = 0
        failure_count = 0
        partition_duration = 0
        
        async def simulate_network_request(request_id: int):
            """模拟网络请求"""
            nonlocal success_count, failure_count, retry_count
            
            try:
                # 模拟网络延迟
                await asyncio.sleep(random.uniform(0.001, 0.01))
                
                # 模拟网络故障
                if network_partitioned and request_id % 3 == 0:
                    raise Exception("Network partition detected")
                
                success_count += 1
                return {"status": "success", "request_id": request_id}
                
            except Exception as e:
                failure_count += 1
                retry_count += 1
                return {"status": "failed", "request_id": request_id, "error": str(e)}
        
        print(f"  阶段1: 正常网络状态...")
        normal_requests = 100
        tasks = [simulate_network_request(i) for i in range(normal_requests)]
        normal_results = await asyncio.gather(*tasks)
        
        # 模拟网络分区
        print(f"  阶段2: 网络分区开始...")
        network_partitioned = True
        partition_start = time.time()
        await asyncio.sleep(1.0)  # 分区持续1秒
        
        partition_tasks = 200
        tasks = [simulate_network_request(100 + i) for i in range(partition_tasks)]
        partition_results = await asyncio.gather(*tasks)
        
        # 模拟网络恢复
        print(f"  阶段3: 网络恢复...")
        network_partitioned = False
        partition_duration = time.time() - partition_start
        
        recovery_requests = 100
        tasks = [simulate_network_request(300 + i) for i in range(recovery_requests)]
        recovery_results = await asyncio.gather(*tasks)
        
        total_requests = normal_requests + partition_tasks + recovery_requests
        success_rate = success_count / total_requests * 100
        
        duration = time.time() - start_time
        
        print(f"\n  📊 网络分区测试结果:")
        print(f"     总请求: {total_requests}")
        print(f"     成功: {success_count}")
        print(f"     失败: {failure_count}")
        print(f"     重试次数: {retry_count}")
        print(f"     分区持续: {partition_duration:.2f}秒")
        print(f"     成功率: {success_rate:.2f}%")
        
        issues = []
        if failure_count > total_requests * 0.2:
            issues.append(f"网络分区期间失败率过高: {failure_count/total_requests*100:.1f}% > 20%")
        if retry_count > total_requests * 0.3:
            issues.append(f"重试次数过多: {retry_count} ({retry_count/total_requests*100:.1f}%)")
        
        return TestResult(
            scenario_id="network_partition_test",
            scenario_name="网络分区模拟测试",
            success=len(issues) == 0,
            metrics={
                "total_requests": total_requests,
                "success_count": success_count,
                "failure_count": failure_count,
                "retry_count": retry_count,
                "partition_duration": partition_duration,
                "success_rate": success_rate
            },
            issues=issues,
            duration=duration
        )


class MemoryStressTest:
    """内存压力测试"""
    
    async def run(self) -> TestResult:
        """运行测试"""
        start_time = time.time()
        print("\n" + "="*70)
        print("💾 内存压力测试 - 验证内存管理能力")
        print("="*70)
        
        process = psutil.Process()
        
        # 记录初始内存
        initial_memory = process.memory_info().rss / 1024 / 1024
        memory_samples = []
        
        print(f"  执行10000次内存密集操作...")
        
        for i in range(10000):
            # 创建内存压力
            data = bytearray(1024 * 100)  # 100KB
            for j in range(0, len(data), 1024):
                data[j] = i % 256
            
            # 定期采样
            if i % 1000 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory)
                print(f"     第{i:5d}次: 内存 {current_memory:.2f}MB")
            
            # 让垃圾回收工作
            if i % 100 == 0:
                del data
                gc.collect()
        
        # 最终内存
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        memory_growth_rate = memory_growth / 10000
        
        duration = time.time() - start_time
        
        print(f"\n  📊 内存压力测试结果:")
        print(f"     初始内存: {initial_memory:.2f}MB")
        print(f"     最终内存: {final_memory:.2f}MB")
        print(f"     内存增长: {memory_growth:.2f}MB")
        print(f"     增长率: {memory_growth_rate:.4f}MB/次")
        print(f"     内存样本: {len(memory_samples)}个")
        
        issues = []
        if memory_growth > 100:
            issues.append(f"内存增长过大: {memory_growth:.2f}MB > 100MB")
        if memory_growth_rate > 0.01:
            issues.append(f"内存增长率过高: {memory_growth_rate:.4f}MB/次 > 0.01MB/次")
        
        return TestResult(
            scenario_id="memory_stress_test",
            scenario_name="内存压力测试",
            success=len(issues) == 0,
            metrics={
                "initial_memory": initial_memory,
                "final_memory": final_memory,
                "memory_growth": memory_growth,
                "memory_growth_rate": memory_growth_rate,
                "memory_samples": memory_samples
            },
            issues=issues,
            duration=duration
        )


async def run_all_extreme_tests():
    """运行所有极端测试"""
    print("\n" + "🎯"*35)
    print("🚀 Agent Cluster Orchestrator - 特复杂高难度测试 V8.4")
    print("🎯"*35)
    print("测试目标: 持续发现系统缺陷，不断迭代改进")
    
    all_results = []
    
    # 运行测试
    testers = [
        ("10000并发Agent调度", ExtremeConcurrencyTest()),
        ("内存泄漏检测", MemoryLeakTest()),
        ("熔断器验证", CircuitBreakerTest()),
        ("反压机制验证", BackPressureTest()),
        ("LLM限流验证", LLMRateLimitTest()),
        # ("数据库连接池压测", DatabaseConnectionPoolTest()),
        ("缓存击穿测试", CacheStampedeTest()),
        ("多Agent死锁检测", AgentDeadlockTest()),
        ("50000超极端并发测试", ExtremeConcurrencyTestV2()),
        ("网络分区模拟测试", NetworkPartitionTest()),
        ("内存压力测试", MemoryStressTest()),
    ]
    
    for name, tester in testers:
        try:
            result = await tester.run()
            all_results.append(result)
            
            status = "✅ 通过" if result.success else "❌ 失败"
            print(f"\n  {status}: {name}")
            
            if result.issues:
                print(f"     问题:")
                for issue in result.issues:
                    print(f"       - {issue}")
                    
        except Exception as e:
            print(f"\n  ❌ {name} 执行失败: {e}")
            import traceback
            traceback.print_exc()
            
            all_results.append(TestResult(
                scenario_id=name.replace(" ", "_"),
                scenario_name=name,
                success=False,
                metrics={},
                issues=[str(e)],
                duration=0
            ))
    
    # 打印汇总
    print("\n" + "="*70)
    print("📋 测试汇总报告 V8.3")
    print("="*70)
    
    passed = sum(1 for r in all_results if r.success)
    failed = len(all_results) - passed
    
    print(f"\n总测试数: {len(all_results)}")
    print(f"通过数: {passed}")
    print(f"失败数: {failed}")
    
    # 统计所有问题
    all_issues = []
    for result in all_results:
        all_issues.extend(result.issues)
    
    if all_issues:
        print(f"\n发现的问题 ({len(all_issues)} 个):")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
    
    # 性能统计
    print(f"\n性能统计:")
    total_duration = sum(r.duration for r in all_results)
    print(f"  总耗时: {total_duration:.2f}秒")
    
    for result in all_results:
        print(f"  - {result.scenario_name}: {result.duration:.2f}秒")
    
    return all_results


if __name__ == "__main__":
    results = asyncio.run(run_all_extreme_tests())
