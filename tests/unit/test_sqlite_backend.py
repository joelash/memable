"""Unit tests for SQLite backend."""

from pathlib import Path

import pytest

from memento_ai import Durability, MemoryCreate, build_sqlite_store, build_store


class TestSQLiteBackend:
    """Tests for SQLite backend functionality."""

    def test_build_sqlite_store_memory(self):
        """Test creating in-memory SQLite store."""
        with build_sqlite_store(":memory:") as store:
            store.setup()
            assert store is not None

    def test_build_sqlite_store_file(self, tmp_path: Path):
        """Test creating file-based SQLite store."""
        db_path = tmp_path / "test.db"
        with build_sqlite_store(str(db_path)) as store:
            store.setup()
            assert store is not None
            assert db_path.exists()

    def test_build_store_sqlite_url(self, tmp_path: Path):
        """Test build_store with sqlite:// URL."""
        db_path = tmp_path / "test.db"
        with build_store(f"sqlite:///{db_path}") as store:
            store.setup()
            assert store is not None

    def test_build_store_memory_url(self):
        """Test build_store with :memory: URL."""
        with build_store(":memory:") as store:
            store.setup()
            assert store is not None


class TestSQLiteOperations:
    """Tests for SQLite CRUD operations (requires OPENAI_API_KEY)."""

    @pytest.fixture
    def store(self):
        """Create an in-memory store for testing."""
        with build_sqlite_store(":memory:") as s:
            s.setup()
            yield s

    @pytest.fixture
    def namespace(self):
        """Test namespace."""
        return ("test_user", "memories")

    @pytest.mark.skipif(
        not pytest.importorskip("openai", reason="OpenAI not installed"),
        reason="Requires OPENAI_API_KEY"
    )
    def test_add_and_get(self, store, namespace):
        """Test adding and retrieving a memory."""
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        memory = MemoryCreate(
            text="Test memory content",
            durability=Durability.CORE,
            confidence=0.9,
        )

        stored = store.add(namespace, memory)
        assert stored.text == "Test memory content"

        retrieved = store.get(namespace, stored.id)
        assert retrieved is not None
        assert retrieved.text == "Test memory content"
        assert retrieved.durability == Durability.CORE

    @pytest.mark.skipif(
        not pytest.importorskip("openai", reason="OpenAI not installed"),
        reason="Requires OPENAI_API_KEY"
    )
    def test_delete(self, store, namespace):
        """Test deleting a memory."""
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        memory = MemoryCreate(text="To be deleted", durability=Durability.EPISODIC)
        stored = store.add(namespace, memory)

        result = store.delete(namespace, stored.id)
        assert result is True

        retrieved = store.get(namespace, stored.id)
        assert retrieved is None

    @pytest.mark.skipif(
        not pytest.importorskip("openai", reason="OpenAI not installed"),
        reason="Requires OPENAI_API_KEY"
    )
    def test_list_all(self, store, namespace):
        """Test listing all memories."""
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        # Add some memories
        for i in range(3):
            store.add(namespace, MemoryCreate(
                text=f"Memory {i}",
                durability=Durability.SITUATIONAL,
            ))

        memories = store.list_all(namespace)
        assert len(memories) == 3
