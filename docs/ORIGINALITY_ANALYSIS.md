# Originality Analysis: memento-ai vs Similar OSS Projects

**Date:** 2026-02-09  
**Purpose:** Document architectural differences and originality of memento-ai compared to existing open-source AI memory libraries.

## Executive Summary

memento-ai is an **original implementation** designed specifically for LangGraph integration. While it solves similar problems as other memory libraries (mem0, memary, letta), its architecture, data model, and implementation are distinct. Key differentiators:

1. **LangGraph-native design** with pre-built nodes and graphs
2. **Version chains** for contradiction handling (audit trail, not soft delete)
3. **Temporal validity** with explicit valid_from/valid_until fields
4. **Durability tiers** (core/situational/episodic) with automatic classification
5. **Multi-backend abstraction** (Postgres/SQLite/DuckDB) via unified interface

---

## Compared Projects

| Project | GitHub | Stars | Focus |
|---------|--------|-------|-------|
| mem0 | mem0ai/mem0 | ~25k | General-purpose memory layer |
| memary | kingjulio8238/memary | ~2k | Entity extraction + knowledge graphs |
| letta | letta-ai/letta | ~15k | Context window management (formerly MemGPT) |
| **memento-ai** | joelash/memento-ai | new | LangGraph-native semantic memory |

---

## Architectural Comparison

### mem0

**Pattern:** Monolithic class with factory patterns for pluggable backends.

```python
# mem0 pattern
from mem0 import Memory
m = Memory()
m.add(messages, user_id="user123")
results = m.search(query, user_id="user123")
```

- Heavy use of factories: `VectorStoreFactory`, `LlmFactory`, `EmbedderFactory`, `GraphStoreFactory`
- Session-based scoping: `user_id`, `agent_id`, `run_id`
- Single `Memory` class handles everything
- Optional graph store integration
- Telemetry built-in

### memary

**Pattern:** Entity-centric memory with knowledge graphs.

```python
# memary pattern
from memary.memory import MemoryStream
stream = MemoryStream(file_name="memory.json")
stream.add_memory(entities)  # Adds entity objects, not facts
```

- Focus on **entity extraction**, not fact storage
- `MemoryItem` = entity + timestamp (very different from fact-based memory)
- File-based persistence (JSON)
- Knowledge graph construction
- Much simpler, narrower scope

### letta (MemGPT)

**Pattern:** Context window management with core/archival memory split.

```python
# letta pattern - Block-based core memory
from letta.schemas.memory import Memory, Block
memory = Memory(blocks=[
    Block(label="persona", value="..."),
    Block(label="human", value="...")
])
```

- **Core memory**: In-context blocks with character limits
- **Archival memory**: Long-term storage, retrieved as needed
- **Recall memory**: Conversation history
- Focus on **context window optimization**
- Memory edited via tool calls to the agent
- Summarization for compaction

### memento-ai

**Pattern:** LangGraph-native store with durability tiers and version chains.

```python
# memento-ai pattern
from memento_ai import build_store, MemoryCreate, Durability

with build_store("postgresql://...") as store:
    store.add(namespace, MemoryCreate(
        text="User prefers dark mode",
        durability=Durability.CORE,
        confidence=0.9,
    ))
    memories = store.search(namespace, "preferences")
```

- **Namespace-based scoping** (tuple-based hierarchy)
- **Durability tiers**: core (permanent), situational (temporary), episodic (events)
- **Version chains**: Updates create new versions, old versions linked via `supersedes`/`superseded_by`
- **Temporal validity**: `valid_from`, `valid_until` fields with automatic filtering
- **LangGraph nodes**: `retrieve_memories_node`, `store_memories_node`, `consolidate_memories_node`
- **Multi-backend**: Single interface for Postgres, SQLite, DuckDB

---

## Data Model Comparison

### Memory Object Structure

**mem0:**
```python
# Flat structure with metadata
{
    "id": "uuid",
    "memory": "User likes pizza",
    "user_id": "user123",
    "metadata": {...},
    "created_at": "...",
    "updated_at": "..."
}
```

**memary:**
```python
# Entity-centric
@dataclass
class MemoryItem:
    entity: str
    date: datetime
```

**letta:**
```python
# Block-based
class Block(BaseModel):
    label: str  # "persona", "human", etc.
    value: str  # The actual content
    limit: int  # Character limit
```

**memento-ai:**
```python
class Memory(BaseModel):
    id: UUID
    text: str
    durability: Durability  # CORE, SITUATIONAL, EPISODIC
    confidence: float
    source: MemorySource   # EXPLICIT, INFERRED, SYSTEM
    valid_from: datetime
    valid_until: datetime | None
    supersedes: UUID | None      # Version chain
    superseded_by: UUID | None   # Version chain
    superseded_at: datetime | None
    tags: list[str]
    metadata: dict
```

**Key differences:**
- memento-ai has **durability classification** (unique)
- memento-ai has **version chains** for contradiction handling (unique)
- memento-ai has **temporal validity** fields (unique)
- memento-ai has **confidence scores** with source tracking

---

## Extraction Prompt Comparison

### mem0 FACT_RETRIEVAL_PROMPT

```
You are a Personal Information Organizer...
Types of Information to Remember:
1. Store Personal Preferences...
2. Maintain Important Personal Details...
[7 categories listed]

Return the facts and preferences in a json format...
{{"facts": ["fact1", "fact2"]}}
```

- Returns flat list of fact strings
- No durability classification
- No confidence scoring
- No temporal estimation

### memento-ai EXTRACTION_SYSTEM_PROMPT

```
You are a memory extraction system...

For each fact, classify its durability:
- "core": Stable facts that rarely change
- "situational": Temporary context with a natural end
- "episodic": Things that happened or were discussed

Return a JSON object with this structure:
{
  "facts": [
    {
      "text": "...",
      "durability": "core",
      "confidence": 0.95,
      "valid_days": null,
      "category": "...",
      "reasoning": "..."
    }
  ]
}
```

- Returns **structured objects** with metadata
- **Durability classification** (core/situational/episodic)
- **Confidence scoring** (0-1)
- **Temporal estimation** (valid_days for situational facts)
- **Reasoning** for debugging

**Conclusion:** Prompts are substantially different in structure, output format, and capabilities.

---

## Storage Backend Comparison

| Feature | mem0 | memary | letta | memento-ai |
|---------|------|--------|-------|-----------|
| Postgres | ✅ (via vector stores) | ❌ | ✅ | ✅ (pgvector) |
| SQLite | ✅ | ❌ | ✅ | ✅ (sqlite-vec) |
| DuckDB | ❌ | ❌ | ❌ | ✅ |
| MotherDuck | ❌ | ❌ | ❌ | ✅ |
| In-memory | ❌ | ❌ | ❌ | ✅ |
| Pinecone | ✅ | ❌ | ❌ | ❌ |
| Qdrant | ✅ | ❌ | ✅ | ❌ |
| Chroma | ✅ | ✅ | ✅ | ❌ |

**memento-ai's backend pattern:**
```python
# Unified interface via URL scheme detection
with build_store("postgresql://...") as store: ...
with build_store("sqlite:///./dev.db") as store: ...
with build_store("duckdb:///./data.duckdb") as store: ...
with build_store("md:my_database") as store: ...  # MotherDuck
with build_store(":memory:") as store: ...  # Testing
```

---

## Unique memento-ai Features

### 1. Version Chains (Contradiction Handling)

```python
# When a fact is updated, old version is preserved
old_memory = store.get(namespace, memory_id)
new_memory = store.update(namespace, memory_id, MemoryUpdate(text="New fact"))

# Version chain linked:
# old_memory.superseded_by → new_memory.id
# new_memory.supersedes → old_memory.id

# Full history available:
history = store.get_version_history(namespace, memory_id)
```

**No other compared project has this pattern.** mem0 tracks history separately, letta uses overwrite, memary has no versioning.

### 2. Temporal Validity

```python
memory = MemoryCreate(
    text="User visiting Ohio",
    durability=Durability.SITUATIONAL,
    valid_until=datetime(2026, 2, 15),  # Auto-expires
)

# Search automatically filters expired memories
results = store.search(namespace, query)  # Only returns valid memories
```

### 3. LangGraph Integration

```python
from memento_ai.graph import build_memory_graph

# Pre-built graph with memory nodes
graph = build_memory_graph()
compiled = graph.compile(store=store.raw_store)

result = compiled.invoke(
    {"messages": [{"role": "user", "content": "Hi, I'm Joel"}]},
    config={"configurable": {"user_id": "user_123"}}
)
```

**No other compared project provides LangGraph-native integration.**

---

## Code Similarity Analysis

### Method: Manual inspection of core patterns

| Component | Similar to mem0? | Similar to memary? | Similar to letta? |
|-----------|------------------|--------------------|--------------------|
| Memory model | ❌ Different fields | ❌ Entity vs fact | ❌ Block vs fact |
| Extraction prompt | ❌ Different structure | N/A (no LLM extraction) | N/A (tool-based) |
| Storage interface | ❌ Different pattern | ❌ File-based | ❌ Different ORM |
| Search/retrieval | Similar concept | ❌ Entity-based | ❌ Context-based |
| Version handling | ❌ Unique chain pattern | ❌ None | ❌ Overwrite |
| Namespace pattern | Similar concept | ❌ None | ❌ Agent-scoped |

### Shared Concepts (Industry Standard)

These patterns are common across all memory libraries and represent industry-standard approaches, not copied code:

1. **Vector embeddings for semantic search** - Standard practice
2. **User/namespace scoping** - Standard practice
3. **LLM-based extraction** - Standard practice
4. **CRUD operations** - Standard practice

---

## Conclusion

**memento-ai is an original implementation** with several unique features:

1. **Durability tiers** with automatic classification
2. **Version chains** for audit trails
3. **Temporal validity** with auto-expiration
4. **LangGraph-native** design
5. **Multi-backend** via URL scheme detection

While it solves similar problems as mem0/memary/letta, its architecture, data model, and implementation are distinct. The shared concepts (embeddings, namespaces, LLM extraction) are industry-standard patterns, not copied code.

**Recommendation:** This analysis provides a defensible paper trail for originality. Consider adding this document to the repository for reference.
