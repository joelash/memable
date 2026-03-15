"""
Backend storage implementations for memento-ai.

Supported backends:
- PostgreSQL (via LangGraph PostgresStore + pgvector)
- SQLite (via sqlite-vec for vector search)
- DuckDB (native vector similarity)
- MotherDuck (cloud DuckDB)
"""

from memable.backends.base import BaseStore, StoreItem
from memable.backends.factory import build_store

__all__ = ["BaseStore", "StoreItem", "build_store"]
