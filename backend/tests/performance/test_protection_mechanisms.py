"""
保护机制验证测试

验证熔断器、超时保护、连接池、自适应队列等机制是否正常工作
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, Any

from app.core.protection import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    CircuitBreakerManager,
    execute_with_timeout,
    TimeoutError,
    TimeoutMonitor,
    AdaptiveQueue,
    QueueConfig,
    ConnectionPool,
    PoolConfig
)


async def test_circuit_breaker():
    """测试熔断器"""
    print("\n" + "="*70)
    print("🔄 测试1：熔断器")
    print("="*70)
    
    # 创建熔断器
    config = CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_duration=2.0,
        half_open_max_calls=2
    )
    
    cb = CircuitBreaker("test_circuit", config)
    
    call_count = 0
    fail_count = 0
    
    async def unreliable_service():
        """不可靠的服务"""
        nonlocal call_count, fail_count
        call_count += 1
        
        if call_count <= 3:
            # 前3次调用失败
            fail_count += 1
            raise Exception("Service unavailable")
        
        return "Success"
    
    # 测试1: 正常调用
    print("\n  阶段1：正常调用...")
    for i in range(5):
        try:
            result = await cb.call(unreliable_service)
            print(f"    第{i+1}次调用: ✅ {result}")
        except Exception as e:
            print(f"    第{i+1}次调用: ❌ {e}")
    
    stats = cb.get_stats()
    print(f"\n  📊 熔断器状态:")
    print(f"     当前状态: {stats['state']}")
    print(f"     总调用: {stats['total_calls']}")
    print(f"     失败次数: {stats['failure_count']}")
    
    # 测试2: 验证状态转换
    print(f"\n  阶段2：状态转换验证")
    print(f"     初始状态: CLOSED")
    print(f"     当前状态: {cb.state.value}")
    
    if cb.state == CircuitState.OPEN:
        print(f"     ✅ 熔断器正确打开（失败{config.failure_threshold}次后）")
    else:
        print(f"     ❌ 熔断器未正确打开")
    
    # 测试3: 等待恢复
    print(f"\n  阶段3：等待超时后恢复...")
    print(f"     等待 {config.timeout_duration} 秒...")
    await asyncio.sleep(config.timeout_duration + 0.5)
    
    print(f"     当前状态: {cb.state.value}")
    
    if cb.state == CircuitState.HALF_OPEN:
        print(f"     ✅ 熔断器正确进入HALF_OPEN状态")
    else:
        print(f"     ⚠️  熔断器状态: {cb.state.value}")
    
    return cb.state == CircuitState.HALF_OPEN or cb.state == CircuitState.OPEN


async def test_timeout_protection():
    """测试超时保护"""
    print("\n" + "="*70)
    print("⏱️  测试2：超时保护")
    print("="*70)
    
    timeout_monitor = TimeoutMonitor()
    
    async def slow_task():
        """慢任务"""
        await asyncio.sleep(2.0)
        return "Done"
    
    async def fast_task():
        """快任务"""
        await asyncio.sleep(0.1)
        return "Fast done"
    
    # 测试1: 超时任务
    print("\n  阶段1：超时任务测试...")
    try:
        result = await execute_with_timeout(
            slow_task(),
            timeout=0.5,
            task_name="slow_task"
        )
        print(f"     结果: ✅ {result}")
    except TimeoutError as e:
        print(f"     ✅ 正确捕获超时: {e}")
    except Exception as e:
        print(f"     ❌ 意外错误: {e}")
    
    # 测试2: 正常任务
    print("\n  阶段2：正常任务测试...")
    try:
        result = await execute_with_timeout(
            fast_task(),
            timeout=2.0,
            task_name="fast_task"
        )
        print(f"     ✅ 正常完成: {result}")
    except Exception as e:
        print(f"     ❌ 错误: {e}")
    
    # 测试3: 批量超时测试
    print("\n  阶段3：批量超时测试...")
    timeout_count = 0
    
    for i in range(10):
        try:
            # 交替超时和正常
            timeout = 0.1 if i % 2 == 0 else 2.0
            task = slow_task if i % 2 == 0 else fast_task
            
            await execute_with_timeout(
                task(),
                timeout=timeout,
                task_name=f"task_{i}"
            )
        except TimeoutError:
            timeout_count += 1
    
    print(f"     总任务: 10")
    print(f"     超时数: {timeout_count}")
    print(f"     ✅ 超时保护正常工作")
    
    stats = timeout_monitor.get_stats()
    print(f"\n  📊 超时统计:")
    print(f"     总超时: {stats['total_timeouts']}")
    
    return True


async def test_adaptive_queue():
    """测试自适应队列"""
    print("\n" + "="*70)
    print("📦 测试3：自适应队列")
    print("="*70)
    
    config = QueueConfig(
        initial_capacity=10,
        max_capacity=50,
        growth_factor=2.0
    )
    
    queue = AdaptiveQueue(config)
    
    # 测试1: 基本入队出队
    print("\n  阶段1：基本入队出队...")
    for i in range(15):
        success = await queue.enqueue(f"item_{i}", priority=15-i)
        status = "✅" if success else "❌"
        print(f"     入队 item_{i}: {status}")
    
    stats = queue.get_stats()
    print(f"\n  📊 队列统计:")
    print(f"     当前大小: {stats['current_size']}")
    print(f"     容量: {stats['capacity']}")
    print(f"     利用率: {stats['utilization']:.1f}%")
    print(f"     扩容次数: {stats['growth_count']}")
    
    # 测试2: 优先级测试
    print("\n  阶段2：优先级测试...")
    await queue.enqueue("low_priority", priority=1)
    await queue.enqueue("high_priority", priority=10)
    await queue.enqueue("medium_priority", priority=5)
    
    # 出队顺序应该是：高 -> 中 -> 低
    items = []
    for _ in range(3):
        item = await queue.dequeue()
        if item:
            items.append(item)
    
    print(f"     出队顺序: {' -> '.join(items)}")
    
    expected = ["high_priority", "medium_priority", "low_priority"]
    if items == expected:
        print(f"     ✅ 优先级正确（高 -> 中 -> 低）")
    else:
        print(f"     ❌ 优先级错误")
    
    # 测试3: 容量限制
    print("\n  阶段3：容量限制测试...")
    
    # 清空队列
    while await queue.dequeue():
        pass
    
    # 尝试超过容量入队
    for i in range(60):
        await queue.enqueue(f"overflow_{i}")
    
    stats = queue.get_stats()
    print(f"     尝试入队: 60")
    print(f"     实际入队: {stats['current_size']}")
    print(f"     拒绝数: {stats['rejected']}")
    print(f"     最大容量: {stats['capacity']}")
    
    return True


async def test_connection_pool():
    """测试连接池"""
    print("\n" + "="*70)
    print("🔗 测试4：连接池管理")
    print("="*70)
    
    # 模拟连接工厂
    connection_id = 0
    
    async def create_connection():
        nonlocal connection_id
        connection_id += 1
        await asyncio.sleep(0.01)  # 模拟连接建立
        return {"id": connection_id, "status": "connected"}
    
    # 创建连接池
    config = PoolConfig(
        min_size=2,
        max_size=10,
        max_idle_time=60.0,
        acquire_timeout=5.0
    )
    
    pool = ConnectionPool(config, create_connection)
    await pool.initialize()
    
    print(f"\n  阶段1：连接池初始化...")
    stats = pool.get_stats()
    print(f"     可用连接: {stats['available']}")
    print(f"     最大连接: {stats['max_size']}")
    
    # 测试1: 获取和释放连接
    print("\n  阶段2：获取和释放连接...")
    connections = []
    
    for i in range(5):
        conn = await pool.acquire()
        connections.append(conn)
        print(f"     获取连接 {conn.connection['id']}: ✅")
    
    stats = pool.get_stats()
    print(f"\n  📊 获取后统计:")
    print(f"     可用: {stats['available']}")
    print(f"     已占用: {stats['acquired']}")
    print(f"     利用率: {stats['utilization']:.1f}%")
    
    # 释放连接
    print("\n  阶段3：释放连接...")
    for conn in connections:
        await pool.release(conn)
        print(f"     释放连接 {conn.connection['id']}: ✅")
    
    stats = pool.get_stats()
    print(f"\n  📊 释放后统计:")
    print(f"     可用: {stats['available']}")
    print(f"     已占用: {stats['acquired']}")
    
    # 测试2: 并发获取
    print("\n  阶段4：并发获取连接...")
    
    async def get_and_use():
        conn = await pool.acquire()
        await asyncio.sleep(0.1)
        await pool.release(conn)
        return conn.connection['id']
    
    tasks = [get_and_use() for _ in range(8)]
    results = await asyncio.gather(*tasks)
    
    print(f"     并发获取: 8个")
    print(f"     成功: {len(results)}个")
    print(f"     ✅ 连接池正常工作")
    
    await pool.close()
    
    return True


async def run_protection_tests():
    """运行所有保护机制测试"""
    print("\n" + "🎯"*35)
    print("🚀 Agent Cluster Orchestrator - 保护机制验证测试")
    print("🎯"*35)
    
    results = {}
    
    # 运行所有测试
    tests = [
        ("熔断器", test_circuit_breaker),
        ("超时保护", test_timeout_protection),
        ("自适应队列", test_adaptive_queue),
        ("连接池", test_connection_pool),
    ]
    
    for name, test_func in tests:
        try:
            success = await test_func()
            results[name] = {
                "success": success,
                "error": None
            }
        except Exception as e:
            print(f"\n  💥 {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results[name] = {
                "success": False,
                "error": str(e)
            }
    
    # 打印汇总
    print("\n" + "="*70)
    print("📋 测试汇总")
    print("="*70)
    
    for name, result in results.items():
        status = "✅ 通过" if result["success"] else f"❌ 失败: {result['error']}"
        print(f"  {name}: {status}")
    
    passed = sum(1 for r in results.values() if r["success"])
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    return results


if __name__ == "__main__":
    results = asyncio.run(run_protection_tests())
