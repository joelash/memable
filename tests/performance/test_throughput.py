"""
Throughput performance tests for memento-ai.

Measures operations per second for core operations at various database sizes.

Run with: pytest tests/performance/test_throughput.py -v -s
"""

import os
import statistics
import time
from uuid import uuid4

import pytest

from memento_ai import Durability, MemoryCreate, build_sqlite_store

# Skip if no API key (these tests need real embeddings)
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY required for performance tests"
)


class TestThroughput:
    """Throughput benchmarks for core operations."""

    @pytest.fixture
    def store(self):
        """In-memory SQLite store for benchmarking."""
        with build_sqlite_store(":memory:") as s:
            s.setup()
            yield s

    @pytest.fixture
    def namespace(self):
        """Unique namespace for each test."""
        return (f"perf_test_{uuid4().hex[:8]}", "memories")

    def _measure_operation(self, operation, iterations=10):
        """Run operation multiple times and return stats."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            operation()
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        return {
            "mean_ms": statistics.mean(times) * 1000,
            "median_ms": statistics.median(times) * 1000,
            "stdev_ms": statistics.stdev(times) * 1000 if len(times) > 1 else 0,
            "min_ms": min(times) * 1000,
            "max_ms": max(times) * 1000,
            "ops_per_sec": len(times) / sum(times),
        }

    def test_add_throughput(self, store, namespace):
        """Measure add() operation throughput."""
        results = []

        def add_memory():
            store.add(namespace, MemoryCreate(
                text=f"Test memory {uuid4().hex}",
                durability=Durability.CORE,
                confidence=0.9,
            ))

        stats = self._measure_operation(add_memory, iterations=20)
        results.append(stats)

        print(f"\n📊 ADD Throughput:")
        print(f"   Mean: {stats['mean_ms']:.2f}ms")
        print(f"   Median: {stats['median_ms']:.2f}ms")
        print(f"   Ops/sec: {stats['ops_per_sec']:.2f}")

        # Baseline assertion: should be under 2 seconds per add
        assert stats["mean_ms"] < 2000, f"Add too slow: {stats['mean_ms']}ms"

    def test_search_throughput_small_db(self, store, namespace):
        """Measure search() throughput with small database (100 memories)."""
        # Seed database
        for i in range(100):
            store.add(namespace, MemoryCreate(
                text=f"Memory about topic {i % 10}: detail {i}",
                durability=Durability.CORE,
            ))

        def search_memories():
            store.search(namespace, "topic 5")

        stats = self._measure_operation(search_memories, iterations=10)

        print(f"\n📊 SEARCH Throughput (100 memories):")
        print(f"   Mean: {stats['mean_ms']:.2f}ms")
        print(f"   Median: {stats['median_ms']:.2f}ms")
        print(f"   Ops/sec: {stats['ops_per_sec']:.2f}")

        # Baseline: search should be under 1 second
        assert stats["mean_ms"] < 1000, f"Search too slow: {stats['mean_ms']}ms"

    def test_get_throughput(self, store, namespace):
        """Measure get() operation throughput."""
        # Create a memory to retrieve
        memory = store.add(namespace, MemoryCreate(
            text="Test memory for get benchmark",
            durability=Durability.CORE,
        ))
        memory_id = memory.id

        def get_memory():
            store.get(namespace, memory_id)

        stats = self._measure_operation(get_memory, iterations=50)

        print(f"\n📊 GET Throughput:")
        print(f"   Mean: {stats['mean_ms']:.2f}ms")
        print(f"   Median: {stats['median_ms']:.2f}ms")
        print(f"   Ops/sec: {stats['ops_per_sec']:.2f}")

        # Get should be very fast (no embedding needed)
        assert stats["mean_ms"] < 50, f"Get too slow: {stats['mean_ms']}ms"

    def test_list_throughput(self, store, namespace):
        """Measure list_all() operation throughput."""
        # Seed database
        for i in range(50):
            store.add(namespace, MemoryCreate(
                text=f"Memory {i}",
                durability=Durability.SITUATIONAL,
            ))

        def list_memories():
            store.list_all(namespace)

        stats = self._measure_operation(list_memories, iterations=20)

        print(f"\n📊 LIST Throughput (50 memories):")
        print(f"   Mean: {stats['mean_ms']:.2f}ms")
        print(f"   Median: {stats['median_ms']:.2f}ms")
        print(f"   Ops/sec: {stats['ops_per_sec']:.2f}")

        # List should be reasonably fast
        assert stats["mean_ms"] < 500, f"List too slow: {stats['mean_ms']}ms"


class TestScalingBehavior:
    """Test how performance scales with database size."""

    @pytest.fixture
    def store(self):
        """In-memory SQLite store."""
        with build_sqlite_store(":memory:") as s:
            s.setup()
            yield s

    @pytest.fixture
    def namespace(self):
        return (f"scale_test_{uuid4().hex[:8]}", "memories")

    @pytest.mark.slow
    def test_search_scaling(self, store, namespace):
        """Measure how search time scales with DB size."""
        sizes = [10, 50, 100, 200]
        results = {}

        for size in sizes:
            # Add memories up to this size
            current_count = store.count(namespace)
            for i in range(current_count, size):
                store.add(namespace, MemoryCreate(
                    text=f"Scaling test memory {i} about various topics",
                    durability=Durability.CORE,
                ))

            # Measure search time
            times = []
            for _ in range(5):
                start = time.perf_counter()
                store.search(namespace, "various topics")
                times.append(time.perf_counter() - start)

            results[size] = statistics.mean(times) * 1000

        print(f"\n📊 Search Scaling:")
        for size, ms in results.items():
            print(f"   {size:4d} memories: {ms:.2f}ms")

        # Check that scaling is sub-linear (not O(n))
        # 20x more data shouldn't be 20x slower
        ratio = results[200] / results[10] if results[10] > 0 else float('inf')
        print(f"   Scaling ratio (200/10): {ratio:.2f}x")

        # With vector index, should be much better than 20x
        assert ratio < 10, f"Search scaling too linear: {ratio}x slowdown for 20x data"
