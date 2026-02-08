"""
Integration tests for SemanticMemoryStore.

These tests require:
- PostgreSQL with pgvector extension (via testcontainers)
- OPENAI_API_KEY environment variable
"""

from datetime import UTC, datetime, timedelta

import pytest

from engram_ai.schema import (
    Durability,
    Memory,
    MemoryCreate,
    MemoryQuery,
    MemoryUpdate,
)


@pytest.mark.integration
class TestSemanticMemoryStore:
    """Integration tests for the store."""

    def test_add_and_get_memory(self, semantic_store, test_namespace):
        """Test adding and retrieving a memory."""
        mem = MemoryCreate(
            text="User prefers dark mode",
            durability=Durability.CORE,
            confidence=0.95,
        )

        stored = semantic_store.add(test_namespace, mem)

        assert stored.id is not None
        assert stored.text == "User prefers dark mode"

        retrieved = semantic_store.get(test_namespace, stored.id)

        assert retrieved is not None
        assert retrieved.id == stored.id
        assert retrieved.text == stored.text
        assert retrieved.durability == Durability.CORE

    def test_search_memories(self, semantic_store, test_namespace):
        """Test semantic search for memories."""
        # Add several memories
        memories = [
            MemoryCreate(text="User loves Python programming"),
            MemoryCreate(text="User prefers dark mode in editors"),
            MemoryCreate(text="User works at a tech company"),
        ]

        for mem in memories:
            semantic_store.add(test_namespace, mem)

        # Search for related memories
        results = semantic_store.search(test_namespace, "favorite programming language")

        assert len(results) > 0
        # Python memory should be most relevant
        assert any("Python" in m.text for m in results)

    def test_search_with_filters(self, semantic_store, test_namespace):
        """Test search with durability filters."""
        semantic_store.add(
            test_namespace,
            MemoryCreate(text="Core fact", durability=Durability.CORE),
        )
        semantic_store.add(
            test_namespace,
            MemoryCreate(text="Episodic memory", durability=Durability.EPISODIC),
        )

        query = MemoryQuery(
            query="fact",
            durability=[Durability.CORE],
        )
        results = semantic_store.search(test_namespace, query)

        assert all(m.durability == Durability.CORE for m in results)

    def test_update_creates_version_chain(self, semantic_store, test_namespace):
        """Test that update creates a version chain."""
        # Add original memory
        original = semantic_store.add(
            test_namespace,
            MemoryCreate(text="User lives in Chicago", durability=Durability.CORE),
        )

        # Update it
        update = MemoryUpdate(text="User lives in Austin")
        updated = semantic_store.update(test_namespace, original.id, update)

        # Check version chain
        assert updated.supersedes == original.id

        # Original should be superseded
        original_now = semantic_store.get(test_namespace, original.id)
        assert original_now is not None
        assert original_now.superseded_by == updated.id
        assert original_now.superseded_at is not None

    def test_get_version_history(self, semantic_store, test_namespace):
        """Test retrieving version history."""
        # Create and update a memory
        v1 = semantic_store.add(
            test_namespace,
            MemoryCreate(text="Version 1"),
        )
        v2 = semantic_store.update(test_namespace, v1.id, MemoryUpdate(text="Version 2"))
        semantic_store.update(test_namespace, v2.id, MemoryUpdate(text="Version 3"))

        # Get history from any point
        history = semantic_store.get_version_history(test_namespace, v1.id)

        assert len(history) == 3
        assert history[0].text == "Version 1"
        assert history[1].text == "Version 2"
        assert history[2].text == "Version 3"

        # Get current version
        current = semantic_store.get_current_version(test_namespace, v1.id)
        assert current is not None
        assert current.text == "Version 3"

    def test_search_excludes_superseded(self, semantic_store, test_namespace):
        """Test that search excludes superseded memories by default."""
        original = semantic_store.add(
            test_namespace,
            MemoryCreate(text="Old location: Chicago"),
        )
        semantic_store.update(
            test_namespace,
            original.id,
            MemoryUpdate(text="New location: Austin"),
        )

        results = semantic_store.search(test_namespace, "location")

        # Should only find the new version
        texts = [m.text for m in results]
        assert "New location: Austin" in texts
        assert "Old location: Chicago" not in texts

    def test_search_excludes_expired(self, semantic_store, test_namespace):
        """Test that search excludes expired memories by default."""
        # Add expired memory
        expired_mem = Memory(
            text="Visiting Ohio",
            valid_until=datetime.now(UTC) - timedelta(days=1),
        )
        semantic_store.add(test_namespace, expired_mem)

        # Add valid memory
        semantic_store.add(
            test_namespace,
            MemoryCreate(text="Living in Wheaton"),
        )

        results = semantic_store.search(test_namespace, "location")

        texts = [m.text for m in results]
        assert "Visiting Ohio" not in texts

    def test_multi_scope_search(self, semantic_store):
        """Test searching across multiple namespaces."""
        user_ns = ("org_test", "user_123", "memories")
        org_ns = ("org_test", "shared")

        # Add user-specific memory
        semantic_store.add(
            user_ns,
            MemoryCreate(text="User likes Python"),
        )

        # Add org-level memory
        semantic_store.add(
            org_ns,
            MemoryCreate(text="Company uses TypeScript"),
        )

        # Search across both scopes
        results = semantic_store.search_multi_scope(
            [user_ns, org_ns],
            "programming language",
        )

        texts = [m.text for m in results]
        assert "User likes Python" in texts
        assert "Company uses TypeScript" in texts

    def test_delete_memory(self, semantic_store, test_namespace):
        """Test deleting a memory."""
        mem = semantic_store.add(
            test_namespace,
            MemoryCreate(text="To be deleted"),
        )

        assert semantic_store.get(test_namespace, mem.id) is not None

        result = semantic_store.delete(test_namespace, mem.id)

        assert result is True
        assert semantic_store.get(test_namespace, mem.id) is None

    def test_namespace_helper(self, semantic_store):
        """Test namespace tuple generation."""
        # Simple user namespace
        ns = semantic_store.namespace("user_123")
        assert ns == ("user_123", "memories")

        # With org
        ns = semantic_store.namespace("user_123", org_id="org_456")
        assert ns == ("org_456", "user_123", "memories")

        # With project
        ns = semantic_store.namespace(
            "user_123",
            scope="preferences",
            org_id="org_456",
            project_id="proj_789",
        )
        assert ns == ("org_456", "proj_789", "user_123", "preferences")
