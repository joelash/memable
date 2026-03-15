"""
Integration tests for memory extraction.

Requires OPENAI_API_KEY environment variable.
"""

import os

import pytest

from memento_ai.extraction import MemoryExtractor, extract_memories
from memento_ai.schema import Durability


@pytest.fixture
def skip_without_openai():
    """Skip test if OPENAI_API_KEY is not set."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")


@pytest.mark.integration
class TestMemoryExtraction:
    """Integration tests for extraction."""

    def test_extract_core_fact(self, skip_without_openai, sample_messages):
        """Test extracting core biographical facts."""
        extracted = extract_memories(sample_messages[:2])

        assert len(extracted) > 0

        # Should extract name and location as core facts
        texts = [m.text.lower() for m in extracted]
        assert any("joel" in t for t in texts)

    def test_extract_situational_fact(self, skip_without_openai, sample_messages):
        """Test extracting situational facts with expiry."""
        extracted = extract_memories(sample_messages)

        # Should find the trip mention
        situational = [m for m in extracted if m.durability == Durability.SITUATIONAL]

        # If it classified the trip as situational, it should have an expiry
        if situational:
            assert any(m.valid_until is not None for m in situational)

    def test_extract_nothing_from_greeting(self, skip_without_openai):
        """Test that greetings don't produce memories."""
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there! How can I help?"},
        ]

        extracted = extract_memories(messages)

        # Should extract nothing or very little from a simple greeting
        assert len(extracted) == 0

    def test_extractor_with_context(self, skip_without_openai):
        """Test extraction with additional context."""
        messages = [
            {"role": "user", "content": "I switched to vim last month."},
        ]

        extractor = MemoryExtractor()
        extracted = extractor.extract(
            messages,
            context="User is a software developer who previously used VS Code",
        )

        # Should extract the editor preference
        assert len(extracted) > 0
        texts = [m.text.lower() for m in extracted]
        assert any("vim" in t for t in texts)


@pytest.mark.integration
@pytest.mark.asyncio
class TestAsyncExtraction:
    """Async extraction tests."""

    async def test_async_extract(self, skip_without_openai, sample_messages):
        """Test async extraction."""
        extractor = MemoryExtractor()
        extracted = await extractor.aextract(sample_messages)

        assert len(extracted) > 0
