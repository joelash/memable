<p align="center">
  <img src="assets/memable-hero.png" alt="memable - AI memory that never forgets" width="600">
</p>

<h1 align="center">memable 🐘</h1>

<p align="center">
  <em>Long-term semantic memory for AI agents. Elephants never forget.</em>
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
pip install memable
```

Or for development:

```bash
git clone https://github.com/joelash/memable
cd memable
pip install -e ".[dev]"
```

## Quick Start

```python
from memable import build_postgres_store
from memable.graph import build_memory_graph

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
from memable import consolidate_memories

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
from memable.nodes import (
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

## Performance & Costs

### Storage Requirements

| Scale | Memories | SQLite | DuckDB | Postgres |
|-------|----------|--------|--------|----------|
| Light user | 100 | ~700 KB | ~3 MB | ~700 KB |
| Regular user | 1,000 | ~7 MB | ~30 MB | ~7 MB |
| Heavy user | 10,000 | ~70 MB | ~300 MB | ~70 MB |
| Power user | 100,000 | ~700 MB | ~3 GB | ~700 MB |

*Embeddings dominate storage: 1536 dims × 4 bytes = ~6KB per memory*

### API Costs (text-embedding-3-small)

| Usage | Daily Tokens | Daily Cost | Monthly Cost |
|-------|--------------|------------|--------------|
| Light (100 adds, 500 searches) | 7,000 | $0.0001 | $0.00 |
| Medium (500 adds, 2,000 searches) | 30,000 | $0.0006 | $0.02 |
| Heavy (2,000 adds, 10,000 searches) | 140,000 | $0.0028 | $0.08 |

### Extraction Costs (gpt-4.1-mini)

If using LLM-based memory extraction:

| Usage | Daily Cost | Monthly Cost |
|-------|------------|--------------|
| Light (50 extractions) | $0.007 | $0.20 |
| Medium (200 extractions) | $0.027 | $0.81 |
| Heavy (1,000 extractions) | $0.135 | $4.05 |

**Total cost for a typical agent (100 conversations/day):** ~$0.08-0.50/month

Run `pytest tests/performance/ -v -s` to benchmark on your hardware.

## Configuration

Environment variables:

```bash
# Embeddings (one of these)
OPENAI_API_KEY=sk-...           # Use OpenAI embeddings
MEMABLE_EMBEDDINGS=ollama       # Force Ollama (auto-detects by default)
OLLAMA_HOST=http://localhost:11434  # Ollama server URL (optional)

# Database
DATABASE_URL=postgresql://...    # Postgres connection
```

## Local Embeddings with Ollama

For fully local operation without OpenAI, use [Ollama](https://ollama.ai):

```bash
# Install Ollama, then pull the embedding model
ollama pull nomic-embed-text
```

memable auto-detects Ollama when no `OPENAI_API_KEY` is set:

```python
from memable import create_embeddings, build_store

# Auto-detects: Ollama if available, else OpenAI if key set
embeddings = create_embeddings()

# Or force Ollama explicitly
embeddings = create_embeddings(provider="ollama")

# Use with store
with build_store("sqlite:///memories.db", embeddings=embeddings) as store:
    store.setup()
    # ...
```

You can also use `OllamaEmbeddings` directly (LangChain-compatible):

```python
from memable import OllamaEmbeddings

embeddings = OllamaEmbeddings(model="nomic-embed-text")
```

> **Note:** Don't mix embedding providers in the same database — vector dimensions differ (OpenAI: 1536, nomic-embed-text: 768).

## Multi-Tenant / Schema Isolation

For multi-tenant deployments where each customer needs isolated data, you can use PostgreSQL schemas:

```python
from memable import build_store

# Each tenant gets their own schema
with build_store("postgresql://...", schema="customer_123") as store:
    store.setup()  # Creates tables in customer_123 schema
    store.add(namespace, memory)
```

**Requirements:**
- The schema must already exist in the database (`CREATE SCHEMA customer_123;`)
- Tables will be created within that schema when `setup()` is called
- Each schema has its own isolated set of tables

### Database Tables

memable uses LangGraph's PostgresStore under the hood, which creates:

| Table | Purpose |
|-------|---------|
| `store` | Memory documents with metadata |
| `store_vectors` | pgvector embeddings for semantic search |
| `store_migrations` | Migration version tracking |

**Note:** Table names are currently fixed by LangGraph. If you need custom table names (e.g., prefixes/suffixes), use schema-based isolation instead, or run each app in a separate PostgreSQL schema.

**Alternative pattern:** For apps that already use schema-per-tenant, you could combine with a suffix:
```sql
-- Example: customer schemas with memory suffix
CREATE SCHEMA customer_123_memories;
```
```python
with build_store("postgresql://...", schema="customer_123_memories") as store:
    store.setup()
```

## License

MIT
