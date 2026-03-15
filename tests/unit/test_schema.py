"""
Unit tests for schema models.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from memable.schema import (
    Durability,
    Memory,
    MemoryCreate,
    MemoryQuery,
    MemorySource,
    MemoryType,
    MemoryUpdate,
)


class TestMemory:
    """Tests for the Memory model."""

    def test_memory_defaults(self):
        """Test default values for Memory."""
        mem = Memory(text="Test memory")

        assert mem.text == "Test memory"
        assert mem.durability == Durability.EPISODIC
        assert mem.confidence == 0.8
        assert mem.source == MemorySource.INFERRED
        assert mem.id is not None
        assert mem.created_at is not None
        assert mem.supersedes is None
        assert mem.superseded_by is None
        assert mem.tags == []

    def test_memory_custom_values(self, sample_memory):
        """Test Memory with custom values."""
        assert sample_memory.durability == Durability.CORE
        assert sample_memory.confidence == 0.95
        assert sample_memory.source == MemorySource.EXPLICIT

    def test_memory_to_store_value(self, sample_memory):
        """Test serialization to store value dict."""
        value = sample_memory.to_store_value()

        assert value["text"] == sample_memory.text
        assert value["durability"] == "core"
        assert value["confidence"] == 0.95
        assert value["source"] == "explicit"
        assert value["id"] == str(sample_memory.id)

    def test_memory_from_store_value(self, sample_memory):
        """Test deserialization from store value dict."""
        value = sample_memory.to_store_value()
        restored = Memory.from_store_value(value)

        assert restored.id == sample_memory.id
        assert restored.text == sample_memory.text
        assert restored.durability == sample_memory.durability
        assert restored.confidence == sample_memory.confidence

    def test_memory_is_valid_permanent(self):
        """Test is_valid for permanent memories."""
        mem = Memory(text="Permanent fact", valid_until=None)

        assert mem.is_valid()
        assert mem.is_valid(at=datetime.now(UTC) + timedelta(days=365))

    def test_memory_is_valid_expired(self):
        """Test is_valid for expired memories."""
        mem = Memory(
            text="Temporary fact",
            valid_until=datetime.now(UTC) - timedelta(days=1),
        )

        assert not mem.is_valid()

    def test_memory_is_valid_future(self):
        """Test is_valid for memories with future start date."""
        mem = Memory(
            text="Future fact",
            valid_from=datetime.now(UTC) + timedelta(days=1),
        )

        assert not mem.is_valid()

    def test_memory_is_valid_superseded(self):
        """Test is_valid for superseded memories."""
        mem = Memory(
            text="Old fact",
            superseded_by=uuid4(),
        )

        assert not mem.is_valid()
        assert not mem.is_current()

    def test_memory_is_current(self):
        """Test is_current for non-superseded memories."""
        mem = Memory(text="Current fact")

        assert mem.is_current()


class TestMemoryCreate:
    """Tests for MemoryCreate model."""

    def test_memory_create_to_memory(self, sample_memory_create):
        """Test converting MemoryCreate to Memory."""
        mem = sample_memory_create.to_memory()

        assert mem.text == sample_memory_create.text
        assert mem.durability == sample_memory_create.durability
        assert mem.confidence == sample_memory_create.confidence
        assert mem.tags == sample_memory_create.tags
        assert mem.id is not None

    def test_memory_create_defaults(self):
        """Test default values for MemoryCreate."""
        mc = MemoryCreate(text="Simple fact")

        assert mc.durability == Durability.EPISODIC
        assert mc.confidence == 0.8
        assert mc.source == MemorySource.INFERRED


class TestMemoryUpdate:
    """Tests for MemoryUpdate model."""

    def test_memory_update_defaults(self):
        """Test default values for MemoryUpdate."""
        update = MemoryUpdate(text="Updated text")

        assert update.text == "Updated text"
        assert update.confidence == 0.9
        assert update.source == MemorySource.EXPLICIT


class TestMemoryQuery:
    """Tests for MemoryQuery model."""

    def test_memory_query_defaults(self):
        """Test default values for MemoryQuery."""
        query = MemoryQuery(query="test search")

        assert query.query == "test search"
        assert query.limit == 10
        assert query.min_confidence == 0.0
        assert query.include_superseded is False
        assert query.include_expired is False

    def test_memory_query_custom(self):
        """Test MemoryQuery with custom filters."""
        query = MemoryQuery(
            query="test",
            limit=5,
            durability=[Durability.CORE],
            min_confidence=0.8,
        )

        assert query.limit == 5
        assert query.durability == [Durability.CORE]
        assert query.min_confidence == 0.8

    def test_memory_query_limit_bounds(self):
        """Test that limit is bounded."""
        with pytest.raises(ValueError):
            MemoryQuery(query="test", limit=0)

        with pytest.raises(ValueError):
            MemoryQuery(query="test", limit=101)


class TestDurability:
    """Tests for Durability enum."""

    def test_durability_values(self):
        """Test durability tier values."""
        assert Durability.CORE.value == "core"
        assert Durability.SITUATIONAL.value == "situational"
        assert Durability.EPISODIC.value == "episodic"

    def test_durability_from_string(self):
        """Test creating durability from string."""
        assert Durability("core") == Durability.CORE
        assert Durability("situational") == Durability.SITUATIONAL
        assert Durability("episodic") == Durability.EPISODIC


class TestMemorySource:
    """Tests for MemorySource enum."""

    def test_source_values(self):
        """Test memory source values."""
        assert MemorySource.EXPLICIT.value == "explicit"
        assert MemorySource.INFERRED.value == "inferred"
        assert MemorySource.SYSTEM.value == "system"


class TestMemoryType:
    """Tests for MemoryType enum."""

    def test_memory_type_values(self):
        """Test memory type values."""
        assert MemoryType.FACT.value == "fact"
        assert MemoryType.RULE.value == "rule"
        assert MemoryType.DECISION.value == "decision"
        assert MemoryType.PREFERENCE.value == "preference"
        assert MemoryType.CONTEXT.value == "context"
        assert MemoryType.OBSERVATION.value == "observation"

    def test_memory_type_from_string(self):
        """Test creating memory type from string."""
        assert MemoryType("fact") == MemoryType.FACT
        assert MemoryType("rule") == MemoryType.RULE
        assert MemoryType("decision") == MemoryType.DECISION
        assert MemoryType("preference") == MemoryType.PREFERENCE
        assert MemoryType("context") == MemoryType.CONTEXT
        assert MemoryType("observation") == MemoryType.OBSERVATION


class TestMemoryWithType:
    """Tests for Memory model with memory_type field."""

    def test_memory_with_type(self):
        """Test Memory with memory_type field."""
        mem = Memory(
            text="Always use TypeScript strict mode",
            durability=Durability.CORE,
            memory_type=MemoryType.RULE,
        )

        assert mem.memory_type == MemoryType.RULE

    def test_memory_type_defaults_to_none(self):
        """Test that memory_type defaults to None."""
        mem = Memory(text="Test memory")

        assert mem.memory_type is None

    def test_memory_to_store_value_with_type(self):
        """Test serialization includes memory_type."""
        mem = Memory(
            text="Chose Tailwind for CSS",
            memory_type=MemoryType.DECISION,
        )
        value = mem.to_store_value()

        assert value["memory_type"] == "decision"

    def test_memory_to_store_value_without_type(self):
        """Test serialization with None memory_type."""
        mem = Memory(text="Test memory")
        value = mem.to_store_value()

        assert value["memory_type"] is None

    def test_memory_from_store_value_with_type(self):
        """Test deserialization restores memory_type."""
        mem = Memory(
            text="User prefers dark mode",
            memory_type=MemoryType.PREFERENCE,
        )
        value = mem.to_store_value()
        restored = Memory.from_store_value(value)

        assert restored.memory_type == MemoryType.PREFERENCE

    def test_memory_from_store_value_without_type(self):
        """Test deserialization handles missing memory_type."""
        # Simulate old data without memory_type field
        value = {
            "id": str(uuid4()),
            "text": "Old memory without type",
            "durability": "core",
            "confidence": 0.8,
            "source": "inferred",
            # no memory_type field
        }
        restored = Memory.from_store_value(value)

        assert restored.memory_type is None


class TestMemoryCreateWithType:
    """Tests for MemoryCreate with memory_type."""

    def test_memory_create_with_type(self):
        """Test MemoryCreate with memory_type."""
        mc = MemoryCreate(
            text="API rate limit is 100/min",
            durability=Durability.SITUATIONAL,
            memory_type=MemoryType.FACT,
        )

        assert mc.memory_type == MemoryType.FACT

    def test_memory_create_to_memory_preserves_type(self):
        """Test that to_memory() preserves memory_type."""
        mc = MemoryCreate(
            text="Currently refactoring auth module",
            memory_type=MemoryType.CONTEXT,
        )
        mem = mc.to_memory()

        assert mem.memory_type == MemoryType.CONTEXT


class TestMemoryQueryWithType:
    """Tests for MemoryQuery with memory_type filter."""

    def test_memory_query_with_type_filter(self):
        """Test MemoryQuery with memory_type filter."""
        query = MemoryQuery(
            query="coding standards",
            memory_type=[MemoryType.RULE],
        )

        assert query.memory_type == [MemoryType.RULE]

    def test_memory_query_with_multiple_types(self):
        """Test MemoryQuery with multiple memory types."""
        query = MemoryQuery(
            query="project decisions",
            memory_type=[MemoryType.DECISION, MemoryType.RULE],
        )

        assert MemoryType.DECISION in query.memory_type
        assert MemoryType.RULE in query.memory_type

    def test_memory_query_type_defaults_to_none(self):
        """Test that memory_type filter defaults to None (no filter)."""
        query = MemoryQuery(query="test")

        assert query.memory_type is None
