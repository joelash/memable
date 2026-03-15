# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all tests
pytest

# Run unit tests only (no external deps)
pytest tests/unit -m unit

# Run integration tests (requires Docker with pgvector or DATABASE_URL)
pytest tests/integration -m integration

# Run a single test file
pytest tests/unit/test_schema.py -v

# Run performance tests (requires OPENAI_API_KEY)
pytest tests/performance -v -s

# Lint and format
ruff check src tests
ruff format src tests

# Type check
mypy src
```

## Environment Variables

- `OPENAI_API_KEY` - Required for embeddings
- `DATABASE_URL` - PostgreSQL connection string (for integration tests and production)
- `MEMORY_DB_PATH` - SQLite path when using SQLite backend

## Architecture Overview

memento-ai is a semantic memory library for LangGraph agents with three storage backends.

### Core Components

**Schema (`src/memento_ai/schema.py`)**
- `Memory` - Main memory object with durability tiers (core/situational/episodic), temporal validity, version chains, and MemoryType categorization
- `MemoryCreate`/`MemoryUpdate`/`MemoryQuery` - Input/query types
- Version chains track supersedes/superseded_by for contradiction handling

**Store (`src/memento_ai/store.py`)**
- `SemanticMemoryStore` - High-level API wrapping backend stores
- Factory functions: `build_store()` (auto-detect), `build_postgres_store()`, `build_sqlite_store()`, `build_duckdb_store()`
- All stores use context managers for connection lifecycle

**Backends (`src/memento_ai/backends/`)**
- `BaseStore` - Abstract protocol defining put/get/delete/search operations
- `PostgresStore` - Production backend using pgvector
- `SQLiteStore` - Dev/testing backend using sqlite-vec
- `DuckDBStore` - Analytics backend with native vector similarity
- Factory in `factory.py` auto-selects backend from URL scheme

**LangGraph Integration**
- `nodes.py` - Pre-built nodes: `retrieve_memories_node`, `store_memories_node`, `consolidate_memories_node`
- `graph.py` - `build_memory_graph()` creates a ready-to-use graph with retrieve -> LLM -> store flow

**Supporting Modules**
- `extraction.py` - LLM-based memory extraction from conversations
- `contradiction.py` - Detect and resolve conflicting memories via version chains
- `consolidation.py` - Decay, summarize, and prune old memories
- `retrieval.py` - Multi-scope retrieval with priority merging

### Key Patterns

- Namespaces are tuples: `("org_id", "user_id", "scope")` for hierarchical scoping
- Version chains preserve history: old memories get `superseded_by`, new ones get `supersedes`
- Temporal validity via `valid_from`/`valid_until` with automatic filtering
- All backends implement the same `BaseStore` interface for swappable storage

### Testing

Integration tests use testcontainers with `pgvector/pgvector:pg16` image. Pull first:
```bash
docker pull pgvector/pgvector:pg16
```
