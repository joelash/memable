"""
Unit tests for consolidation module.
"""


from memable.consolidation import ConsolidationResult, ConsolidationStrategy


class TestConsolidationStrategy:
    """Tests for ConsolidationStrategy enum."""

    def test_strategy_values(self):
        """Test strategy enum values."""
        assert ConsolidationStrategy.PRUNE_EXPIRED.value == "prune_expired"
        assert ConsolidationStrategy.DECAY_ACCESS.value == "decay_access"
        assert ConsolidationStrategy.SUMMARIZE.value == "summarize"
        assert ConsolidationStrategy.DEDUPE.value == "dedupe"

    def test_strategy_from_string(self):
        """Test creating strategy from string."""
        assert ConsolidationStrategy("prune_expired") == ConsolidationStrategy.PRUNE_EXPIRED
        assert ConsolidationStrategy("summarize") == ConsolidationStrategy.SUMMARIZE


class TestConsolidationResult:
    """Tests for ConsolidationResult model."""

    def test_result_defaults(self):
        """Test default values for ConsolidationResult."""
        result = ConsolidationResult(strategy=ConsolidationStrategy.PRUNE_EXPIRED)

        assert result.strategy == ConsolidationStrategy.PRUNE_EXPIRED
        assert result.memories_processed == 0
        assert result.memories_removed == 0
        assert result.memories_created == 0
        assert result.summaries_created == 0
        assert result.details == []

    def test_result_with_stats(self):
        """Test ConsolidationResult with stats."""
        result = ConsolidationResult(
            strategy=ConsolidationStrategy.SUMMARIZE,
            memories_processed=10,
            memories_removed=8,
            memories_created=2,
            summaries_created=2,
            details=["Summarized 8 memories into 2"],
        )

        assert result.memories_processed == 10
        assert result.memories_removed == 8
        assert result.memories_created == 2
        assert len(result.details) == 1
