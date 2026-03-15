"""
Memory retrieval with recency weighting and context formatting.
"""

from datetime import UTC, datetime
from typing import Any

from memable.schema import Durability, Memory, MemoryQuery, MemoryType
from memable.store import SemanticMemoryStore


class RetrievalResult:
    """Result of memory retrieval with formatted context."""

    def __init__(self, memories: list[Memory], query: str):
        self.memories = memories
        self.query = query

    @property
    def count(self) -> int:
        return len(self.memories)

    def as_context_string(
        self,
        format: str = "bullets",
        include_metadata: bool = False,
        max_chars: int | None = None,
    ) -> str:
        """
        Format memories as a context string for LLM prompts.

        Args:
            format: "bullets", "numbered", or "prose"
            include_metadata: Include durability and confidence info
            max_chars: Truncate to this length if set

        Returns:
            Formatted string suitable for injection into prompts.
        """
        if not self.memories:
            return "No relevant memories found."

        lines: list[str] = []

        for i, mem in enumerate(self.memories, 1):
            if format == "numbered":
                prefix = f"{i}. "
            elif format == "bullets":
                prefix = "- "
            else:
                prefix = ""

            line = f"{prefix}{mem.text}"

            if include_metadata:
                meta_parts = [f"[{mem.durability.value}]"]
                if mem.memory_type:
                    meta_parts.append(f"[{mem.memory_type.value}]")
                if mem.confidence < 1.0:
                    meta_parts.append(f"conf={mem.confidence:.0%}")
                line += f" {' '.join(meta_parts)}"

            lines.append(line)

        result = "\n".join(lines)

        if max_chars and len(result) > max_chars:
            result = result[: max_chars - 3] + "..."

        return result

    def as_dict_list(self) -> list[dict[str, Any]]:
        """Return memories as a list of dicts."""
        return [
            {
                "text": m.text,
                "durability": m.durability.value,
                "memory_type": m.memory_type.value if m.memory_type else None,
                "confidence": m.confidence,
                "created_at": m.created_at.isoformat(),
            }
            for m in self.memories
        ]


def retrieve_memories(
    store: SemanticMemoryStore,
    user_id: str,
    query: str,
    limit: int = 10,
    min_confidence: float = 0.0,
    durability_filter: list[Durability] | None = None,
    memory_type_filter: list[MemoryType] | None = None,
    scope: str = "memories",
    org_id: str | None = None,
    include_org_shared: bool = True,
    recency_boost: bool = True,
) -> RetrievalResult:
    """
    Retrieve relevant memories with optional multi-scope search.

    Args:
        store: SemanticMemoryStore instance.
        user_id: User identifier.
        query: Semantic search query.
        limit: Maximum results.
        min_confidence: Minimum confidence threshold.
        durability_filter: Only return specific durability tiers.
        memory_type_filter: Only return specific memory types (fact, rule, etc.).
        scope: Memory scope (e.g., "memories", "preferences").
        org_id: Organization ID for scoped namespaces.
        include_org_shared: Also search org-level shared memories.
        recency_boost: Boost recently accessed memories.

    Returns:
        RetrievalResult with memories and formatting helpers.
    """
    # Build scopes in priority order
    scopes: list[tuple[str, ...]] = []

    # User-specific memories (highest priority)
    user_ns = store.namespace(user_id, scope=scope, org_id=org_id)
    scopes.append(user_ns)

    # Org shared memories (if applicable)
    if include_org_shared and org_id:
        org_ns = (org_id, "shared")
        scopes.append(org_ns)

    # Build query
    mem_query = MemoryQuery(
        query=query,
        limit=limit,
        min_confidence=min_confidence,
        durability=durability_filter,
        memory_type=memory_type_filter,
    )

    # Search across scopes
    if len(scopes) > 1:
        memories = store.search_multi_scope(scopes, mem_query)
    else:
        memories = store.search(scopes[0], mem_query)

    # Apply recency boost (re-sort by combining relevance + recency)
    if recency_boost and memories:
        memories = _apply_recency_boost(memories)

    # Update access stats (fire and forget)
    _update_access_stats(store, scopes[0], memories)

    return RetrievalResult(memories, query)


def _apply_recency_boost(
    memories: list[Memory],
    recency_weight: float = 0.2,
) -> list[Memory]:
    """
    Re-order memories by combining semantic relevance with recency.

    Memories are already ordered by semantic similarity from the store.
    This adds a recency factor based on last_accessed_at and created_at.
    """
    if not memories:
        return memories

    now = datetime.now(UTC)

    def recency_score(mem: Memory) -> float:
        # Use last_accessed_at if available, else created_at
        reference_time = mem.last_accessed_at or mem.created_at
        age_days = (now - reference_time).days
        # Exponential decay: recent = higher score
        return 1.0 / (1.0 + age_days * 0.1)

    # Assign position scores (earlier = more relevant semantically)
    scored: list[tuple[Memory, float]] = []
    for i, mem in enumerate(memories):
        semantic_score = 1.0 - (i / len(memories))  # 1.0 for first, lower for later
        rec_score = recency_score(mem)
        combined = (1 - recency_weight) * semantic_score + recency_weight * rec_score
        scored.append((mem, combined))

    # Re-sort by combined score
    scored.sort(key=lambda x: x[1], reverse=True)

    return [mem for mem, _ in scored]


def _update_access_stats(
    store: SemanticMemoryStore,
    namespace: tuple[str, ...],
    memories: list[Memory],
) -> None:
    """
    Update access timestamps and counts for retrieved memories.

    This helps with recency boosting and usage analytics.
    """
    now = datetime.now(UTC)

    for mem in memories:
        mem.last_accessed_at = now
        mem.access_count += 1

        # Write back to store
        try:
            store._store.put(
                namespace=namespace,
                key=str(mem.id),
                value=mem.to_store_value(),
            )
        except Exception:
            pass  # Best effort, don't fail retrieval on stats update


def build_memory_context(
    result: RetrievalResult,
    prefix: str = "MEMORIES",
    format: str = "bullets",
) -> str:
    """
    Build a context block for LLM prompts.

    Args:
        result: RetrievalResult from retrieve_memories.
        prefix: Section header.
        format: "bullets", "numbered", or "prose".

    Returns:
        Formatted context string like:
        "MEMORIES:\n- User prefers dark mode\n- User lives in Wheaton"
    """
    if result.count == 0:
        return f"{prefix}: None available."

    body = result.as_context_string(format=format)
    return f"{prefix}:\n{body}"
