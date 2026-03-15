"""
PostgreSQL backend using LangGraph's PostgresStore with pgvector.
"""

import os
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from typing import TYPE_CHECKING, Any

from langgraph.store.postgres import PostgresStore

from memento_ai.backends.base import BaseStore, StoreItem

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIMS = 1536


def _add_schema_to_conn_string(conn_str: str, schema: str) -> str:
    """
    Add search_path option to a PostgreSQL connection string.

    Args:
        conn_str: Original connection string.
        schema: PostgreSQL schema name.

    Returns:
        Connection string with search_path set.

    Example:
        >>> _add_schema_to_conn_string("postgresql://user:pass@host/db", "customer_123")
        'postgresql://user:pass@host/db?options=-c%20search_path%3Dcustomer_123'
    """
    parsed = urlparse(conn_str)
    query_params = parse_qs(parsed.query)

    # Build the search_path option
    search_path_option = f"-c search_path={schema}"

    # Merge with existing options if any
    if "options" in query_params:
        existing = query_params["options"][0]
        query_params["options"] = [f"{existing} {search_path_option}"]
    else:
        query_params["options"] = [search_path_option]

    # Rebuild the URL
    new_query = urlencode(query_params, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


class PostgresBackend(BaseStore):
    """
    PostgreSQL backend with pgvector for semantic search.

    Uses LangGraph's PostgresStore under the hood.

    Supports schema-based isolation for multi-tenant deployments via the
    `schema` parameter, which sets the PostgreSQL search_path.
    """

    def __init__(
        self,
        conn_str: str,
        embeddings: "Embeddings | None" = None,
        embed_model: str = DEFAULT_EMBED_MODEL,
        dims: int = DEFAULT_EMBED_DIMS,
        embed_fields: list[str] | None = None,
        schema: str | None = None,
    ):
        """
        Initialize PostgreSQL backend.

        Args:
            conn_str: PostgreSQL connection string.
            embeddings: LangChain Embeddings instance. If None, uses OpenAIEmbeddings.
            embed_model: OpenAI embedding model name (only used if embeddings is None).
            dims: Embedding dimensions.
            embed_fields: Fields to embed (default: ["text"]).
            schema: PostgreSQL schema name for isolation (sets search_path).

        Note:
            When using `schema`, the schema must already exist in the database.
            Tables will be created in that schema when `setup()` is called.
        """
        # Apply schema to connection string if provided
        if schema:
            conn_str = _add_schema_to_conn_string(conn_str, schema)

        self._conn_str = conn_str
        self._embed_model = embed_model
        self._embeddings: Embeddings | None = embeddings
        self._dims = dims
        self._embed_fields = embed_fields or ["text"]
        self._schema = schema
        self._store: PostgresStore | None = None
        self._context = None

    def _get_embeddings(self) -> "Embeddings":
        """Get embeddings client, lazy-loading OpenAI if not provided."""
        if self._embeddings is None:
            from langchain_openai import OpenAIEmbeddings
            self._embeddings = OpenAIEmbeddings(model=self._embed_model)
        return self._embeddings

    def _ensure_connected(self) -> PostgresStore:
        """Ensure we have an active connection."""
        if self._store is None:
            self._context = PostgresStore.from_conn_string(
                self._conn_str,
                index={
                    "dims": self._dims,
                    "embed": self._get_embeddings(),
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
    embeddings: "Embeddings | None" = None,
    embed_model: str = DEFAULT_EMBED_MODEL,
    dims: int = DEFAULT_EMBED_DIMS,
    embed_fields: list[str] | None = None,
    schema: str | None = None,
) -> PostgresBackend:
    """
    Create a PostgreSQL backend.

    Args:
        conn_str: Connection string. Falls back to DATABASE_URL env var.
        embeddings: LangChain Embeddings instance. If None, uses OpenAIEmbeddings.
        embed_model: OpenAI embedding model (only used if embeddings is None).
        dims: Embedding dimensions.
        embed_fields: Fields to embed.
        schema: PostgreSQL schema name for tenant isolation (sets search_path).

    Returns:
        PostgresBackend instance.

    Examples:
        # Default (OpenAI)
        backend = build_postgres_backend("postgresql://...")

        # With AWS Bedrock
        from langchain_aws import BedrockEmbeddings
        backend = build_postgres_backend("postgresql://...", embeddings=BedrockEmbeddings())

        # With AI Gateway (OpenAI-compatible)
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(base_url="https://gateway.ai.cloudflare.com/v1/...")
        backend = build_postgres_backend("postgresql://...", embeddings=embeddings)

        # With schema-based tenant isolation
        backend = build_postgres_backend("postgresql://...", schema="customer_123")
    """
    conn_str = conn_str or os.environ.get("DATABASE_URL")
    if not conn_str:
        raise ValueError("Connection string required. Pass conn_str or set DATABASE_URL.")

    return PostgresBackend(
        conn_str=conn_str,
        embeddings=embeddings,
        embed_model=embed_model,
        dims=dims,
        embed_fields=embed_fields,
        schema=schema,
    )
