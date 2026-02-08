"""
Base protocol for backend storage implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StoreItem:
    """Result item from store operations."""
    key: str
    value: dict[str, Any]
    namespace: tuple[str, ...]
    score: float | None = None  # Similarity score for search results


class BaseStore(ABC):
    """
    Abstract base class for storage backends.

    Implementations must provide:
    - Key-value storage with namespace scoping
    - Vector similarity search
    - Setup/migration support
    """

    @abstractmethod
    def setup(self) -> None:
        """
        Initialize the store (create tables, indexes, etc.).

        Should be idempotent - safe to call multiple times.
        """
        pass

    @abstractmethod
    def put(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
    ) -> None:
        """
        Store or update a value.

        Args:
            namespace: Hierarchical namespace tuple.
            key: Unique key within namespace.
            value: Dict to store (must include 'text' field for embedding).
        """
        pass

    @abstractmethod
    def get(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> StoreItem | None:
        """
        Retrieve a value by key.

        Args:
            namespace: Hierarchical namespace tuple.
            key: Key to retrieve.

        Returns:
            StoreItem if found, None otherwise.
        """
        pass

    @abstractmethod
    def delete(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> None:
        """
        Delete a value by key.

        Args:
            namespace: Hierarchical namespace tuple.
            key: Key to delete.
        """
        pass

    @abstractmethod
    def search(
        self,
        namespace: tuple[str, ...],
        query: str | None,
        limit: int = 10,
    ) -> list[StoreItem]:
        """
        Search for items, optionally with vector similarity.

        Args:
            namespace: Hierarchical namespace tuple.
            query: Search query for semantic search, or None to list all.
            limit: Maximum results to return.

        Returns:
            List of matching items, ordered by relevance.
        """
        pass

    def close(self) -> None:
        """
        Close the store connection.

        Default implementation does nothing. Override for backends
        that need explicit cleanup.
        """
        pass

    def __enter__(self) -> "BaseStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
