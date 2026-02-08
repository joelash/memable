"""
Pytest fixtures for ai-semantic-memory tests.
"""

import os
from datetime import datetime
from uuid import uuid4

import pytest
from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv()

from engram_ai.schema import Durability, Memory, MemoryCreate, MemorySource  # noqa: E402

# ============================================================================
# Unit test fixtures (no external dependencies)
# ============================================================================


@pytest.fixture
def sample_memory() -> Memory:
    """A sample memory for testing."""
    return Memory(
        id=uuid4(),
        text="User prefers dark mode",
        durability=Durability.CORE,
        confidence=0.95,
        source=MemorySource.EXPLICIT,
    )


@pytest.fixture
def sample_memory_create() -> MemoryCreate:
    """A sample MemoryCreate for testing."""
    return MemoryCreate(
        text="User lives in Wheaton, IL",
        durability=Durability.CORE,
        confidence=0.9,
        source=MemorySource.EXPLICIT,
        tags=["location", "biographical"],
    )


@pytest.fixture
def sample_messages() -> list[dict]:
    """Sample conversation messages for extraction tests."""
    return [
        {"role": "user", "content": "Hi, I'm Joel and I live in Wheaton."},
        {"role": "assistant", "content": "Nice to meet you, Joel! How can I help you today?"},
        {"role": "user", "content": "I'm visiting my brother in Ohio this week."},
        {"role": "assistant", "content": "Enjoy your trip to Ohio!"},
    ]


@pytest.fixture
def memories_for_search() -> list[Memory]:
    """A set of memories for testing search and contradiction detection."""
    return [
        Memory(
            text="User's name is Joel",
            durability=Durability.CORE,
            confidence=0.95,
            source=MemorySource.EXPLICIT,
        ),
        Memory(
            text="User lives in Wheaton, IL",
            durability=Durability.CORE,
            confidence=0.9,
            source=MemorySource.EXPLICIT,
        ),
        Memory(
            text="User prefers TypeScript",
            durability=Durability.CORE,
            confidence=0.85,
            source=MemorySource.INFERRED,
        ),
        Memory(
            text="User is visiting brother in Ohio",
            durability=Durability.SITUATIONAL,
            confidence=0.9,
            source=MemorySource.EXPLICIT,
            valid_until=datetime(2026, 2, 13),
        ),
    ]


# ============================================================================
# Integration test fixtures (require Postgres)
# ============================================================================


@pytest.fixture(scope="session")
def postgres_container():
    """
    Start a PostgreSQL container for integration tests.

    If DATABASE_URL is set, skip container and use that directly.
    Otherwise, requires testcontainers[postgres] and Docker with pgvector image.

    Pull the image first:
        docker pull pgvector/pgvector:pg16
    """
    # If DATABASE_URL is set (e.g., in CI), skip container
    if os.environ.get("DATABASE_URL"):
        yield None
        return

    pytest.importorskip("testcontainers")

    from testcontainers.postgres import PostgresContainer

    try:
        with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as postgres:
            yield postgres
    except Exception as e:
        pytest.skip(f"Could not start Postgres container: {e}")


@pytest.fixture
def postgres_url(postgres_container) -> str:
    """Get the PostgreSQL connection URL from the container or env."""
    # Prefer DATABASE_URL from environment (CI)
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    url = postgres_container.get_connection_url()
    # Testcontainers returns SQLAlchemy-style URL (postgresql+psycopg://...)
    # but psycopg wants standard postgres URL (postgresql://...)
    return url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture
def semantic_store(postgres_url: str):
    """
    Create a SemanticMemoryStore connected to the test container.
    """
    # Skip if no OpenAI key (can't create embeddings)
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    from engram_ai.store import build_postgres_store

    with build_postgres_store(postgres_url) as store:
        store.setup()
        yield store


@pytest.fixture
def test_namespace() -> tuple[str, ...]:
    """A unique namespace for each test."""
    return (f"test_user_{uuid4().hex[:8]}", "memories")
