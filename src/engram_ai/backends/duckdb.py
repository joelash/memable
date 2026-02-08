"""
DuckDB backend with vector similarity search.

Supports both local DuckDB files and MotherDuck (cloud).
"""

import json
import os
from pathlib import Path
from typing import Any

from langchain_openai import OpenAIEmbeddings

from engram_ai.backends.base import BaseStore, StoreItem


DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIMS = 1536


def _serialize_namespace(namespace: tuple[str, ...]) -> str:
    """Convert namespace tuple to string for storage."""
    return "/".join(namespace)


class DuckDBBackend(BaseStore):
    """
    DuckDB backend with vector similarity search.
    
    Supports:
    - Local DuckDB files
    - MotherDuck cloud (md: or motherduck: URLs)
    - In-memory databases
    
    Uses DuckDB's built-in array functions for vector operations.
    """
    
    def __init__(
        self,
        db_path: str | Path,
        embed_model: str = DEFAULT_EMBED_MODEL,
        dims: int = DEFAULT_EMBED_DIMS,
        embed_fields: list[str] | None = None,
        motherduck_token: str | None = None,
    ):
        """
        Initialize DuckDB backend.
        
        Args:
            db_path: Path to DuckDB file, ":memory:", or MotherDuck connection string.
            embed_model: OpenAI embedding model name.
            dims: Embedding dimensions.
            embed_fields: Fields to embed (default: ["text"]).
            motherduck_token: MotherDuck API token (can also use MOTHERDUCK_TOKEN env).
        """
        self._db_path = str(db_path)
        self._embeddings = OpenAIEmbeddings(model=embed_model)
        self._dims = dims
        self._embed_fields = embed_fields or ["text"]
        self._motherduck_token = motherduck_token or os.environ.get("MOTHERDUCK_TOKEN")
        self._conn = None
    
    def _ensure_connected(self):
        """Ensure we have an active connection."""
        if self._conn is None:
            try:
                import duckdb
            except ImportError:
                raise ImportError(
                    "DuckDB not installed. Install with: pip install duckdb"
                )
            
            # Handle MotherDuck connections
            if self._db_path.startswith(("md:", "motherduck:")):
                if self._motherduck_token:
                    # Token can be passed via connection string or config
                    config = {"motherduck_token": self._motherduck_token}
                    self._conn = duckdb.connect(self._db_path, config=config)
                else:
                    self._conn = duckdb.connect(self._db_path)
            else:
                self._conn = duckdb.connect(self._db_path)
        
        return self._conn
    
    def setup(self) -> None:
        """Create tables and indexes."""
        conn = self._ensure_connected()
        
        # Main data table with embedding as array
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS memories (
                namespace VARCHAR NOT NULL,
                key VARCHAR NOT NULL,
                value JSON NOT NULL,
                embedding DOUBLE[{self._dims}],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (namespace, key)
            )
        """)
        
        # Index for namespace queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_namespace 
            ON memories(namespace)
        """)
    
    def _get_embedding(self, value: dict[str, Any]) -> list[float]:
        """Generate embedding for a value."""
        texts = []
        for field in self._embed_fields:
            if field in value and value[field]:
                texts.append(str(value[field]))
        text = " ".join(texts)
        
        if not text:
            return [0.0] * self._dims
        
        embedding = self._embeddings.embed_query(text)
        return embedding
    
    def put(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Store a value with its embedding."""
        conn = self._ensure_connected()
        ns_str = _serialize_namespace(namespace)
        value_json = json.dumps(value)
        embedding = self._get_embedding(value)
        
        # Upsert using INSERT OR REPLACE
        conn.execute("""
            INSERT OR REPLACE INTO memories (namespace, key, value, embedding)
            VALUES (?, ?, ?, ?)
        """, [ns_str, key, value_json, embedding])
    
    def get(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> StoreItem | None:
        """Retrieve a value by key."""
        conn = self._ensure_connected()
        ns_str = _serialize_namespace(namespace)
        
        result = conn.execute(
            "SELECT key, value FROM memories WHERE namespace = ? AND key = ?",
            [ns_str, key]
        ).fetchone()
        
        if result is None:
            return None
        
        return StoreItem(
            key=result[0],
            value=json.loads(result[1]),
            namespace=namespace,
        )
    
    def delete(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> None:
        """Delete a value."""
        conn = self._ensure_connected()
        ns_str = _serialize_namespace(namespace)
        
        conn.execute(
            "DELETE FROM memories WHERE namespace = ? AND key = ?",
            [ns_str, key]
        )
    
    def search(
        self,
        namespace: tuple[str, ...],
        query: str | None,
        limit: int = 10,
    ) -> list[StoreItem]:
        """Search with optional vector similarity."""
        conn = self._ensure_connected()
        ns_str = _serialize_namespace(namespace)
        
        if query is None:
            # List all in namespace
            results = conn.execute(
                "SELECT key, value FROM memories WHERE namespace = ? LIMIT ?",
                [ns_str, limit]
            ).fetchall()
            return [
                StoreItem(
                    key=row[0],
                    value=json.loads(row[1]),
                    namespace=namespace,
                )
                for row in results
            ]
        
        # Semantic search using cosine similarity
        query_embedding = self._embeddings.embed_query(query)
        
        # DuckDB cosine similarity using list_cosine_similarity
        results = conn.execute("""
            SELECT 
                key, 
                value,
                list_cosine_similarity(embedding, ?::DOUBLE[]) as similarity
            FROM memories 
            WHERE namespace = ?
            ORDER BY similarity DESC
            LIMIT ?
        """, [query_embedding, ns_str, limit]).fetchall()
        
        return [
            StoreItem(
                key=row[0],
                value=json.loads(row[1]),
                namespace=namespace,
                score=row[2] if row[2] is not None else 0.0,
            )
            for row in results
        ]
    
    def close(self) -> None:
        """Close the connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def build_duckdb_backend(
    db_path: str | Path | None = None,
    embed_model: str = DEFAULT_EMBED_MODEL,
    dims: int = DEFAULT_EMBED_DIMS,
    embed_fields: list[str] | None = None,
    motherduck_token: str | None = None,
) -> DuckDBBackend:
    """
    Create a DuckDB backend.
    
    Args:
        db_path: Path to database file, ":memory:", or MotherDuck URL.
                 Falls back to DUCKDB_PATH env var or "engram.duckdb".
        embed_model: OpenAI embedding model.
        dims: Embedding dimensions.
        embed_fields: Fields to embed.
        motherduck_token: MotherDuck API token.
        
    Returns:
        DuckDBBackend instance.
        
    Examples:
        # Local file
        backend = build_duckdb_backend("./data.duckdb")
        
        # In-memory
        backend = build_duckdb_backend(":memory:")
        
        # MotherDuck cloud
        backend = build_duckdb_backend("md:my_database")
    """
    if db_path is None:
        db_path = os.environ.get("DUCKDB_PATH", "engram.duckdb")
    
    return DuckDBBackend(
        db_path=db_path,
        embed_model=embed_model,
        dims=dims,
        embed_fields=embed_fields,
        motherduck_token=motherduck_token,
    )
