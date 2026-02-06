"""
PostgresStore factory with semantic search via OpenAI embeddings.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

from langchain_openai import OpenAIEmbeddings
from langgraph.store.postgres import PostgresStore

from engram_ai.schema import (
    Memory,
    MemoryCreate,
    MemoryQuery,
    MemoryUpdate,
)

# Default embedding model
DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIMS = 1536


@contextmanager
def build_postgres_store(
    conn_str: str | None = None,
    embed_model: str = DEFAULT_EMBED_MODEL,
    dims: int = DEFAULT_EMBED_DIMS,
    embed_fields: list[str] | None = None,
) -> Iterator["SemanticMemoryStore"]:
    """
    Create a SemanticMemoryStore backed by PostgresStore with semantic search.

    This is a context manager that handles connection lifecycle.

    Args:
        conn_str: PostgreSQL connection string. Falls back to DATABASE_URL env var.
        embed_model: OpenAI embedding model name.
        dims: Embedding dimensions.
        embed_fields: Which fields of the stored value to embed. Default: ["text"].

    Yields:
        SemanticMemoryStore instance.

    Example:
        with build_postgres_store("postgresql://user:pass@host:5432/db") as store:
            store.setup()  # Run once to create tables
            store.add(namespace, memory)
    """
    conn_str = conn_str or os.environ.get("DATABASE_URL")
    if not conn_str:
        raise ValueError("Connection string required. Pass conn_str or set DATABASE_URL.")

    embeddings = OpenAIEmbeddings(model=embed_model)

    with PostgresStore.from_conn_string(
        conn_str,
        index={
            "dims": dims,
            "embed": embeddings,
            "fields": embed_fields or ["text"],
        },
    ) as pg_store:
        yield SemanticMemoryStore(pg_store)


class SemanticMemoryStore:
    """
    High-level memory store with durability tiers, version chains, and temporal awareness.

    Wraps PostgresStore and provides:
    - Typed memory operations (add, update, search, delete)
    - Version chain management for contradiction handling
    - Temporal validity filtering
    - Scoped namespace support
    """

    def __init__(self, pg_store: PostgresStore):
        self._store = pg_store

    @property
    def raw_store(self) -> PostgresStore:
        """Access the underlying PostgresStore for advanced operations."""
        return self._store

    def setup(self) -> None:
        """Run database migrations. Call once at app startup."""
        self._store.setup()

    # -------------------------------------------------------------------------
    # Namespace helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def namespace(
        user_id: str,
        scope: str = "memories",
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> tuple[str, ...]:
        """
        Build a hierarchical namespace tuple.

        Examples:
            namespace("user_123") -> ("user_123", "memories")
            namespace("user_123", org_id="org_456") -> ("org_456", "user_123", "memories")
            namespace("user_123", scope="preferences") -> ("user_123", "preferences")
        """
        parts: list[str] = []
        if org_id:
            parts.append(org_id)
        if project_id:
            parts.append(project_id)
        parts.append(user_id)
        parts.append(scope)
        return tuple(parts)

    # -------------------------------------------------------------------------
    # Core operations
    # -------------------------------------------------------------------------

    def add(
        self,
        namespace: tuple[str, ...],
        memory: MemoryCreate | Memory,
    ) -> Memory:
        """
        Add a new memory to the store.

        Args:
            namespace: Hierarchical namespace tuple.
            memory: Memory to store (MemoryCreate or Memory).

        Returns:
            The stored Memory with generated ID.
        """
        if isinstance(memory, MemoryCreate):
            memory = memory.to_memory()

        self._store.put(
            namespace=namespace,
            key=str(memory.id),
            value=memory.to_store_value(),
        )
        return memory

    def get(self, namespace: tuple[str, ...], memory_id: str | UUID) -> Memory | None:
        """
        Get a specific memory by ID.

        Args:
            namespace: Hierarchical namespace tuple.
            memory_id: Memory UUID.

        Returns:
            Memory if found, None otherwise.
        """
        result = self._store.get(namespace=namespace, key=str(memory_id))
        if result is None:
            return None
        return Memory.from_store_value(result.value)

    def update(
        self,
        namespace: tuple[str, ...],
        memory_id: str | UUID,
        update: MemoryUpdate,
    ) -> Memory:
        """
        Update a memory by creating a new version (version chain).

        The old memory is marked as superseded; a new memory is created
        with supersedes pointing to the old one.

        Args:
            namespace: Hierarchical namespace tuple.
            memory_id: ID of the memory to update.
            update: New values for the memory.

        Returns:
            The new Memory (head of version chain).

        Raises:
            ValueError: If the memory doesn't exist.
        """
        old_memory = self.get(namespace, memory_id)
        if old_memory is None:
            raise ValueError(f"Memory {memory_id} not found")

        # Create new version
        new_memory = Memory(
            text=update.text,
            durability=old_memory.durability,  # Keep durability tier
            confidence=update.confidence,
            source=update.source,
            valid_from=update.valid_from or datetime.now(UTC),
            valid_until=update.valid_until,
            supersedes=old_memory.id,
            tags=old_memory.tags,  # Inherit tags
            metadata={**old_memory.metadata, "previous_version": str(old_memory.id)},
        )

        # Mark old memory as superseded
        old_memory.superseded_by = new_memory.id
        old_memory.superseded_at = datetime.now(UTC)

        # Store both
        self._store.put(
            namespace=namespace,
            key=str(old_memory.id),
            value=old_memory.to_store_value(),
        )
        self._store.put(
            namespace=namespace,
            key=str(new_memory.id),
            value=new_memory.to_store_value(),
        )

        return new_memory

    def delete(self, namespace: tuple[str, ...], memory_id: str | UUID) -> bool:
        """
        Hard delete a memory.

        For audit trails, prefer update() which creates version chains.

        Args:
            namespace: Hierarchical namespace tuple.
            memory_id: Memory UUID.

        Returns:
            True if deleted, False if not found.
        """
        try:
            self._store.delete(namespace=namespace, key=str(memory_id))
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(
        self,
        namespace: tuple[str, ...],
        query: MemoryQuery | str,
    ) -> list[Memory]:
        """
        Semantic search for memories.

        Args:
            namespace: Hierarchical namespace tuple.
            query: Search query (string or MemoryQuery for filters).

        Returns:
            List of matching Memory objects, ordered by relevance.
        """
        if isinstance(query, str):
            query = MemoryQuery(query=query)

        # Use PostgresStore's semantic search
        # namespace_prefix is positional-only in PostgresStore.search
        results = self._store.search(
            namespace,
            query=query.query,
            limit=query.limit * 2,  # Fetch extra to filter
        )

        memories: list[Memory] = []
        check_time = query.valid_at or datetime.now(UTC)

        for result in results:
            try:
                memory = Memory.from_store_value(result.value)
            except Exception:
                continue  # Skip malformed entries

            # Apply filters
            if not query.include_superseded and not memory.is_current():
                continue

            if not query.include_expired and not memory.is_valid(at=check_time):
                continue

            if memory.confidence < query.min_confidence:
                continue

            if query.durability and memory.durability not in query.durability:
                continue

            if query.tags and not any(t in memory.tags for t in query.tags):
                continue

            memories.append(memory)

            if len(memories) >= query.limit:
                break

        return memories

    def search_multi_scope(
        self,
        scopes: list[tuple[str, ...]],
        query: MemoryQuery | str,
        dedupe: bool = True,
    ) -> list[Memory]:
        """
        Search across multiple namespaces with priority ordering.

        Results from earlier scopes take priority. Useful for:
        - User preferences (user scope) > org defaults (org scope)
        - Project context > user context > org context

        Args:
            scopes: List of namespaces in priority order (first = highest).
            query: Search query.
            dedupe: Remove duplicate texts across scopes.

        Returns:
            Combined list of memories, priority-ordered.
        """
        if isinstance(query, str):
            query = MemoryQuery(query=query)

        all_memories: list[Memory] = []
        seen_texts: set[str] = set()

        for scope in scopes:
            scope_memories = self.search(scope, query)
            for mem in scope_memories:
                if dedupe and mem.text in seen_texts:
                    continue
                seen_texts.add(mem.text)
                all_memories.append(mem)

                if len(all_memories) >= query.limit:
                    return all_memories

        return all_memories

    # -------------------------------------------------------------------------
    # Version chain operations
    # -------------------------------------------------------------------------

    def get_version_history(
        self,
        namespace: tuple[str, ...],
        memory_id: str | UUID,
    ) -> list[Memory]:
        """
        Get the full version chain for a memory.

        Traverses both directions (supersedes and superseded_by) to build
        the complete history.

        Args:
            namespace: Hierarchical namespace tuple.
            memory_id: Any memory ID in the chain.

        Returns:
            List of memories in chronological order (oldest first).
        """
        memory = self.get(namespace, memory_id)
        if memory is None:
            return []

        # Walk back to find the oldest version
        current = memory
        while current.supersedes:
            prev = self.get(namespace, current.supersedes)
            if prev is None:
                break
            current = prev

        # Now walk forward to collect all versions
        history: list[Memory] = [current]
        while current.superseded_by:
            next_mem = self.get(namespace, current.superseded_by)
            if next_mem is None:
                break
            history.append(next_mem)
            current = next_mem

        return history

    def get_current_version(
        self,
        namespace: tuple[str, ...],
        memory_id: str | UUID,
    ) -> Memory | None:
        """
        Get the current (head) version of a memory chain.

        Args:
            namespace: Hierarchical namespace tuple.
            memory_id: Any memory ID in the chain.

        Returns:
            The current version, or None if not found.
        """
        history = self.get_version_history(namespace, memory_id)
        return history[-1] if history else None

    # -------------------------------------------------------------------------
    # Bulk operations
    # -------------------------------------------------------------------------

    def list_all(
        self,
        namespace: tuple[str, ...],
        include_superseded: bool = False,
        include_expired: bool = False,
    ) -> list[Memory]:
        """
        List all memories in a namespace.

        Args:
            namespace: Hierarchical namespace tuple.
            include_superseded: Include old versions.
            include_expired: Include expired memories.

        Returns:
            List of memories.
        """
        # PostgresStore doesn't have a direct list method with namespace filtering,
        # so we use a broad search. This is not efficient for large stores.
        # TODO: Add proper list support when PostgresStore API allows it.
        results = self._store.search(
            namespace,  # positional-only
            query=None,  # None to get all without vector search
            limit=1000,
        )

        memories: list[Memory] = []
        now = datetime.now(UTC)

        for result in results:
            try:
                memory = Memory.from_store_value(result.value)
            except Exception:
                continue

            if not include_superseded and not memory.is_current():
                continue

            if not include_expired and not memory.is_valid(at=now):
                continue

            memories.append(memory)

        return memories

    def count(
        self,
        namespace: tuple[str, ...],
        include_superseded: bool = False,
    ) -> int:
        """Count memories in a namespace."""
        return len(self.list_all(namespace, include_superseded=include_superseded))
