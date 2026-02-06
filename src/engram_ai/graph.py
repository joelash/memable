"""
Pre-built LangGraph with memory capabilities.

Provides a ready-to-use graph with:
- Memory retrieval before LLM call
- Memory extraction after LLM response
- Configurable LLM node
"""

from collections.abc import Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.store.base import BaseStore

from engram_ai.nodes import retrieve_memories_node, store_memories_node


def _default_llm_node(
    state: MessagesState,
    config: RunnableConfig,
    *,
    llm: BaseChatModel,
) -> dict[str, Any]:
    """Default LLM node that just calls the model."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def build_memory_graph(
    llm: BaseChatModel | None = None,
    model_name: str = "gpt-4.1-mini",
    memory_scope: str = "memories",
    retrieval_top_k: int = 10,
    check_contradictions: bool = True,
    custom_llm_node: Callable[..., dict[str, Any]] | None = None,
) -> StateGraph:
    """
    Build a LangGraph with memory retrieval and storage.

    Graph flow:
    START -> retrieve_memories -> llm -> store_memories -> END

    Args:
        llm: LangChain chat model (creates default if not provided).
        model_name: Model name if creating default LLM.
        memory_scope: Memory namespace scope.
        retrieval_top_k: Max memories to retrieve.
        check_contradictions: Enable contradiction detection.
        custom_llm_node: Optional custom LLM node function.

    Returns:
        Compiled StateGraph. Call with store= to inject memory store.

    Example:
        from engram_ai import build_postgres_store
        from engram_ai.graph import build_memory_graph

        store = build_postgres_store(DATABASE_URL)
        store.setup()

        graph = build_memory_graph()
        compiled = graph.compile(store=store.raw_store)

        result = compiled.invoke(
            {"messages": [{"role": "user", "content": "Hi, I'm Joel"}]},
            config={"configurable": {"user_id": "user_123"}}
        )
    """
    if llm is None:
        llm = ChatOpenAI(model=model_name)

    builder = StateGraph(MessagesState)

    # Create node functions with bound parameters
    def retrieve_node(
        state: MessagesState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> dict[str, Any]:
        return retrieve_memories_node(
            state,
            config,
            store=store,
            scope=memory_scope,
            top_k=retrieval_top_k,
        )

    def llm_node(state: MessagesState, config: RunnableConfig) -> dict[str, Any]:
        if custom_llm_node:
            return custom_llm_node(state, config)
        return _default_llm_node(state, config, llm=llm)

    def store_node(
        state: MessagesState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> dict[str, Any]:
        return store_memories_node(
            state,
            config,
            store=store,
            scope=memory_scope,
            check_contradictions=check_contradictions,
        )

    # Add nodes
    builder.add_node("retrieve_memories", retrieve_node)
    builder.add_node("llm", llm_node)
    builder.add_node("store_memories", store_node)

    # Wire up the graph
    builder.add_edge(START, "retrieve_memories")
    builder.add_edge("retrieve_memories", "llm")
    builder.add_edge("llm", "store_memories")
    builder.add_edge("store_memories", END)

    return builder


def build_memory_graph_minimal(
    memory_scope: str = "memories",
    retrieval_top_k: int = 10,
) -> StateGraph:
    """
    Build a minimal memory graph with just retrieve/store (no LLM).

    Use this when you want to plug memory into your own graph structure.

    Graph flow:
    START -> retrieve_memories -> (your nodes here) -> store_memories -> END

    Example:
        builder = build_memory_graph_minimal()

        # Insert your own nodes
        builder.add_node("my_logic", my_logic_node)
        builder.remove_edge("retrieve_memories", END)  # Remove default end
        builder.add_edge("retrieve_memories", "my_logic")
        builder.add_edge("my_logic", "store_memories")
    """
    builder = StateGraph(MessagesState)

    def retrieve_node(
        state: MessagesState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> dict[str, Any]:
        return retrieve_memories_node(
            state,
            config,
            store=store,
            scope=memory_scope,
            top_k=retrieval_top_k,
        )

    def store_node(
        state: MessagesState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> dict[str, Any]:
        return store_memories_node(
            state,
            config,
            store=store,
            scope=memory_scope,
        )

    builder.add_node("retrieve_memories", retrieve_node)
    builder.add_node("store_memories", store_node)

    builder.add_edge(START, "retrieve_memories")
    builder.add_edge("retrieve_memories", "store_memories")
    builder.add_edge("store_memories", END)

    return builder
