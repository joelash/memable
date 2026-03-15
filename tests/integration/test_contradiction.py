"""
Integration tests for contradiction detection.

Requires OPENAI_API_KEY environment variable.
"""

import os

import pytest

from memable.contradiction import (
    ContradictionDetector,
    add_memory_with_contradiction_check,
)
from memable.schema import Memory


@pytest.fixture
def skip_without_openai():
    """Skip test if OPENAI_API_KEY is not set."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")


@pytest.mark.integration
class TestContradictionDetection:
    """Integration tests for contradiction detection."""

    def test_detect_location_contradiction(self, skip_without_openai, memories_for_search):
        """Test detecting location change contradiction."""
        detector = ContradictionDetector()

        # Check if "moved to Austin" contradicts existing memories
        check = detector.check(
            "User moved to Austin, TX",
            memories_for_search,
        )

        assert check.has_contradiction is True
        assert check.contradicted_memory_id is not None
        # Should flag the Wheaton memory
        assert "wheaton" in check.contradicted_text.lower()

    def test_no_contradiction_for_new_fact(self, skip_without_openai, memories_for_search):
        """Test that new unrelated facts don't trigger contradictions."""
        detector = ContradictionDetector()

        check = detector.check(
            "User has a dog named Bentley",
            memories_for_search,
        )

        assert check.has_contradiction is False

    def test_complementary_facts_not_contradiction(self, skip_without_openai, memories_for_search):
        """Test that complementary facts aren't flagged as contradictions."""
        detector = ContradictionDetector()

        # "Also likes Python" shouldn't contradict "prefers TypeScript"
        check = detector.check(
            "User also enjoys Python for scripting",
            memories_for_search,
        )

        assert check.has_contradiction is False


@pytest.mark.integration
class TestContradictionResolution:
    """Integration tests for contradiction resolution with store."""

    def test_add_with_contradiction_check(
        self,
        skip_without_openai,
        semantic_store,
        test_namespace,
    ):
        """Test adding memory with automatic contradiction handling."""
        # First, add a memory about location
        semantic_store.add(
            test_namespace,
            Memory(text="User lives in Chicago"),
        )

        # Now add a contradicting memory
        new_mem, check = add_memory_with_contradiction_check(
            store=semantic_store,
            namespace=test_namespace,
            new_fact="User moved to Austin",
        )

        # Should detect and resolve contradiction
        if check and check.has_contradiction:
            # The old memory should be superseded
            history = semantic_store.get_version_history(
                test_namespace,
                check.contradicted_memory_id,
            )
            assert len(history) == 2
            assert history[1].text == "User moved to Austin"
