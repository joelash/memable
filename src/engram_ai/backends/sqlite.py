"""
SQLite backend using sqlite-vec for vector search.

Great for local development and testing without external dependencies.
"""

import json
import os
import sqlite3
import struct
from pathlib import Path
from typing import Any

from langchain_openai import OpenAIEmbeddings

from engram_ai.backends.base import BaseStore, StoreItem

DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIMS = 1536


def _serialize_f32(vector: list[float]) -> bytes:
    """Serialize a float32 vector for sqlite-vec."""
    return struct.pack(f"{len(vector)}f", *vector)


def _serialize_namespace(namespace: tuple[str, ...]) -> str:
    """Convert namespace tuple to string for storage."""
    return "/".join(namespace)


def _parse_namespace(namespace_str: str) -> tuple[str, ...]:
    """Convert namespace string back to tuple."""
    return tuple(namespace_str.split("/"))


class SQLiteBackend(BaseStore):
    """
    SQLite backend with sqlite-vec for semantic search.

    Uses a local file for storage - perfect for development and testing.
    """

    def __init__(
        self,
        db_path: str | Path,
        embed_model: str = DEFAULT_EMBED_MODEL,
        dims: int = DEFAULT_EMBED_DIMS,
        embed_fields: list[str] | None = None,
    ):
        """
        Initialize SQLite backend.

        Args:
            db_path: Path to SQLite database file. Use ":memory:" for in-memory.
            embed_model: OpenAI embedding model name.
            dims: Embedding dimensions.
            embed_fields: Fields to embed (default: ["text"]).
        """
        self._db_path = str(db_path)
        self._embeddings = OpenAIEmbeddings(model=embed_model)
        self._dims = dims
        self._embed_fields = embed_fields or ["text"]
        self._conn: sqlite3.Connection | None = None
        self._vec_available = False

    def _ensure_connected(self) -> sqlite3.Connection:
        """Ensure we have an active connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row

            # Try to load sqlite-vec extension
            try:
                self._conn.enable_load_extension(True)
                # Try common locations for sqlite-vec
                for ext_name in ["vec0", "sqlite_vec", "vec"]:
                    try:
                        self._conn.load_extension(ext_name)
                        self._vec_available = True
                        break
                    except sqlite3.OperationalError:
                        continue
                self._conn.enable_load_extension(False)
            except (sqlite3.OperationalError, AttributeError):
                # Extension loading not supported or vec not available
                pass

            if not self._vec_available:
                # Fall back to brute-force cosine similarity in Python
                pass

        return self._conn

    def setup(self) -> None:
        """Create tables and indexes."""
        conn = self._ensure_connected()

        # Main data table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (namespace, key)
            )
        """)

        # Index for namespace queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_namespace
            ON memories(namespace)
        """)

        if self._vec_available:
            # Create virtual table for vector search
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(
                    embedding float[{self._dims}]
                )
            """)

        conn.commit()

    def _get_embedding(self, value: dict[str, Any]) -> list[float]:
        """Generate embedding for a value."""
        # Combine embed fields into text
        texts = []
        for field in self._embed_fields:
            if field in value and value[field]:
                texts.append(str(value[field]))
        text = " ".join(texts)

        if not text:
            return [0.0] * self._dims

        # Get embedding from OpenAI
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
        embedding_blob = _serialize_f32(embedding)

        # Check if exists for vec table management
        existing = conn.execute(
            "SELECT rowid FROM memories WHERE namespace = ? AND key = ?",
            (ns_str, key)
        ).fetchone()

        if existing:
            # Update
            conn.execute(
                "UPDATE memories SET value = ?, embedding = ? WHERE namespace = ? AND key = ?",
                (value_json, embedding_blob, ns_str, key)
            )
            if self._vec_available:
                conn.execute(
                    "UPDATE memories_vec SET embedding = ? WHERE rowid = ?",
                    (embedding_blob, existing["rowid"])
                )
        else:
            # Insert
            cursor = conn.execute(
                "INSERT INTO memories (namespace, key, value, embedding) VALUES (?, ?, ?, ?)",
                (ns_str, key, value_json, embedding_blob)
            )
            if self._vec_available:
                conn.execute(
                    "INSERT INTO memories_vec (rowid, embedding) VALUES (?, ?)",
                    (cursor.lastrowid, embedding_blob)
                )

        conn.commit()

    def get(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> StoreItem | None:
        """Retrieve a value by key."""
        conn = self._ensure_connected()
        ns_str = _serialize_namespace(namespace)

        row = conn.execute(
            "SELECT key, value FROM memories WHERE namespace = ? AND key = ?",
            (ns_str, key)
        ).fetchone()

        if row is None:
            return None

        return StoreItem(
            key=row["key"],
            value=json.loads(row["value"]),
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

        if self._vec_available:
            # Get rowid first for vec table
            row = conn.execute(
                "SELECT rowid FROM memories WHERE namespace = ? AND key = ?",
                (ns_str, key)
            ).fetchone()
            if row:
                conn.execute("DELETE FROM memories_vec WHERE rowid = ?", (row["rowid"],))

        conn.execute(
            "DELETE FROM memories WHERE namespace = ? AND key = ?",
            (ns_str, key)
        )
        conn.commit()

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
            rows = conn.execute(
                "SELECT key, value FROM memories WHERE namespace = ? LIMIT ?",
                (ns_str, limit)
            ).fetchall()
            return [
                StoreItem(
                    key=row["key"],
                    value=json.loads(row["value"]),
                    namespace=namespace,
                )
                for row in rows
            ]

        # Semantic search
        query_embedding = self._embeddings.embed_query(query)

        if self._vec_available:
            # Use sqlite-vec for efficient search
            query_blob = _serialize_f32(query_embedding)
            rows = conn.execute("""
                SELECT m.key, m.value, v.distance
                FROM memories m
                JOIN memories_vec v ON m.rowid = v.rowid
                WHERE m.namespace = ?
                AND v.embedding MATCH ?
                ORDER BY v.distance
                LIMIT ?
            """, (ns_str, query_blob, limit)).fetchall()

            return [
                StoreItem(
                    key=row["key"],
                    value=json.loads(row["value"]),
                    namespace=namespace,
                    score=1 - row["distance"],  # Convert distance to similarity
                )
                for row in rows
            ]
        else:
            # Fallback: brute-force cosine similarity in Python
            rows = conn.execute(
                "SELECT key, value, embedding FROM memories WHERE namespace = ?",
                (ns_str,)
            ).fetchall()

            results = []
            for row in rows:
                if row["embedding"]:
                    # Unpack embedding
                    emb = struct.unpack(f"{self._dims}f", row["embedding"])
                    # Cosine similarity
                    dot = sum(a * b for a, b in zip(query_embedding, emb))
                    norm_q = sum(a * a for a in query_embedding) ** 0.5
                    norm_e = sum(a * a for a in emb) ** 0.5
                    score = dot / (norm_q * norm_e) if norm_q and norm_e else 0
                else:
                    score = 0

                results.append((row, score))

            # Sort by score descending
            results.sort(key=lambda x: x[1], reverse=True)

            return [
                StoreItem(
                    key=row["key"],
                    value=json.loads(row["value"]),
                    namespace=namespace,
                    score=score,
                )
                for row, score in results[:limit]
            ]

    def close(self) -> None:
        """Close the connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def build_sqlite_backend(
    db_path: str | Path | None = None,
    embed_model: str = DEFAULT_EMBED_MODEL,
    dims: int = DEFAULT_EMBED_DIMS,
    embed_fields: list[str] | None = None,
) -> SQLiteBackend:
    """
    Create a SQLite backend.

    Args:
        db_path: Path to database file. Falls back to MEMORY_DB_PATH env var
                 or "engram.db" in current directory.
        embed_model: OpenAI embedding model.
        dims: Embedding dimensions.
        embed_fields: Fields to embed.

    Returns:
        SQLiteBackend instance.
    """
    if db_path is None:
        db_path = os.environ.get("MEMORY_DB_PATH", "engram.db")

    return SQLiteBackend(
        db_path=db_path,
        embed_model=embed_model,
        dims=dims,
        embed_fields=embed_fields,
    )
