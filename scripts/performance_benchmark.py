#!/usr/bin/env python3
"""
Performance Benchmark Tool for Agent Cluster Orchestrator
Tests against real-world LLM frameworks and workloads.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import sys
sys.path.insert(0, '/workspace/backend')

from app.cache.cache_consistency import ConsistentCacheManager, agent_cache, task_cache
from app.tasks.task_retry_manager import RetryManager, RetryPolicy


class BenchmarkType(Enum):
    AGENT_CREATION = "agent_creation"
    TASK_EXECUTION = "task_execution"
    CACHE_PERFORMANCE = "cache_performance"
    RETRY_MECHANISM = "retry_mechanism"
    WEBSOCKET_THROUGHPUT = "websocket_throughput"


@dataclass
class BenchmarkResult:
    """Results of a benchmark run."""
    benchmark_type: BenchmarkType
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    p50_time: float
    p95_time: float
    p99_time: float
    success_rate: float
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    iterations: int = 100
    concurrent_users: int = 10
    warmup_iterations: int = 10
    timeout: int = 60


class PerformanceBenchmarker:
    """Comprehensive performance benchmarking tool."""
    
    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or BenchmarkConfig()
        self.cache_manager = ConsistentCacheManager()
        self.retry_manager = RetryManager()
    
    async def run_agent_creation_benchmark(self) -> BenchmarkResult:
        """Benchmark agent creation performance."""
        print("🔄 Running Agent Creation Benchmark...")
        
        times = []
        errors = []
        
        for i in range(self.config.iterations):
            start = time.time()
            try:
                agent_id = str(uuid.uuid4())
                await agent_cache.set_agent(agent_id, {
                    "id": agent_id,
                    "name": f"benchmark-agent-{i}",
                    "capabilities": ["test", "benchmark"],
                    "model": "gpt-4",
                    "provider": "openai",
                    "status": "idle",
                })
                times.append(time.time() - start)
            except Exception as e:
                errors.append(str(e))
        
        return self._compute_results(BenchmarkType.AGENT_CREATION, times, errors)
    
    async def run_task_execution_benchmark(self) -> BenchmarkResult:
        """Benchmark task execution performance."""
        print("🔄 Running Task Execution Benchmark...")
        
        times = []
        errors = []
        
        for i in range(self.config.iterations):
            start = time.time()
            try:
                task_id = str(uuid.uuid4())
                await task_cache.set_task(task_id, {
                    "id": task_id,
                    "description": f"benchmark-task-{i}",
                    "type": "data_analysis",
                    "priority": 1,
                    "status": "completed",
                    "result": {"success": True},
                })
                times.append(time.time() - start)
            except Exception as e:
                errors.append(str(e))
        
        return self._compute_results(BenchmarkType.TASK_EXECUTION, times, errors)
    
    async def run_cache_performance_benchmark(self) -> BenchmarkResult:
        """Benchmark cache read/write performance."""
        print("🔄 Running Cache Performance Benchmark...")
        
        read_times = []
        write_times = []
        errors = []
        
        # First, populate cache
        for i in range(self.config.iterations):
            start = time.time()
            try:
                await self.cache_manager.local_cache.set(
                    f"benchmark-key-{i}",
                    f"benchmark-value-{i}",
                    ttl=3600
                )
                write_times.append(time.time() - start)
            except Exception as e:
                errors.append(str(e))
        
        # Then read from cache
        for i in range(self.config.iterations):
            start = time.time()
            try:
                value = await self.cache_manager.local_cache.get(f"benchmark-key-{i}")
                if value is None:
                    errors.append(f"Cache miss for key-{i}")
                read_times.append(time.time() - start)
            except Exception as e:
                errors.append(str(e))
        
        times = write_times + read_times
        result = self._compute_results(BenchmarkType.CACHE_PERFORMANCE, times, errors)
        result.metrics["write_avg_ms"] = (sum(write_times) / len(write_times) * 1000) if write_times else 0
        result.metrics["read_avg_ms"] = (sum(read_times) / len(read_times) * 1000) if read_times else 0
        result.metrics["cache_hits"] = len(read_times) - errors.count("Cache miss")
        result.metrics["cache_misses"] = errors.count("Cache miss")
        
        return result
    
    async def run_retry_mechanism_benchmark(self) -> BenchmarkResult:
        """Benchmark retry mechanism performance."""
        print("🔄 Running Retry Mechanism Benchmark...")
        
        times = []
        errors = []
        success_count = 0
        
        for i in range(self.config.iterations):
            start = time.time()
            try:
                call_count = 0
                
                async def flaky_func():
                    nonlocal call_count
                    call_count += 1
                    if call_count <= 2:
                        raise Exception("Temporary failure")
                    return "success"
                
                await self.retry_manager.execute_with_retry(f"benchmark-{i}", flaky_func)
                success_count += 1
                times.append(time.time() - start)
            except Exception as e:
                errors.append(str(e))
        
        result = self._compute_results(BenchmarkType.RETRY_MECHANISM, times, errors)
        result.success_rate = success_count / self.config.iterations
        return result
    
    async def run_concurrent_benchmark(self) -> BenchmarkResult:
        """Benchmark concurrent operations."""
        print("🔄 Running Concurrent Operations Benchmark...")
        
        times = []
        errors = []
        
        async def perform_operation(operation_id: int):
            start = time.time()
            try:
                agent_id = str(uuid.uuid4())
                await agent_cache.set_agent(agent_id, {
                    "id": agent_id,
                    "name": f"concurrent-agent-{operation_id}",
                    "capabilities": ["test"],
                    "model": "gpt-4",
                })
                return time.time() - start, None
            except Exception as e:
                return time.time() - start, str(e)
        
        # Run concurrent operations
        tasks = [perform_operation(i) for i in range(self.config.concurrent_users)]
        results = await asyncio.gather(*tasks)
        
        for duration, error in results:
            times.append(duration)
            if error:
                errors.append(error)
        
        result = self._compute_results(BenchmarkType.TASK_EXECUTION, times, errors)
        result.metrics["concurrent_users"] = self.config.concurrent_users
        
        return result
    
    def _compute_results(self, benchmark_type: BenchmarkType, times: List[float], errors: List[str]) -> BenchmarkResult:
        """Compute statistical results from timing data."""
        if not times:
            return BenchmarkResult(
                benchmark_type=benchmark_type,
                iterations=self.config.iterations,
                total_time=0,
                avg_time=0,
                min_time=0,
                max_time=0,
                p50_time=0,
                p95_time=0,
                p99_time=0,
                success_rate=0,
                errors=errors,
            )
        
        sorted_times = sorted(times)
        total_time = sum(times)
        avg_time = total_time / len(times)
        min_time = min(times)
        max_time = max(times)
        p50_time = sorted_times[int(len(sorted_times) * 0.50)]
        p95_time = sorted_times[int(len(sorted_times) * 0.95)]
        p99_time = sorted_times[int(len(sorted_times) * 0.99)]
        success_rate = len(times) / self.config.iterations
        
        return BenchmarkResult(
            benchmark_type=benchmark_type,
            iterations=self.config.iterations,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            p50_time=p50_time,
            p95_time=p95_time,
            p99_time=p99_time,
            success_rate=success_rate,
            errors=errors,
        )
    
    def _print_result(self, result: BenchmarkResult):
        """Pretty print benchmark result."""
        print(f"\n📊 {result.benchmark_type.value.replace('_', ' ').title()} Results:")
        print("-" * 60)
        print(f"  Iterations:     {result.iterations}")
        print(f"  Total Time:     {result.total_time:.2f}s")
        print(f"  Avg Time:       {result.avg_time * 1000:.2f}ms")
        print(f"  Min Time:       {result.min_time * 1000:.2f}ms")
        print(f"  Max Time:       {result.max_time * 1000:.2f}ms")
        print(f"  P50:            {result.p50_time * 1000:.2f}ms")
        print(f"  P95:            {result.p95_time * 1000:.2f}ms")
        print(f"  P99:            {result.p99_time * 1000:.2f}ms")
        print(f"  Success Rate:   {result.success_rate * 100:.1f}%")
        print(f"  Errors:         {len(result.errors)}")
        
        if result.metrics:
            print("\n  Additional Metrics:")
            for key, value in result.metrics.items():
                print(f"    {key}: {value}")
    
    async def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run all benchmarks and return results."""
        print("🚀 Starting Comprehensive Performance Benchmark Suite")
        print("=" * 60)
        
        results = []
        
        # Run benchmarks
        results.append(await self.run_cache_performance_benchmark())
        self._print_result(results[-1])
        
        results.append(await self.run_agent_creation_benchmark())
        self._print_result(results[-1])
        
        results.append(await self.run_task_execution_benchmark())
        self._print_result(results[-1])
        
        results.append(await self.run_retry_mechanism_benchmark())
        self._print_result(results[-1])
        
        results.append(await self.run_concurrent_benchmark())
        self._print_result(results[-1])
        
        print("\n" + "=" * 60)
        print("✅ Benchmark Suite Complete")
        
        return results


async def main():
    """Run all benchmarks."""
    benchmarker = PerformanceBenchmarker(BenchmarkConfig(
        iterations=100,
        concurrent_users=20,
        warmup_iterations=5,
    ))
    
    results = await benchmarker.run_all_benchmarks()
    
    # Generate report
    report = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "iterations": benchmarker.config.iterations,
            "concurrent_users": benchmarker.config.concurrent_users,
        },
        "benchmarks": [
            {
                "type": result.benchmark_type.value,
                "iterations": result.iterations,
                "avg_time_ms": result.avg_time * 1000,
                "p95_time_ms": result.p95_time * 1000,
                "success_rate": result.success_rate,
                "errors": len(result.errors),
                "metrics": result.metrics,
            }
            for result in results
        ],
    }
    
    # Save report
    with open("/workspace/benchmark_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("\n📝 Report saved to /workspace/benchmark_report.json")


if __name__ == "__main__":
    asyncio.run(main())
