"""Unit tests for DuckDB backend."""

import os
from pathlib import Path

import pytest

from engram_ai import Durability, MemoryCreate, build_duckdb_store, build_store

# Skip all tests if duckdb not installed
duckdb = pytest.importorskip("duckdb")


class TestDuckDBBackend:
    """Tests for DuckDB backend functionality."""

    def test_build_duckdb_store_memory(self):
        """Test creating in-memory DuckDB store."""
        with build_duckdb_store(":memory:") as store:
            store.setup()
            assert store is not None

    def test_build_duckdb_store_file(self, tmp_path: Path):
        """Test creating file-based DuckDB store."""
        db_path = tmp_path / "test.duckdb"
        with build_duckdb_store(str(db_path)) as store:
            store.setup()
            assert store is not None
            assert db_path.exists()

    def test_build_store_duckdb_url(self, tmp_path: Path):
        """Test build_store with duckdb:// URL."""
        db_path = tmp_path / "test.duckdb"
        with build_store(f"duckdb:///{db_path}") as store:
            store.setup()
            assert store is not None

    def test_build_store_duckdb_extension(self, tmp_path: Path):
        """Test build_store auto-detects .duckdb extension."""
        db_path = tmp_path / "test.duckdb"
        with build_store(str(db_path)) as store:
            store.setup()
            assert store is not None


class TestDuckDBOperations:
    """Tests for DuckDB CRUD operations (requires OPENAI_API_KEY)."""

    @pytest.fixture
    def store(self):
        """Create an in-memory store for testing."""
        with build_duckdb_store(":memory:") as s:
            s.setup()
            yield s

    @pytest.fixture
    def namespace(self):
        """Test namespace."""
        return ("test_user", "memories")

    def test_add_and_get(self, store, namespace):
        """Test adding and retrieving a memory."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        memory = MemoryCreate(
            text="Test memory content for DuckDB",
            durability=Durability.CORE,
            confidence=0.9,
        )

        stored = store.add(namespace, memory)
        assert stored.text == "Test memory content for DuckDB"

        retrieved = store.get(namespace, stored.id)
        assert retrieved is not None
        assert retrieved.text == "Test memory content for DuckDB"
        assert retrieved.durability == Durability.CORE

    def test_delete(self, store, namespace):
        """Test deleting a memory."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        memory = MemoryCreate(text="To be deleted from DuckDB", durability=Durability.EPISODIC)
        stored = store.add(namespace, memory)

        result = store.delete(namespace, stored.id)
        assert result is True

        retrieved = store.get(namespace, stored.id)
        assert retrieved is None

    def test_list_all(self, store, namespace):
        """Test listing all memories."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        # Add some memories
        for i in range(3):
            store.add(namespace, MemoryCreate(
                text=f"DuckDB Memory {i}",
                durability=Durability.SITUATIONAL,
            ))

        memories = store.list_all(namespace)
        assert len(memories) == 3

    def test_search(self, store, namespace):
        """Test semantic search."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        # Add memories with different topics
        store.add(namespace, MemoryCreate(
            text="The user loves Python programming",
            durability=Durability.CORE,
        ))
        store.add(namespace, MemoryCreate(
            text="The user enjoys hiking in mountains",
            durability=Durability.CORE,
        ))
        store.add(namespace, MemoryCreate(
            text="The user prefers dark mode in IDEs",
            durability=Durability.SITUATIONAL,
        ))

        # Search for programming-related
        results = store.search(namespace, "coding software development")
        assert len(results) > 0
        # The Python memory should be most relevant
        assert "Python" in results[0].text or "dark mode" in results[0].text
