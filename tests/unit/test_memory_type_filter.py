"""
Unit tests for memory_type filtering in store search.
"""

import pytest

from memable import (
    MemoryCreate,
    MemoryQuery,
    MemoryType,
    Durability,
    build_sqlite_store,
)


@pytest.fixture
def store_with_typed_memories():
    """Create a store with memories of different types."""
    with build_sqlite_store(":memory:") as store:
        store.setup()
        namespace = ("test_user", "memories")
        
        # Add memories with different types
        memories = [
            MemoryCreate(
                text="Always use TypeScript strict mode",
                durability=Durability.CORE,
                memory_type=MemoryType.RULE,
            ),
            MemoryCreate(
                text="Chose React for the frontend",
                durability=Durability.SITUATIONAL,
                memory_type=MemoryType.DECISION,
            ),
            MemoryCreate(
                text="API rate limit is 100 requests per minute",
                durability=Durability.CORE,
                memory_type=MemoryType.FACT,
            ),
            MemoryCreate(
                text="User prefers dark mode",
                durability=Durability.CORE,
                memory_type=MemoryType.PREFERENCE,
            ),
            MemoryCreate(
                text="Currently working on authentication refactor",
                durability=Durability.SITUATIONAL,
                memory_type=MemoryType.CONTEXT,
            ),
            MemoryCreate(
                text="User tends to ask clarifying questions",
                durability=Durability.EPISODIC,
                memory_type=MemoryType.OBSERVATION,
            ),
            MemoryCreate(
                text="Memory without type for backward compat",
                durability=Durability.EPISODIC,
                memory_type=None,
            ),
        ]
        
        for mem in memories:
            store.add(namespace, mem)
        
        yield store, namespace


class TestMemoryTypeFilter:
    """Tests for filtering by memory_type in store.search()."""

    def test_filter_by_single_type(self, store_with_typed_memories):
        """Test filtering by a single memory type."""
        store, namespace = store_with_typed_memories
        
        # Search for rules only
        query = MemoryQuery(
            query="coding standards",
            memory_type=[MemoryType.RULE],
            limit=10,
        )
        results = store.search(namespace, query)
        
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.RULE
        assert "TypeScript" in results[0].text

    def test_filter_by_multiple_types(self, store_with_typed_memories):
        """Test filtering by multiple memory types."""
        store, namespace = store_with_typed_memories
        
        # Search for rules and decisions
        query = MemoryQuery(
            query="project",
            memory_type=[MemoryType.RULE, MemoryType.DECISION],
            limit=10,
        )
        results = store.search(namespace, query)
        
        assert len(results) == 2
        types = {m.memory_type for m in results}
        assert types == {MemoryType.RULE, MemoryType.DECISION}

    def test_no_type_filter_returns_all(self, store_with_typed_memories):
        """Test that no memory_type filter returns all memories."""
        store, namespace = store_with_typed_memories
        
        query = MemoryQuery(
            query="",
            memory_type=None,
            limit=10,
        )
        results = store.search(namespace, query)
        
        # Should return all 7 memories
        assert len(results) == 7

    def test_filter_excludes_none_type(self, store_with_typed_memories):
        """Test that filtering by type excludes memories with None type."""
        store, namespace = store_with_typed_memories
        
        query = MemoryQuery(
            query="memory",
            memory_type=[MemoryType.FACT],
            limit=10,
        )
        results = store.search(namespace, query)
        
        # Should only get the API rate limit fact
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.FACT
        
        # The "Memory without type" should be excluded
        for mem in results:
            assert mem.memory_type is not None

    def test_filter_by_preference_type(self, store_with_typed_memories):
        """Test filtering by preference type."""
        store, namespace = store_with_typed_memories
        
        query = MemoryQuery(
            query="user",
            memory_type=[MemoryType.PREFERENCE],
            limit=10,
        )
        results = store.search(namespace, query)
        
        assert len(results) == 1
        assert "dark mode" in results[0].text

    def test_filter_by_context_type(self, store_with_typed_memories):
        """Test filtering by context type."""
        store, namespace = store_with_typed_memories
        
        query = MemoryQuery(
            query="working",
            memory_type=[MemoryType.CONTEXT],
            limit=10,
        )
        results = store.search(namespace, query)
        
        assert len(results) == 1
        assert "authentication" in results[0].text

    def test_combine_type_and_durability_filters(self, store_with_typed_memories):
        """Test combining memory_type and durability filters."""
        store, namespace = store_with_typed_memories
        
        # Search for core facts and rules
        query = MemoryQuery(
            query="",
            memory_type=[MemoryType.FACT, MemoryType.RULE],
            durability=[Durability.CORE],
            limit=10,
        )
        results = store.search(namespace, query)
        
        # Should get: TypeScript rule (core) and API rate limit fact (core)
        assert len(results) == 2
        for mem in results:
            assert mem.durability == Durability.CORE
            assert mem.memory_type in [MemoryType.FACT, MemoryType.RULE]
