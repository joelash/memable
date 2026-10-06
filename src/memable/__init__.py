"""
memento-ai: Reusable semantic memory for LangGraph agents.

Supports multiple backends:
- PostgreSQL with pgvector (production)
- SQLite with sqlite-vec (development/testing)
"""

from memable.embeddings import (
    OllamaEmbeddings,
    create_embeddings,
    has_ollama_model,
    is_ollama_available,
)
from memable.schema import (
    Durability,
    Memory,
    MemoryCreate,
    MemoryPatch,
    MemoryQuery,
    MemorySource,
    MemoryType,
    MemoryUpdate,
)
from memable.store import (
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
    # Embeddings
    "create_embeddings",     # Auto-detect Ollama vs OpenAI
    "is_ollama_available",   # Check if Ollama is running
    "has_ollama_model",      # Check if embedding model installed
    "OllamaEmbeddings",      # LangChain-compatible Ollama embeddings
    # Schema
    "Memory",
    "MemoryCreate",
    "MemoryUpdate",
    "MemoryPatch",
    "MemoryQuery",
    "Durability",
    "MemorySource",
    "MemoryType",
]
