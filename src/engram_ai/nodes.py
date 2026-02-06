"""
LangGraph nodes for memory operations.

These nodes can be plugged into any LangGraph to add memory capabilities:
- retrieve_memories_node: Fetches relevant memories and adds to message context
- store_memories_node: Extracts and stores memories from conversation
- consolidate_memories_node: Periodic cleanup and consolidation
"""

from typing import Any

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState
from langgraph.store.base import BaseStore

from engram_ai.contradiction import (
    ContradictionDetector,
    add_memory_with_contradiction_check,
)
from engram_ai.extraction import MemoryExtractor
from engram_ai.retrieval import build_memory_context, retrieve_memories
from engram_ai.store import SemanticMemoryStore


def retrieve_memories_node(
    state: MessagesState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    scope: str = "memories",
    top_k: int = 10,
    min_confidence: float = 0.0,
    include_org_shared: bool = True,
) -> dict[str, Any]:
    """
    LangGraph node that retrieves relevant memories and prepends to messages.

    Expects config["configurable"]["user_id"] to be set.
    Optionally uses config["configurable"]["org_id"] for scoped namespaces.

    Args:
        state: Current graph state with messages.
        config: Runnable config with user_id in configurable.
        store: LangGraph BaseStore instance.
        scope: Memory scope to search.
        top_k: Maximum memories to retrieve.
        min_confidence: Minimum confidence threshold.
        include_org_shared: Also search org-level memories.

    Returns:
        Updated state with memory-augmented messages.
    """
    user_id = config["configurable"]["user_id"]
    org_id = config["configurable"].get("org_id")

    # Get the last user message as the query
    messages = state["messages"]
    last_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content if isinstance(msg.content, str) else str(msg.content)
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    if not last_user_msg:
        return {"messages": messages}

    # Wrap the BaseStore in our SemanticMemoryStore
    semantic_store = SemanticMemoryStore(store)  # type: ignore

    # Retrieve memories
    result = retrieve_memories(
        store=semantic_store,
        user_id=user_id,
        query=last_user_msg,
        limit=top_k,
        min_confidence=min_confidence,
        scope=scope,
        org_id=org_id,
        include_org_shared=include_org_shared,
    )

    if result.count == 0:
        return {"messages": messages}

    # Build memory context
    memory_context = build_memory_context(result)

    # Prepend as a system message
    memory_msg = SystemMessage(content=memory_context)

    return {"messages": [memory_msg, *messages]}


async def aretrieve_memories_node(
    state: MessagesState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    **kwargs: Any,
) -> dict[str, Any]:
    """Async version of retrieve_memories_node."""
    # For now, just call sync version - PostgresStore search is not async
    return retrieve_memories_node(state, config, store=store, **kwargs)


def store_memories_node(
    state: MessagesState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    scope: str = "memories",
    model: str = "gpt-4.1-mini",
    check_contradictions: bool = True,
) -> dict[str, Any]:
    """
    LangGraph node that extracts and stores memories from conversation.

    Expects config["configurable"]["user_id"] to be set.

    Args:
        state: Current graph state with messages.
        config: Runnable config with user_id in configurable.
        store: LangGraph BaseStore instance.
        scope: Memory scope to store to.
        model: Model for extraction.
        check_contradictions: Whether to check and resolve contradictions.

    Returns:
        Empty dict (state unchanged, memories stored as side effect).
    """
    user_id = config["configurable"]["user_id"]
    org_id = config["configurable"].get("org_id")

    messages = state["messages"]

    # Convert LangChain messages to dicts for extraction
    msg_dicts = []
    for msg in messages:
        if hasattr(msg, "type"):
            role = "assistant" if msg.type == "ai" else "user"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            msg_dicts.append({"role": role, "content": content})
        elif isinstance(msg, dict):
            msg_dicts.append(msg)

    # Extract memories
    extractor = MemoryExtractor(model=model)
    extracted = extractor.extract(msg_dicts)

    if not extracted:
        return {}

    # Wrap store
    semantic_store = SemanticMemoryStore(store)  # type: ignore
    namespace = semantic_store.namespace(user_id, scope=scope, org_id=org_id)

    detector = ContradictionDetector(model=model) if check_contradictions else None

    # Store each extracted memory
    for mem_create in extracted:
        if check_contradictions and detector:
            add_memory_with_contradiction_check(
                store=semantic_store,
                namespace=namespace,
                new_fact=mem_create.text,
                confidence=mem_create.confidence,
                source=mem_create.source,
                detector=detector,
            )
        else:
            semantic_store.add(namespace, mem_create)

    return {}


async def astore_memories_node(
    state: MessagesState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    **kwargs: Any,
) -> dict[str, Any]:
    """Async version of store_memories_node."""
    user_id = config["configurable"]["user_id"]
    org_id = config["configurable"].get("org_id")
    scope = kwargs.get("scope", "memories")
    model = kwargs.get("model", "gpt-4.1-mini")
    kwargs.get("check_contradictions", True)

    messages = state["messages"]

    msg_dicts = []
    for msg in messages:
        if hasattr(msg, "type"):
            role = "assistant" if msg.type == "ai" else "user"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            msg_dicts.append({"role": role, "content": content})
        elif isinstance(msg, dict):
            msg_dicts.append(msg)

    extractor = MemoryExtractor(model=model)
    extracted = await extractor.aextract(msg_dicts)

    if not extracted:
        return {}

    semantic_store = SemanticMemoryStore(store)  # type: ignore
    namespace = semantic_store.namespace(user_id, scope=scope, org_id=org_id)

    # Contradiction checking is sync for now
    for mem_create in extracted:
        semantic_store.add(namespace, mem_create)

    return {}


def consolidate_memories_node(
    state: MessagesState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    scope: str = "memories",
    strategy: str = "prune_expired",
    older_than_days: int = 30,
) -> dict[str, Any]:
    """
    LangGraph node for periodic memory consolidation.

    Typically called on a schedule rather than every turn.

    Args:
        state: Current graph state.
        config: Runnable config with user_id.
        store: LangGraph BaseStore instance.
        scope: Memory scope to consolidate.
        strategy: Consolidation strategy.
        older_than_days: Age threshold for consolidation.

    Returns:
        Empty dict (consolidation is a side effect).
    """
    from engram_ai.consolidation import consolidate_memories

    user_id = config["configurable"]["user_id"]
    org_id = config["configurable"].get("org_id")

    semantic_store = SemanticMemoryStore(store)  # type: ignore

    consolidate_memories(
        store=semantic_store,
        user_id=user_id,
        strategy=strategy,
        scope=scope,
        org_id=org_id,
        older_than_days=older_than_days,
    )

    return {}
