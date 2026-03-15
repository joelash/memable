"""
Embedding API cost tests for memento-ai.

Tracks OpenAI API usage per operation to help estimate costs.

Run with: pytest tests/performance/test_embedding_costs.py -v -s
"""

import os
from unittest.mock import patch, MagicMock, call
from uuid import uuid4

import pytest

from memable import Durability, MemoryCreate, build_sqlite_store


class TestEmbeddingCosts:
    """Track embedding API calls and estimate costs."""

    # OpenAI pricing (as of 2024)
    # text-embedding-3-small: $0.02 per 1M tokens
    PRICE_PER_MILLION_TOKENS = 0.02

    @pytest.fixture
    def namespace(self):
        return (f"cost_test_{uuid4().hex[:8]}", "memories")

    def test_embedding_calls_per_add(self, namespace):
        """Count embedding API calls for add operation."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY required")

        with build_sqlite_store(":memory:") as store:
            store.setup()

            # Patch at the class level to count calls
            with patch.object(
                store._store._get_embeddings().__class__,
                'embed_query',
                wraps=store._store._get_embeddings().embed_query
            ) as mock_embed:
                store.add(namespace, MemoryCreate(
                    text="User prefers dark mode in all applications",
                    durability=Durability.CORE,
                ))

                call_count = mock_embed.call_count
                print(f"\n📊 Embedding Calls per ADD: {call_count}")
                assert call_count == 1, f"Expected 1 embedding call, got {call_count}"

    def test_embedding_calls_per_search(self, namespace):
        """Count embedding API calls for search operation."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY required")

        with build_sqlite_store(":memory:") as store:
            store.setup()

            # Seed some data first (these will call embed)
            for i in range(5):
                store.add(namespace, MemoryCreate(
                    text=f"Memory {i} about preferences",
                    durability=Durability.CORE,
                ))

            # Now patch and count only search calls
            with patch.object(
                store._store._get_embeddings().__class__,
                'embed_query',
                wraps=store._store._get_embeddings().embed_query
            ) as mock_embed:
                store.search(namespace, "user preferences")

                call_count = mock_embed.call_count
                print(f"\n📊 Embedding Calls per SEARCH: {call_count}")
                assert call_count == 1, f"Expected 1 embedding call, got {call_count}"

    def test_no_embedding_for_get(self, namespace):
        """Verify get() doesn't call embedding API."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY required")

        with build_sqlite_store(":memory:") as store:
            store.setup()

            # Create a memory first
            mem = store.add(namespace, MemoryCreate(
                text="Test memory",
                durability=Durability.CORE,
            ))

            # Now patch and verify get doesn't call embed
            with patch.object(
                store._store._get_embeddings().__class__,
                'embed_query',
                wraps=store._store._get_embeddings().embed_query
            ) as mock_embed:
                store.get(namespace, mem.id)

                call_count = mock_embed.call_count
                print(f"\n📊 Embedding Calls per GET: {call_count}")
                assert call_count == 0, f"GET should not call embedding API, got {call_count} calls"

    def test_cost_estimation(self):
        """Estimate costs for typical usage patterns (no API needed)."""
        # Typical token counts (rough estimates)
        avg_memory_tokens = 20  # "User prefers dark mode" ≈ 5 tokens, with overhead
        avg_query_tokens = 10

        # Usage scenarios
        scenarios = {
            "Light (100 adds, 500 searches/day)": {
                "adds_per_day": 100,
                "searches_per_day": 500,
            },
            "Medium (500 adds, 2000 searches/day)": {
                "adds_per_day": 500,
                "searches_per_day": 2000,
            },
            "Heavy (2000 adds, 10000 searches/day)": {
                "adds_per_day": 2000,
                "searches_per_day": 10000,
            },
        }

        print(f"\n📊 Cost Estimation (text-embedding-3-small @ ${self.PRICE_PER_MILLION_TOKENS}/1M tokens):")

        for name, usage in scenarios.items():
            add_tokens = usage["adds_per_day"] * avg_memory_tokens
            search_tokens = usage["searches_per_day"] * avg_query_tokens
            total_tokens = add_tokens + search_tokens

            daily_cost = (total_tokens / 1_000_000) * self.PRICE_PER_MILLION_TOKENS
            monthly_cost = daily_cost * 30

            print(f"\n   {name}:")
            print(f"      Daily tokens: {total_tokens:,}")
            print(f"      Daily cost: ${daily_cost:.4f}")
            print(f"      Monthly cost: ${monthly_cost:.2f}")


class TestExtractionCosts:
    """Estimate costs for memory extraction (LLM calls)."""

    # GPT-4.1-mini pricing (rough estimate)
    # Input: $0.15 per 1M tokens, Output: $0.60 per 1M tokens
    INPUT_PRICE_PER_MILLION = 0.15
    OUTPUT_PRICE_PER_MILLION = 0.60

    def test_extraction_cost_estimation(self):
        """Estimate extraction costs for various usage patterns."""
        # Typical token counts
        avg_conversation_tokens = 500  # Input to extraction
        avg_extraction_output_tokens = 100  # JSON response

        scenarios = {
            "Light (50 extractions/day)": 50,
            "Medium (200 extractions/day)": 200,
            "Heavy (1000 extractions/day)": 1000,
        }

        print(f"\n📊 Extraction Cost Estimation (gpt-4.1-mini):")

        for name, extractions in scenarios.items():
            input_tokens = extractions * avg_conversation_tokens
            output_tokens = extractions * avg_extraction_output_tokens

            input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_MILLION
            output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE_PER_MILLION
            daily_cost = input_cost + output_cost
            monthly_cost = daily_cost * 30

            print(f"\n   {name}:")
            print(f"      Daily input tokens: {input_tokens:,}")
            print(f"      Daily output tokens: {output_tokens:,}")
            print(f"      Daily cost: ${daily_cost:.4f}")
            print(f"      Monthly cost: ${monthly_cost:.2f}")

    def test_total_cost_estimation(self):
        """Estimate total costs (embeddings + extraction)."""
        # Combined pricing
        EMBED_PRICE = 0.02  # per 1M tokens
        EXTRACT_INPUT_PRICE = 0.15
        EXTRACT_OUTPUT_PRICE = 0.60

        # Per-operation token estimates
        embed_tokens_per_add = 20
        embed_tokens_per_search = 10
        extract_input_tokens = 500
        extract_output_tokens = 100

        # Typical ratios
        # Assume 1 extraction per 5 conversation turns
        # Assume 0.3 memories per turn (not every turn is memorable)
        # Assume 2 searches per turn (retrieve context)

        turns_per_day = 100  # 100 conversation turns

        extractions = turns_per_day / 5
        adds = turns_per_day * 0.3
        searches = turns_per_day * 2

        # Calculate costs
        embed_cost = (
            (adds * embed_tokens_per_add + searches * embed_tokens_per_search)
            / 1_000_000 * EMBED_PRICE
        )
        extract_cost = (
            (extractions * extract_input_tokens) / 1_000_000 * EXTRACT_INPUT_PRICE +
            (extractions * extract_output_tokens) / 1_000_000 * EXTRACT_OUTPUT_PRICE
        )
        total_daily = embed_cost + extract_cost

        print(f"\n📊 Total Daily Cost Estimation (100 conversation turns/day):")
        print(f"   Extractions: {extractions:.0f}")
        print(f"   Memory adds: {adds:.0f}")
        print(f"   Searches: {searches:.0f}")
        print(f"   Embedding cost: ${embed_cost:.4f}")
        print(f"   Extraction cost: ${extract_cost:.4f}")
        print(f"   Total daily: ${total_daily:.4f}")
        print(f"   Total monthly: ${total_daily * 30:.2f}")
