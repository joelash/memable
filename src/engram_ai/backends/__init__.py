"""
Backend storage implementations for engram-ai.

Supported backends:
- PostgreSQL (via LangGraph PostgresStore + pgvector)
- SQLite (via sqlite-vec for vector search)
- DuckDB (native vector similarity)
- MotherDuck (cloud DuckDB)
"""

from engram_ai.backends.base import BaseStore, StoreItem
from engram_ai.backends.factory import build_store

__all__ = ["BaseStore", "StoreItem", "build_store"]
