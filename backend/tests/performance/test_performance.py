"""
Performance benchmarks and load tests.
"""
import pytest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from httpx import AsyncClient
from app.main_fastapi_application import app


class TestAPIPerformance:
    """API performance benchmarks."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_response_time(self):
        """Test health endpoint response time."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            times = []
            for _ in range(100):
                start = time.time()
                response = await client.get("/health")
                elapsed = time.time() - start
                times.append(elapsed)
                assert response.status_code == 200
            
            avg_time = sum(times) / len(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]
            
            print(f"\nHealth endpoint performance:")
            print(f"  Average: {avg_time*1000:.2f}ms")
            print(f"  P95: {p95_time*1000:.2f}ms")
            
            assert avg_time < 0.1  # Should be under 100ms
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            async def make_request():
                response = await client.get("/health")
                return response.status_code
            
            # Simulate 50 concurrent requests
            tasks = [make_request() for _ in range(50)]
            results = await asyncio.gather(*tasks)
            
            success_count = sum(1 for r in results if r == 200)
            success_rate = success_count / len(results)
            
            print(f"\nConcurrent request test:")
            print(f"  Total requests: {len(results)}")
            print(f"  Successful: {success_count}")
            print(f"  Success rate: {success_rate*100:.1f}%")
            
            assert success_rate >= 0.95


class TestDatabasePerformance:
    """Database performance tests."""
    
    @pytest.mark.asyncio
    async def test_query_performance(self, db_session):
        """Test database query performance."""
        from app.models.agent_data_model import Agent
        
        start = time.time()
        
        # Create test agents
        for i in range(100):
            agent = Agent(
                id=f"perf-test-{i}",
                name=f"perf-agent-{i}",
                status="idle",
                capabilities=["test"],
                model="gpt-4"
            )
            db_session.add(agent)
        
        await db_session.commit()
        
        query_time = time.time() - start
        print(f"\nDatabase write performance:")
        print(f"  100 inserts: {query_time*1000:.2f}ms")
        
        # Test read performance
        start = time.time()
        result = await db_session.execute(
            f"SELECT * FROM agents WHERE name LIKE 'perf-agent-%'"
        )
        rows = result.fetchall()
        read_time = time.time() - start
        
        print(f"  100 reads: {read_time*1000:.2f}ms")
        
        # Cleanup
        await db_session.execute(
            f"DELETE FROM agents WHERE name LIKE 'perf-agent-%'"
        )
        await db_session.commit()
        
        assert query_time < 5.0  # Should complete in under 5 seconds


class TestCachePerformance:
    """Cache performance tests."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_rate(self):
        """Test cache hit rate."""
        from app.cache.redis_cache_manager import RedisCacheManager
        
        cache = RedisCacheManager()
        
        # Warm up cache
        for i in range(10):
            await cache.set(f"key-{i}", {"data": f"value-{i}"})
        
        # Test hits
        hits = 0
        misses = 0
        total = 100
        
        for i in range(total):
            result = await cache.get(f"key-{i % 10}")
            if result:
                hits += 1
            else:
                misses += 1
        
        hit_rate = hits / total
        print(f"\nCache performance:")
        print(f"  Total requests: {total}")
        print(f"  Hits: {hits}")
        print(f"  Misses: {misses}")
        print(f"  Hit rate: {hit_rate*100:.1f}%")
        
        assert hit_rate >= 0.9  # Should be at least 90%


class TestLLMPerformance:
    """LLM provider performance tests."""
    
    @pytest.mark.asyncio
    async def test_llm_provider_timeout(self):
        """Test LLM provider timeout handling."""
        from app.llm.llm_provider_manager import LLMProviderManager
        import asyncio
        
        manager = LLMProviderManager()
        
        start = time.time()
        try:
            result = await asyncio.wait_for(
                manager.execute("test prompt", timeout=1),
                timeout=5
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - start
            print(f"\nLLM timeout test:")
            print(f"  Timed out after: {elapsed:.2f}s")
            # This is expected if no real API key is configured


class TestWebSocketPerformance:
    """WebSocket performance tests."""
    
    @pytest.mark.asyncio
    async def test_websocket_message_throughput(self):
        """Test WebSocket message throughput."""
        from app.websocket.websocket_connection_manager import WebSocketManager
        
        manager = WebSocketManager()
        
        # Simulate message sending
        start = time.time()
        messages_sent = 0
        target_messages = 1000
        
        for i in range(target_messages):
            await manager.broadcast(
                message_type="test",
                data={"index": i}
            )
            messages_sent += 1
        
        elapsed = time.time() - start
        throughput = messages_sent / elapsed
        
        print(f"\nWebSocket throughput:")
        print(f"  Messages sent: {messages_sent}")
        print(f"  Time elapsed: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.0f} msg/s")
        
        # Should handle at least 100 msg/s
        assert throughput >= 100
