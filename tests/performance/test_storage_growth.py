"""
Storage growth tests for memento-ai.

Measures how database size grows relative to memory count and content.

Run with: pytest tests/performance/test_storage_growth.py -v -s
"""

import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from memable import Durability, MemoryCreate, build_sqlite_store, build_duckdb_store

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY required for storage tests"
)


def get_file_size_kb(path: Path) -> float:
    """Get file size in KB."""
    return path.stat().st_size / 1024 if path.exists() else 0


class TestStorageGrowth:
    """Test storage requirements for memories."""

    def test_sqlite_bytes_per_memory(self, tmp_path):
        """Measure bytes per memory in SQLite."""
        db_path = tmp_path / "test.db"
        namespace = (f"storage_test_{uuid4().hex[:8]}", "memories")

        with build_sqlite_store(str(db_path)) as store:
            store.setup()

            # Measure initial size
            initial_size = get_file_size_kb(db_path)

            # Add memories with typical content
            num_memories = 50
            for i in range(num_memories):
                store.add(namespace, MemoryCreate(
                    text=f"User prefers setting {i} with value {i * 10}. This is a typical memory length.",
                    durability=Durability.CORE,
                    confidence=0.9,
                    tags=["preference", "settings"],
                ))

        # Measure final size
        final_size = get_file_size_kb(db_path)
        growth = final_size - initial_size
        bytes_per_memory = (growth * 1024) / num_memories

        print(f"\n📊 SQLite Storage:")
        print(f"   Initial size: {initial_size:.2f} KB")
        print(f"   Final size: {final_size:.2f} KB")
        print(f"   Growth: {growth:.2f} KB for {num_memories} memories")
        print(f"   Bytes per memory: {bytes_per_memory:.0f} bytes")
        print(f"   KB per 1000 memories: {bytes_per_memory * 1000 / 1024:.1f} KB")
        print(f"   MB per 10000 memories: {bytes_per_memory * 10000 / (1024 * 1024):.2f} MB")

        # Embeddings are ~6KB (1536 floats * 4 bytes), plus overhead
        # Each memory should be under 10KB
        assert bytes_per_memory < 10240, f"Memory too large: {bytes_per_memory} bytes"

    @pytest.mark.skipif(
        not pytest.importorskip("duckdb", reason="DuckDB not installed"),
        reason="DuckDB not installed"
    )
    def test_duckdb_bytes_per_memory(self, tmp_path):
        """Measure bytes per memory in DuckDB."""
        db_path = tmp_path / "test.duckdb"
        namespace = (f"storage_test_{uuid4().hex[:8]}", "memories")

        with build_duckdb_store(str(db_path)) as store:
            store.setup()

            # Add memories
            num_memories = 50
            for i in range(num_memories):
                store.add(namespace, MemoryCreate(
                    text=f"User prefers setting {i} with value {i * 10}. This is a typical memory length.",
                    durability=Durability.CORE,
                    confidence=0.9,
                    tags=["preference", "settings"],
                ))

        final_size = get_file_size_kb(db_path)
        bytes_per_memory = (final_size * 1024) / num_memories

        print(f"\n📊 DuckDB Storage:")
        print(f"   Final size: {final_size:.2f} KB")
        print(f"   Bytes per memory: {bytes_per_memory:.0f} bytes")
        print(f"   MB per 10000 memories: {bytes_per_memory * 10000 / (1024 * 1024):.2f} MB")

        # DuckDB stores embeddings as DOUBLE[] which is larger than packed binary
        # 1536 dims * 8 bytes = 12KB just for embedding, plus JSON overhead
        assert bytes_per_memory < 40960, f"Memory too large: {bytes_per_memory} bytes"

    def test_storage_with_version_chains(self, tmp_path):
        """Measure storage impact of version chains."""
        db_path = tmp_path / "test.db"
        namespace = (f"version_test_{uuid4().hex[:8]}", "memories")

        with build_sqlite_store(str(db_path)) as store:
            store.setup()

            # Create initial memories
            memories = []
            for i in range(10):
                mem = store.add(namespace, MemoryCreate(
                    text=f"Original fact {i}",
                    durability=Durability.CORE,
                ))
                memories.append(mem)

            size_after_initial = get_file_size_kb(db_path)

            # Update each memory (creates version chain)
            from memable.schema import MemoryUpdate
            for mem in memories:
                store.update(namespace, mem.id, MemoryUpdate(
                    text=f"Updated fact replacing {mem.id}",
                    confidence=0.95,
                ))

            size_after_updates = get_file_size_kb(db_path)

        growth_ratio = size_after_updates / size_after_initial if size_after_initial > 0 else 0

        print(f"\n📊 Version Chain Storage:")
        print(f"   After 10 initial memories: {size_after_initial:.2f} KB")
        print(f"   After 10 updates (20 total): {size_after_updates:.2f} KB")
        print(f"   Growth ratio: {growth_ratio:.2f}x")

        # Updates should roughly double storage (old + new versions)
        assert growth_ratio < 3, f"Version chains using too much space: {growth_ratio}x"


class TestConversationSimulation:
    """Simulate realistic conversation patterns and measure growth."""

    def test_growth_over_conversations(self, tmp_path):
        """Simulate memory growth over multiple conversations."""
        db_path = tmp_path / "conversation_test.db"
        namespace = ("test_user", "memories")

        # Typical memories extracted per conversation turn
        memories_per_turn = 0.3  # Not every turn has memorable content
        turns_per_conversation = 10
        num_conversations = 5

        with build_sqlite_store(str(db_path)) as store:
            store.setup()

            memory_count = 0
            for conv in range(num_conversations):
                for turn in range(turns_per_conversation):
                    # Simulate probabilistic extraction
                    import random
                    if random.random() < memories_per_turn:
                        store.add(namespace, MemoryCreate(
                            text=f"Conversation {conv}, turn {turn}: User mentioned preference",
                            durability=random.choice([
                                Durability.CORE,
                                Durability.SITUATIONAL,
                                Durability.EPISODIC,
                            ]),
                            confidence=random.uniform(0.7, 0.95),
                        ))
                        memory_count += 1

        final_size = get_file_size_kb(db_path)

        print(f"\n📊 Conversation Simulation:")
        print(f"   Conversations: {num_conversations}")
        print(f"   Turns per conversation: {turns_per_conversation}")
        print(f"   Total turns: {num_conversations * turns_per_conversation}")
        print(f"   Memories extracted: {memory_count}")
        print(f"   Extraction rate: {memory_count / (num_conversations * turns_per_conversation):.2%}")
        print(f"   Database size: {final_size:.2f} KB")
        if memory_count > 0:
            print(f"   KB per memory: {final_size / memory_count:.2f}")

    def test_projected_growth(self, tmp_path):
        """Project storage needs for various usage levels."""
        db_path = tmp_path / "projection_test.db"
        namespace = ("test_user", "memories")

        # Create sample memories to measure baseline
        sample_size = 20

        with build_sqlite_store(str(db_path)) as store:
            store.setup()

            for i in range(sample_size):
                store.add(namespace, MemoryCreate(
                    text=f"Sample memory {i} with typical content about user preferences and context",
                    durability=Durability.CORE,
                    confidence=0.85,
                    tags=["sample"],
                ))

        size_kb = get_file_size_kb(db_path)
        kb_per_memory = size_kb / sample_size

        # Project for various scales
        projections = {
            "Light user (100 memories)": 100 * kb_per_memory / 1024,  # MB
            "Regular user (1,000 memories)": 1000 * kb_per_memory / 1024,
            "Heavy user (10,000 memories)": 10000 * kb_per_memory / 1024,
            "Power user (100,000 memories)": 100000 * kb_per_memory / 1024,
        }

        print(f"\n📊 Storage Projections (based on {kb_per_memory:.2f} KB/memory):")
        for label, mb in projections.items():
            if mb < 1:
                print(f"   {label}: {mb * 1024:.1f} KB")
            elif mb < 1024:
                print(f"   {label}: {mb:.1f} MB")
            else:
                print(f"   {label}: {mb / 1024:.2f} GB")
