"""
Unit tests for retrieval module.
"""

from memable.retrieval import RetrievalResult, build_memory_context
from memable.schema import Durability, Memory, MemoryType


class TestRetrievalResult:
    """Tests for RetrievalResult class."""

    def test_empty_result(self):
        """Test empty retrieval result."""
        result = RetrievalResult(memories=[], query="test")

        assert result.count == 0
        assert result.as_context_string() == "No relevant memories found."
        assert result.as_dict_list() == []

    def test_result_with_memories(self, memories_for_search):
        """Test retrieval result with memories."""
        result = RetrievalResult(memories=memories_for_search, query="user info")

        assert result.count == 4
        assert len(result.as_dict_list()) == 4

    def test_context_string_bullets(self, memories_for_search):
        """Test bullet format context string."""
        result = RetrievalResult(memories=memories_for_search[:2], query="test")
        context = result.as_context_string(format="bullets")

        assert context.startswith("- ")
        assert "User's name is Joel" in context
        assert "User lives in Wheaton" in context

    def test_context_string_numbered(self, memories_for_search):
        """Test numbered format context string."""
        result = RetrievalResult(memories=memories_for_search[:2], query="test")
        context = result.as_context_string(format="numbered")

        assert context.startswith("1. ")
        assert "2. " in context

    def test_context_string_with_metadata(self, memories_for_search):
        """Test context string with metadata."""
        result = RetrievalResult(memories=memories_for_search[:1], query="test")
        context = result.as_context_string(include_metadata=True)

        assert "[core]" in context

    def test_context_string_max_chars(self, memories_for_search):
        """Test context string truncation."""
        result = RetrievalResult(memories=memories_for_search, query="test")
        context = result.as_context_string(max_chars=50)

        assert len(context) <= 50
        assert context.endswith("...")

    def test_as_dict_list(self, memories_for_search):
        """Test converting to dict list."""
        result = RetrievalResult(memories=memories_for_search[:1], query="test")
        dicts = result.as_dict_list()

        assert len(dicts) == 1
        assert dicts[0]["text"] == "User's name is Joel"
        assert dicts[0]["durability"] == "core"
        assert "confidence" in dicts[0]
        assert "created_at" in dicts[0]

    def test_context_string_with_memory_type_metadata(self):
        """Test context string shows memory_type in metadata."""
        memories = [
            Memory(
                text="Always use TypeScript strict mode",
                durability=Durability.CORE,
                memory_type=MemoryType.RULE,
            )
        ]
        result = RetrievalResult(memories=memories, query="test")
        context = result.as_context_string(include_metadata=True)

        assert "[core]" in context
        assert "[rule]" in context

    def test_as_dict_list_includes_memory_type(self):
        """Test dict list includes memory_type."""
        memories = [
            Memory(
                text="Chose React for the frontend",
                durability=Durability.SITUATIONAL,
                memory_type=MemoryType.DECISION,
            )
        ]
        result = RetrievalResult(memories=memories, query="test")
        dicts = result.as_dict_list()

        assert dicts[0]["memory_type"] == "decision"

    def test_as_dict_list_memory_type_none(self):
        """Test dict list handles None memory_type."""
        memories = [
            Memory(text="Simple fact without type")
        ]
        result = RetrievalResult(memories=memories, query="test")
        dicts = result.as_dict_list()

        assert dicts[0]["memory_type"] is None


class TestBuildMemoryContext:
    """Tests for build_memory_context function."""

    def test_build_empty_context(self):
        """Test building context with no memories."""
        result = RetrievalResult(memories=[], query="test")
        context = build_memory_context(result)

        assert context == "MEMORIES: None available."

    def test_build_context_custom_prefix(self, memories_for_search):
        """Test building context with custom prefix."""
        result = RetrievalResult(memories=memories_for_search[:1], query="test")
        context = build_memory_context(result, prefix="LONG-TERM MEMORY")

        assert context.startswith("LONG-TERM MEMORY:")

    def test_build_context_format(self, memories_for_search):
        """Test building context with different formats."""
        result = RetrievalResult(memories=memories_for_search[:2], query="test")

        bullets = build_memory_context(result, format="bullets")
        assert "- " in bullets

        numbered = build_memory_context(result, format="numbered")
        assert "1. " in numbered
