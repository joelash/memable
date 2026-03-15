"""
memento-ai: Reusable semantic memory for LangGraph agents.

Supports multiple backends:
- PostgreSQL with pgvector (production)
- SQLite with sqlite-vec (development/testing)
"""

from memento_ai.schema import (
    Durability,
    Memory,
    MemoryCreate,
    MemoryQuery,
    MemorySource,
    MemoryType,
    MemoryUpdate,
)
from memento_ai.store import (
    SemanticMemoryStore,
    build_duckdb_store,
    build_postgres_store,
    build_sqlite_store,
    build_store,
)

__version__ = "0.2.0"

__all__ = [
    # Store factories
    "build_store",           # Auto-detect backend from URL
    "build_postgres_store",  # PostgreSQL backend
    "build_sqlite_store",    # SQLite backend
    "build_duckdb_store",    # DuckDB / MotherDuck backend
    # Store class
    "SemanticMemoryStore",
    # Schema
    "Memory",
    "MemoryCreate",
    "MemoryUpdate",
    "MemoryQuery",
    "Durability",
    "MemorySource",
    "MemoryType",
]
