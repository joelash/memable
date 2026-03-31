"""
memento-ai: Reusable semantic memory for LangGraph agents.

Supports multiple backends:
- PostgreSQL with pgvector (production)
- SQLite with sqlite-vec (development/testing)
"""

from memable.schema import (
    Durability,
    Memory,
    MemoryCreate,
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
from memable.embeddings import (
    create_embeddings,
    is_ollama_available,
    has_ollama_model,
    OllamaEmbeddings,
)

__version__ = "0.1.5"

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
    "MemoryQuery",
    "Durability",
    "MemorySource",
    "MemoryType",
]
