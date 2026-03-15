"""
Backend storage implementations for memento-ai.

Supported backends:
- PostgreSQL (via LangGraph PostgresStore + pgvector)
- SQLite (via sqlite-vec for vector search)
- DuckDB (native vector similarity)
- MotherDuck (cloud DuckDB)
"""

from memento_ai.backends.base import BaseStore, StoreItem
from memento_ai.backends.factory import build_store

__all__ = ["BaseStore", "StoreItem", "build_store"]
