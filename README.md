<p align="center">
  <img src="assets/logo.png" alt="ai-semantic-memory logo" width="200">
</p>

<h1 align="center">ai-semantic-memory</h1>

<p align="center">
  <em>Reusable semantic memory library for LangGraph agents</em>
</p>

---

Drop-in long-term memory with:

- **Durability tiers** — core facts vs situational context vs episodic memories
- **Temporal awareness** — validity windows, expiry, recency weighting
- **Version chains** — audit trail for memory updates with contradiction handling
- **Scoped namespaces** — org/user/project hierarchies with priority merging
- **Memory consolidation** — decay, summarize, and prune old memories
- **LangGraph integration** — ready-to-use nodes for retrieve/store/consolidate

## Installation

```bash
pip install ai-semantic-memory
```

Or for development:

```bash
git clone https://github.com/joelash/ai-semantic-memory
cd ai-semantic-memory
pip install -e ".[dev]"
```

## Quick Start

```python
from ai_semantic_memory import build_postgres_store
from ai_semantic_memory.graph import build_memory_graph

# Connect to your Neon/Postgres DB (context manager handles connection lifecycle)
with build_postgres_store("postgresql://user:pass@host:5432/dbname") as store:
    store.setup()  # Run migrations (once)

    # Build a graph with memory baked in
    graph = build_memory_graph()
    compiled = graph.compile(store=store.raw_store)

    # Run it
    config = {"configurable": {"user_id": "user_123"}}
    result = compiled.invoke(
        {"messages": [{"role": "user", "content": "I'm Joel, I live in Wheaton."}]},
        config=config,
    )
```

## Memory Schema

Each memory item includes:

```python
{
    "text": "User lives in Wheaton, IL",
    "durability": "core",           # core | situational | episodic
    "valid_from": "2026-02-06",     # when this became true
    "valid_until": None,            # null = permanent
    "confidence": 0.95,
    "source": "explicit",           # explicit | inferred
    "supersedes": None,             # UUID of memory this replaces (version chain)
    "superseded_by": None,          # UUID of memory that replaced this
}
```

## Durability Tiers

| Tier | Description | Example | Default TTL |
|------|-------------|---------|-------------|
| `core` | Stable facts about the user | "Name is Joel", "Prefers dark mode" | Never expires |
| `situational` | Temporary context | "Visiting Ohio this week" | Explicit end date |
| `episodic` | Things that happened | "We discussed the API design" | 30 days, decays |

## Features

### Version Chains (Contradiction Handling)

When a memory contradicts an existing one, we don't delete — we create a version chain:

```python
# Original: "User lives in Wheaton"
# New info: "User moved to Austin"

# Result:
# - Old memory gets superseded_by = new_memory_id
# - New memory gets supersedes = old_memory_id
# - Retrieval only returns current (non-superseded) memories
# - Audit trail preserved for debugging
```

### Scoped Namespaces

```python
# Retrieval merges across scopes with priority
retrieve_memories(
    store=store,
    scopes=[
        ("org_123", "user_456", "preferences"),  # highest priority
        ("org_123", "shared"),                    # org-wide fallback
    ],
    query="user preferences",
)
```

### Memory Consolidation

```python
from ai_semantic_memory import consolidate_memories

# Periodic cleanup job
consolidate_memories(
    store=store,
    user_id="user_123",
    strategy="summarize_and_prune",
    older_than_days=7,
)
```

## LangGraph Nodes

Pre-built nodes for your graph:

```python
from ai_semantic_memory.nodes import (
    retrieve_memories_node,
    store_memories_node,
    consolidate_memories_node,
)

builder = StateGraph(MessagesState)
builder.add_node("retrieve", retrieve_memories_node)
builder.add_node("llm", your_llm_node)
builder.add_node("store", store_memories_node)

builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "llm")
builder.add_edge("llm", "store")
builder.add_edge("store", END)
```

## Configuration

Environment variables:

```bash
OPENAI_API_KEY=sk-...           # For embeddings
DATABASE_URL=postgresql://...    # Postgres connection
```

## License

MIT
