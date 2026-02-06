"""
Memory schema with durability tiers, temporal awareness, and version chains.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current time as timezone-aware UTC datetime."""
    return datetime.now(UTC)


class Durability(StrEnum):
    """Memory durability tier."""

    CORE = "core"
    """Stable facts that rarely change (name, preferences, biographical)."""

    SITUATIONAL = "situational"
    """Temporary context with explicit end date (traveling, project work)."""

    EPISODIC = "episodic"
    """Things that happened, decays over time (conversations, events)."""


class MemorySource(StrEnum):
    """How the memory was created."""

    EXPLICIT = "explicit"
    """User directly stated this fact."""

    INFERRED = "inferred"
    """Extracted/inferred from conversation."""

    SYSTEM = "system"
    """Created by system (consolidation, migration, etc.)."""


class Memory(BaseModel):
    """A memory item with full metadata."""

    id: UUID = Field(default_factory=uuid4)
    """Unique identifier for this memory."""

    text: str
    """The memory content (what we're remembering)."""

    durability: Durability = Durability.EPISODIC
    """How permanent this memory is."""

    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    """Confidence score (0-1) for inferred memories."""

    source: MemorySource = MemorySource.INFERRED
    """How this memory was created."""

    # Temporal validity
    valid_from: datetime = Field(default_factory=_utc_now)
    """When this fact became true."""

    valid_until: datetime | None = None
    """When this fact expires (None = permanent)."""

    # Version chain (for contradiction handling)
    supersedes: UUID | None = None
    """ID of the memory this one replaces (previous version)."""

    superseded_by: UUID | None = None
    """ID of the memory that replaced this one (next version)."""

    superseded_at: datetime | None = None
    """When this memory was superseded."""

    # Metadata
    created_at: datetime = Field(default_factory=_utc_now)
    """When this memory was stored."""

    last_accessed_at: datetime | None = None
    """Last time this memory was retrieved (for decay calculations)."""

    access_count: int = 0
    """Number of times this memory was retrieved."""

    tags: list[str] = Field(default_factory=list)
    """Optional tags for categorization."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Additional metadata (source conversation, etc.)."""

    def to_store_value(self) -> dict[str, Any]:
        """Convert to dict for storage in PostgresStore."""
        return {
            "id": str(self.id),
            "text": self.text,
            "durability": self.durability.value,
            "confidence": self.confidence,
            "source": self.source.value,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "supersedes": str(self.supersedes) if self.supersedes else None,
            "superseded_by": str(self.superseded_by) if self.superseded_by else None,
            "superseded_at": self.superseded_at.isoformat() if self.superseded_at else None,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
            "access_count": self.access_count,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_store_value(cls, value: dict[str, Any]) -> "Memory":
        """Reconstruct from stored dict."""

        def parse_dt(v: str | None) -> datetime | None:
            return datetime.fromisoformat(v) if v else None

        def parse_uuid(v: str | None) -> UUID | None:
            return UUID(v) if v else None

        return cls(
            id=UUID(value["id"]),
            text=value["text"],
            durability=Durability(value["durability"]),
            confidence=value.get("confidence", 0.8),
            source=MemorySource(value.get("source", "inferred")),
            valid_from=parse_dt(value.get("valid_from")) or _utc_now(),
            valid_until=parse_dt(value.get("valid_until")),
            supersedes=parse_uuid(value.get("supersedes")),
            superseded_by=parse_uuid(value.get("superseded_by")),
            superseded_at=parse_dt(value.get("superseded_at")),
            created_at=parse_dt(value.get("created_at")) or _utc_now(),
            last_accessed_at=parse_dt(value.get("last_accessed_at")),
            access_count=value.get("access_count", 0),
            tags=value.get("tags", []),
            metadata=value.get("metadata", {}),
        )

    def is_valid(self, at: datetime | None = None) -> bool:
        """Check if this memory is valid at the given time."""
        at = at or _utc_now()

        # Superseded memories are not valid
        if self.superseded_by is not None:
            return False

        # Check temporal validity
        if self.valid_from and at < self.valid_from:
            return False
        if self.valid_until and at > self.valid_until:
            return False

        return True

    def is_current(self) -> bool:
        """Check if this is the current version (not superseded)."""
        return self.superseded_by is None


class MemoryCreate(BaseModel):
    """Input for creating a new memory."""

    text: str
    durability: Durability = Durability.EPISODIC
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source: MemorySource = MemorySource.INFERRED
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_memory(self) -> Memory:
        """Convert to full Memory object."""
        return Memory(
            text=self.text,
            durability=self.durability,
            confidence=self.confidence,
            source=self.source,
            valid_from=self.valid_from or _utc_now(),
            valid_until=self.valid_until,
            tags=self.tags,
            metadata=self.metadata,
        )


class MemoryUpdate(BaseModel):
    """Input for updating a memory (creates new version in chain)."""

    text: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    source: MemorySource = MemorySource.EXPLICIT
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class MemoryQuery(BaseModel):
    """Query parameters for memory retrieval."""

    query: str
    """Semantic search query."""

    limit: int = Field(default=10, ge=1, le=100)
    """Maximum number of results."""

    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Minimum confidence threshold."""

    durability: list[Durability] | None = None
    """Filter by durability tier(s)."""

    include_superseded: bool = False
    """Include superseded (old version) memories."""

    include_expired: bool = False
    """Include memories past their valid_until date."""

    tags: list[str] | None = None
    """Filter by tags (any match)."""

    valid_at: datetime | None = None
    """Check validity at this time (default: now)."""
