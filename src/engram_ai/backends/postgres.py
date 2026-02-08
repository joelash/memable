"""
PostgreSQL backend using LangGraph's PostgresStore with pgvector.
"""

import os
from typing import Any

from langchain_openai import OpenAIEmbeddings
from langgraph.store.postgres import PostgresStore

from engram_ai.backends.base import BaseStore, StoreItem

DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIMS = 1536


class PostgresBackend(BaseStore):
    """
    PostgreSQL backend with pgvector for semantic search.

    Uses LangGraph's PostgresStore under the hood.
    """

    def __init__(
        self,
        conn_str: str,
        embed_model: str = DEFAULT_EMBED_MODEL,
        dims: int = DEFAULT_EMBED_DIMS,
        embed_fields: list[str] | None = None,
    ):
        """
        Initialize PostgreSQL backend.

        Args:
            conn_str: PostgreSQL connection string.
            embed_model: OpenAI embedding model name.
            dims: Embedding dimensions.
            embed_fields: Fields to embed (default: ["text"]).
        """
        self._conn_str = conn_str
        self._embeddings = OpenAIEmbeddings(model=embed_model)
        self._dims = dims
        self._embed_fields = embed_fields or ["text"]
        self._store: PostgresStore | None = None
        self._context = None

    def _ensure_connected(self) -> PostgresStore:
        """Ensure we have an active connection."""
        if self._store is None:
            self._context = PostgresStore.from_conn_string(
                self._conn_str,
                index={
                    "dims": self._dims,
                    "embed": self._embeddings,
                    "fields": self._embed_fields,
                },
            )
            self._store = self._context.__enter__()
        return self._store

    def setup(self) -> None:
        """Create tables and indexes."""
        store = self._ensure_connected()
        store.setup()

    def put(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Store a value."""
        store = self._ensure_connected()
        store.put(namespace=namespace, key=key, value=value)

    def get(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> StoreItem | None:
        """Retrieve a value by key."""
        store = self._ensure_connected()
        result = store.get(namespace=namespace, key=key)
        if result is None:
            return None
        return StoreItem(
            key=result.key,
            value=result.value,
            namespace=namespace,
        )

    def delete(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> None:
        """Delete a value."""
        store = self._ensure_connected()
        store.delete(namespace=namespace, key=key)

    def search(
        self,
        namespace: tuple[str, ...],
        query: str | None,
        limit: int = 10,
    ) -> list[StoreItem]:
        """Semantic search using pgvector."""
        store = self._ensure_connected()
        results = store.search(namespace, query=query, limit=limit)
        return [
            StoreItem(
                key=r.key,
                value=r.value,
                namespace=namespace,
                score=getattr(r, 'score', None),
            )
            for r in results
        ]

    def close(self) -> None:
        """Close the connection."""
        if self._context is not None:
            self._context.__exit__(None, None, None)
            self._store = None
            self._context = None


def build_postgres_backend(
    conn_str: str | None = None,
    embed_model: str = DEFAULT_EMBED_MODEL,
    dims: int = DEFAULT_EMBED_DIMS,
    embed_fields: list[str] | None = None,
) -> PostgresBackend:
    """
    Create a PostgreSQL backend.

    Args:
        conn_str: Connection string. Falls back to DATABASE_URL env var.
        embed_model: OpenAI embedding model.
        dims: Embedding dimensions.
        embed_fields: Fields to embed.

    Returns:
        PostgresBackend instance.
    """
    conn_str = conn_str or os.environ.get("DATABASE_URL")
    if not conn_str:
        raise ValueError("Connection string required. Pass conn_str or set DATABASE_URL.")

    return PostgresBackend(
        conn_str=conn_str,
        embed_model=embed_model,
        dims=dims,
        embed_fields=embed_fields,
    )
