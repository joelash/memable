"""
Factory function for creating storage backends.

Picks the appropriate backend based on URL scheme.
"""

import os
from urllib.parse import urlparse

from engram_ai.backends.base import BaseStore
from engram_ai.backends.duckdb import DuckDBBackend
from engram_ai.backends.postgres import DEFAULT_EMBED_DIMS, DEFAULT_EMBED_MODEL, PostgresBackend
from engram_ai.backends.sqlite import SQLiteBackend


def build_store(
    url: str | None = None,
    embed_model: str = DEFAULT_EMBED_MODEL,
    dims: int = DEFAULT_EMBED_DIMS,
    embed_fields: list[str] | None = None,
) -> BaseStore:
    """
    Create a storage backend based on URL scheme.

    Supported URL schemes:
    - postgresql://, postgres:// → PostgreSQL with pgvector
    - sqlite://, sqlite:/// → SQLite with sqlite-vec
    - duckdb:// → DuckDB (local file)
    - md:, motherduck: → MotherDuck (cloud DuckDB)
    - file:// → SQLite (local file path)
    - :memory: → SQLite in-memory (for testing)

    Falls back to DATABASE_URL or MEMORY_DATABASE_URL environment variables.

    Args:
        url: Database URL. Scheme determines backend type.
        embed_model: OpenAI embedding model name.
        dims: Embedding dimensions.
        embed_fields: Fields to embed (default: ["text"]).

    Returns:
        Configured BaseStore instance.

    Examples:
        # PostgreSQL (production)
        store = build_store("postgresql://user:pass@host:5432/db")

        # SQLite file (development)
        store = build_store("sqlite:///path/to/engram.db")
        store = build_store("sqlite:///./local.db")  # relative path

        # SQLite in-memory (testing)
        store = build_store(":memory:")

        # DuckDB local
        store = build_store("duckdb:///./analytics.duckdb")

        # MotherDuck cloud
        store = build_store("md:my_database")
        store = build_store("motherduck:my_database")

        # From environment
        store = build_store()  # Uses DATABASE_URL or MEMORY_DATABASE_URL
    """
    # Resolve URL from environment if not provided
    if url is None:
        url = os.environ.get("MEMORY_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not url:
            raise ValueError(
                "Database URL required. Pass url parameter or set "
                "DATABASE_URL / MEMORY_DATABASE_URL environment variable."
            )

    # Handle special cases
    if url == ":memory:":
        return SQLiteBackend(
            db_path=":memory:",
            embed_model=embed_model,
            dims=dims,
            embed_fields=embed_fields,
        )

    # Parse URL
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme in ("postgresql", "postgres"):
        return PostgresBackend(
            conn_str=url,
            embed_model=embed_model,
            dims=dims,
            embed_fields=embed_fields,
        )

    elif scheme == "sqlite":
        # sqlite:///path/to/file.db or sqlite:///./relative.db
        # The path after sqlite:/// is parsed.path
        db_path = parsed.path
        if db_path.startswith("/"):
            # sqlite:////absolute/path → /absolute/path
            # sqlite:///./relative → ./relative
            if db_path.startswith("//"):
                db_path = db_path[1:]  # Remove one leading slash
            elif not db_path.startswith("/."):
                db_path = db_path[1:]  # Remove leading slash for absolute paths

        return SQLiteBackend(
            db_path=db_path or "engram.db",
            embed_model=embed_model,
            dims=dims,
            embed_fields=embed_fields,
        )

    elif scheme == "file":
        # file:///path/to/file.db
        db_path = parsed.path
        return SQLiteBackend(
            db_path=db_path,
            embed_model=embed_model,
            dims=dims,
            embed_fields=embed_fields,
        )

    elif scheme == "duckdb":
        # duckdb:///path/to/file.duckdb
        db_path = parsed.path
        if db_path.startswith("/"):
            if db_path.startswith("//"):
                db_path = db_path[1:]
            elif not db_path.startswith("/."):
                db_path = db_path[1:]

        return DuckDBBackend(
            db_path=db_path or "engram.duckdb",
            embed_model=embed_model,
            dims=dims,
            embed_fields=embed_fields,
        )

    elif scheme in ("md", "motherduck"):
        # md:database_name or motherduck:database_name
        # Pass the full URL to DuckDB which handles MotherDuck natively
        return DuckDBBackend(
            db_path=url,
            embed_model=embed_model,
            dims=dims,
            embed_fields=embed_fields,
        )

    elif scheme == "":
        # Assume it's a file path
        # Check extension to determine backend
        if url.endswith(".duckdb") or url.endswith(".ddb"):
            return DuckDBBackend(
                db_path=url,
                embed_model=embed_model,
                dims=dims,
                embed_fields=embed_fields,
            )
        else:
            # Default to SQLite
            return SQLiteBackend(
                db_path=url,
                embed_model=embed_model,
                dims=dims,
                embed_fields=embed_fields,
            )

    else:
        raise ValueError(
            f"Unsupported URL scheme: {scheme}. "
            f"Supported: postgresql, postgres, sqlite, duckdb, md, motherduck, "
            f"file, or bare file path."
        )
