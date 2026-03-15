"""
Memory consolidation: decay, summarize, and prune old memories.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from memable.schema import Durability, Memory, MemoryCreate, MemorySource
from memable.store import SemanticMemoryStore

DEFAULT_MODEL = "gpt-4.1-mini"


class ConsolidationStrategy(StrEnum):
    """Memory consolidation strategies."""

    PRUNE_EXPIRED = "prune_expired"
    """Remove memories past their valid_until date."""

    DECAY_ACCESS = "decay_access"
    """Remove memories not accessed in a long time."""

    SUMMARIZE = "summarize"
    """Summarize groups of related memories into single entries."""

    DEDUPE = "dedupe"
    """Remove near-duplicate memories."""


class ConsolidationResult(BaseModel):
    """Result of a consolidation run."""

    strategy: ConsolidationStrategy
    memories_processed: int = 0
    memories_removed: int = 0
    memories_created: int = 0
    summaries_created: int = 0
    details: list[str] = Field(default_factory=list)


SUMMARIZE_PROMPT = """\
You are consolidating a group of related memories into a single, denser memory.

These memories are about the same topic or entity. Combine them into one
or more concise summaries that preserve the key information.

Original memories:
{memories}

Rules:
- Preserve all important facts
- Remove redundancy
- Keep the most recent/specific information when there are conflicts
- Output should be shorter than the combined input

Respond with JSON:
{{
  "summaries": [
    "Combined summary text 1",
    "Combined summary text 2 (if needed)"
  ],
  "reasoning": "Why these were combined this way"
}}
"""


def consolidate_memories(
    store: SemanticMemoryStore,
    user_id: str,
    strategy: ConsolidationStrategy | str = ConsolidationStrategy.PRUNE_EXPIRED,
    scope: str = "memories",
    org_id: str | None = None,
    older_than_days: int = 30,
    access_threshold_days: int = 60,
    min_group_size: int = 3,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
) -> ConsolidationResult:
    """
    Run memory consolidation with the specified strategy.

    Args:
        store: SemanticMemoryStore instance.
        user_id: User to consolidate memories for.
        strategy: Consolidation strategy to use.
        scope: Memory scope.
        org_id: Optional org ID for namespacing.
        older_than_days: For age-based strategies, the age threshold.
        access_threshold_days: For decay strategy, remove if not accessed in this many days.
        min_group_size: For summarize strategy, minimum memories to group.
        model: LLM model for summarization.
        dry_run: If True, don't actually modify anything.

    Returns:
        ConsolidationResult with stats.
    """
    if isinstance(strategy, str):
        strategy = ConsolidationStrategy(strategy)

    namespace = store.namespace(user_id, scope=scope, org_id=org_id)

    if strategy == ConsolidationStrategy.PRUNE_EXPIRED:
        return _prune_expired(store, namespace, dry_run)
    elif strategy == ConsolidationStrategy.DECAY_ACCESS:
        return _decay_access(store, namespace, access_threshold_days, dry_run)
    elif strategy == ConsolidationStrategy.SUMMARIZE:
        return _summarize_groups(store, namespace, older_than_days, min_group_size, model, dry_run)
    elif strategy == ConsolidationStrategy.DEDUPE:
        return _dedupe(store, namespace, dry_run)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def _prune_expired(
    store: SemanticMemoryStore,
    namespace: tuple[str, ...],
    dry_run: bool,
) -> ConsolidationResult:
    """Remove memories past their valid_until date."""
    result = ConsolidationResult(strategy=ConsolidationStrategy.PRUNE_EXPIRED)

    # Get all memories including expired
    memories = store.list_all(namespace, include_expired=True)
    result.memories_processed = len(memories)

    now = datetime.now(UTC)

    for mem in memories:
        if mem.valid_until and mem.valid_until < now:
            result.details.append(f"Expired: {mem.text[:50]}...")
            if not dry_run:
                store.delete(namespace, mem.id)
            result.memories_removed += 1

    return result


def _decay_access(
    store: SemanticMemoryStore,
    namespace: tuple[str, ...],
    threshold_days: int,
    dry_run: bool,
) -> ConsolidationResult:
    """Remove memories not accessed recently (only episodic tier)."""
    result = ConsolidationResult(strategy=ConsolidationStrategy.DECAY_ACCESS)

    memories = store.list_all(namespace)
    result.memories_processed = len(memories)

    cutoff = datetime.now(UTC) - timedelta(days=threshold_days)

    for mem in memories:
        # Only decay episodic memories
        if mem.durability != Durability.EPISODIC:
            continue

        last_access = mem.last_accessed_at or mem.created_at
        if last_access < cutoff:
            msg = f"Decayed (not accessed in {threshold_days}d): {mem.text[:50]}..."
            result.details.append(msg)
            if not dry_run:
                store.delete(namespace, mem.id)
            result.memories_removed += 1

    return result


def _summarize_groups(
    store: SemanticMemoryStore,
    namespace: tuple[str, ...],
    older_than_days: int,
    min_group_size: int,
    model: str,
    dry_run: bool,
) -> ConsolidationResult:
    """Summarize groups of related memories."""
    result = ConsolidationResult(strategy=ConsolidationStrategy.SUMMARIZE)

    memories = store.list_all(namespace)
    result.memories_processed = len(memories)

    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)

    # Filter to old episodic memories
    old_episodic = [
        m for m in memories
        if m.durability == Durability.EPISODIC and m.created_at < cutoff
    ]

    if len(old_episodic) < min_group_size:
        msg = "Not enough old episodic memories to summarize "
        msg += f"({len(old_episodic)} < {min_group_size})"
        result.details.append(msg)
        return result

    # Group by tags (simple clustering)
    tag_groups: dict[str, list[Memory]] = {}
    untagged: list[Memory] = []

    for mem in old_episodic:
        if mem.tags:
            for tag in mem.tags:
                tag_groups.setdefault(tag, []).append(mem)
        else:
            untagged.append(mem)

    llm = ChatOpenAI(model=model, temperature=0)

    # Summarize each group
    for tag, group in tag_groups.items():
        if len(group) < min_group_size:
            continue

        summary_result = _summarize_group(llm, group, namespace, store, dry_run)
        result.memories_removed += summary_result["removed"]
        result.memories_created += summary_result["created"]
        result.summaries_created += 1
        result.details.append(f"Summarized {len(group)} memories tagged '{tag}'")

    # Summarize untagged if big enough
    if len(untagged) >= min_group_size:
        summary_result = _summarize_group(llm, untagged, namespace, store, dry_run)
        result.memories_removed += summary_result["removed"]
        result.memories_created += summary_result["created"]
        result.summaries_created += 1
        result.details.append(f"Summarized {len(untagged)} untagged memories")

    return result


def _summarize_group(
    llm: ChatOpenAI,
    memories: list[Memory],
    namespace: tuple[str, ...],
    store: SemanticMemoryStore,
    dry_run: bool,
) -> dict[str, int]:
    """Summarize a group of memories into fewer entries."""
    import json

    # Format memories for prompt
    mem_lines = [f"- {m.text}" for m in memories]
    prompt = SUMMARIZE_PROMPT.format(memories="\n".join(mem_lines))

    response = llm.invoke([
        SystemMessage(content="You are a memory consolidation system."),
        HumanMessage(content=prompt),
    ])

    content = response.content if isinstance(response.content, str) else str(response.content)

    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        summaries = data.get("summaries", [])
    except Exception:
        return {"removed": 0, "created": 0}

    if not summaries:
        return {"removed": 0, "created": 0}

    if dry_run:
        return {"removed": len(memories), "created": len(summaries)}

    # Create summary memories
    for summary_text in summaries:
        store.add(
            namespace=namespace,
            memory=MemoryCreate(
                text=summary_text,
                durability=Durability.EPISODIC,
                source=MemorySource.SYSTEM,
                tags=["consolidated"],
                metadata={
                    "consolidated_from": [str(m.id) for m in memories],
                    "consolidation_date": datetime.now(UTC).isoformat(),
                },
            ),
        )

    # Delete original memories
    for mem in memories:
        store.delete(namespace, mem.id)

    return {"removed": len(memories), "created": len(summaries)}


def _dedupe(
    store: SemanticMemoryStore,
    namespace: tuple[str, ...],
    dry_run: bool,
) -> ConsolidationResult:
    """Remove near-duplicate memories (keep the one with higher confidence)."""
    result = ConsolidationResult(strategy=ConsolidationStrategy.DEDUPE)

    memories = store.list_all(namespace)
    result.memories_processed = len(memories)

    # Simple deduplication: exact text match
    seen: dict[str, Memory] = {}
    to_remove: list[Memory] = []

    for mem in memories:
        normalized = mem.text.lower().strip()
        if normalized in seen:
            existing = seen[normalized]
            # Keep the one with higher confidence, or newer if equal
            if mem.confidence > existing.confidence:
                to_remove.append(existing)
                seen[normalized] = mem
            elif mem.confidence == existing.confidence and mem.created_at > existing.created_at:
                to_remove.append(existing)
                seen[normalized] = mem
            else:
                to_remove.append(mem)
        else:
            seen[normalized] = mem

    for mem in to_remove:
        result.details.append(f"Duplicate removed: {mem.text[:50]}...")
        if not dry_run:
            store.delete(namespace, mem.id)
        result.memories_removed += 1

    return result
