"""
Simple agent with semantic memory.

This example shows how to use ai-semantic-memory with LangGraph.

Requirements:
- PostgreSQL with pgvector (or use Neon)
- OPENAI_API_KEY environment variable
- DATABASE_URL environment variable

Run:
    pip install -e ../..
    python main.py
"""

import os

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

from engram_ai import build_postgres_store  # noqa: E402
from engram_ai.graph import build_memory_graph  # noqa: E402


def main():
    # Get database URL
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Example: postgresql://user:pass@host:5432/dbname")
        return

    # Create the memory store (context manager handles connection)
    print("Connecting to database...")
    with build_postgres_store(db_url) as store:
        store.setup()
        print("✓ Database ready")

        # Build the memory-enabled graph
        graph = build_memory_graph()
        compiled = graph.compile(store=store.raw_store)

        # Configuration with user ID
        config = {
            "configurable": {
                "user_id": "demo_user",
            }
        }

        print("\n" + "=" * 50)
        print("Semantic Memory Agent Demo")
        print("=" * 50)
        print("This agent remembers information across messages.")
        print("Try telling it facts about yourself, then ask what it knows.")
        print("Type 'quit' to exit.\n")

        while True:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in {"quit", "exit", "q"}:
                print("Goodbye!")
                break

            # Run the graph
            result = compiled.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
            )

            # Get the assistant's response
            messages = result.get("messages", [])
            if messages:
                last_msg = messages[-1]
                content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                print(f"Agent: {content}\n")


def demo_memories():
    """
    Demo showing direct memory operations.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        return

    from engram_ai import MemoryCreate
    from engram_ai.schema import Durability

    with build_postgres_store(db_url) as store:
        store.setup()

        user_id = "demo_user"
        namespace = store.namespace(user_id)

        print("\n" + "=" * 50)
        print("Memory Operations Demo")
        print("=" * 50)

        # Add some memories
        memories = [
            MemoryCreate(
                text="User's name is Demo User",
                durability=Durability.CORE,
                confidence=0.95,
            ),
            MemoryCreate(
                text="User prefers Python for backend development",
                durability=Durability.CORE,
                confidence=0.9,
            ),
            MemoryCreate(
                text="User is working on an AI project this week",
                durability=Durability.SITUATIONAL,
                confidence=0.85,
            ),
        ]

        print("\nAdding memories...")
        for mem in memories:
            stored = store.add(namespace, mem)
            print(f"  ✓ {stored.text[:50]}...")

        # Search for memories
        print("\nSearching for 'programming preferences'...")
        results = store.search(namespace, "programming preferences")
        for mem in results:
            print(f"  - {mem.text} (confidence: {mem.confidence:.0%})")

        # List all memories
        print(f"\nTotal memories for user: {store.count(namespace)}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo_memories()
    else:
        main()
