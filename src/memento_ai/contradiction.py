"""
Contradiction detection and resolution via version chains.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from memento_ai.schema import Memory, MemorySource, MemoryUpdate
from memento_ai.store import SemanticMemoryStore

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

DEFAULT_MODEL = "gpt-4.1-mini"


class ContradictionCheck(BaseModel):
    """Result of checking for contradictions."""

    has_contradiction: bool
    """Whether a contradiction was detected."""

    contradicted_memory_id: str | None = None
    """ID of the existing memory that is contradicted."""

    contradicted_text: str | None = None
    """Text of the contradicted memory."""

    explanation: str | None = None
    """Why this is considered a contradiction."""

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Confidence that this is truly a contradiction."""


CONTRADICTION_PROMPT = """\
You are checking if a new fact contradicts any existing memories.

A contradiction exists when:
- The new fact directly negates an old fact (e.g., "lives in Austin" vs "lives in Wheaton")
- The new fact makes an old fact obsolete (e.g., "now uses TypeScript" vs "prefers Python")
- The new fact updates information that can only have one value (e.g., job, name, location)

NOT contradictions:
- Additional facts that complement existing ones
- Facts about different topics
- Facts that could coexist (e.g., "likes Python" and "likes TypeScript" can both be true)

Existing memories:
{memories}

New fact to check:
{new_fact}

Respond with JSON:
{{
  "has_contradiction": true/false,
  "contradicted_memory_id": "uuid if contradiction" or null,
  "contradicted_text": "text of contradicted memory" or null,
  "explanation": "why this is a contradiction" or null,
  "confidence": 0.0-1.0
}}
"""


class ContradictionDetector:
    """
    Detects contradictions between new memories and existing ones.

    Uses LLM to semantically understand whether a new fact
    contradicts or supersedes existing memories.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        llm: "BaseChatModel | None" = None,
    ):
        """
        Initialize the detector.

        Args:
            model: OpenAI model name (only used if llm not provided).
            llm: LangChain chat model. If None, uses ChatOpenAI.

        Examples:
            # Default (OpenAI)
            detector = ContradictionDetector()

            # AWS Bedrock
            from langchain_aws import ChatBedrock
            llm = ChatBedrock(model_id="anthropic.claude-3-5-sonnet...")
            detector = ContradictionDetector(llm=llm)
        """
        if llm is not None:
            self.llm = llm
        else:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model=model, temperature=0)

    def check(
        self,
        new_fact: str,
        existing_memories: list[Memory],
    ) -> ContradictionCheck:
        """
        Check if a new fact contradicts any existing memories.

        Args:
            new_fact: The new fact to check.
            existing_memories: List of existing memories to check against.

        Returns:
            ContradictionCheck with details if contradiction found.
        """
        if not existing_memories:
            return ContradictionCheck(has_contradiction=False)

        # Format existing memories for the prompt
        mem_lines = []
        for mem in existing_memories:
            mem_lines.append(f"- [{mem.id}] {mem.text}")
        memories_str = "\n".join(mem_lines)

        prompt = CONTRADICTION_PROMPT.format(
            memories=memories_str,
            new_fact=new_fact,
        )

        response = self.llm.invoke([
            SystemMessage(content="You are a contradiction detection system."),
            HumanMessage(content=prompt),
        ])

        content = response.content if isinstance(response.content, str) else str(response.content)

        # Parse response
        try:
            import json

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            return ContradictionCheck.model_validate(data)
        except Exception:
            return ContradictionCheck(has_contradiction=False)

    async def acheck(
        self,
        new_fact: str,
        existing_memories: list[Memory],
    ) -> ContradictionCheck:
        """Async version of check."""
        if not existing_memories:
            return ContradictionCheck(has_contradiction=False)

        mem_lines = []
        for mem in existing_memories:
            mem_lines.append(f"- [{mem.id}] {mem.text}")
        memories_str = "\n".join(mem_lines)

        prompt = CONTRADICTION_PROMPT.format(
            memories=memories_str,
            new_fact=new_fact,
        )

        response = await self.llm.ainvoke([
            SystemMessage(content="You are a contradiction detection system."),
            HumanMessage(content=prompt),
        ])

        content = response.content if isinstance(response.content, str) else str(response.content)

        try:
            import json

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            return ContradictionCheck.model_validate(data)
        except Exception:
            return ContradictionCheck(has_contradiction=False)


def resolve_contradiction(
    store: SemanticMemoryStore,
    namespace: tuple[str, ...],
    new_fact: str,
    contradicted_memory_id: str,
    confidence: float = 0.9,
    source: MemorySource = MemorySource.INFERRED,
) -> Memory:
    """
    Resolve a contradiction by creating a version chain.

    The old memory is marked as superseded; a new memory is created
    as the current version.

    Args:
        store: SemanticMemoryStore instance.
        namespace: Memory namespace.
        new_fact: The new fact text.
        contradicted_memory_id: ID of the memory being superseded.
        confidence: Confidence in the new fact.
        source: Source of the new fact.

    Returns:
        The new Memory (current version).
    """
    return store.update(
        namespace=namespace,
        memory_id=contradicted_memory_id,
        update=MemoryUpdate(
            text=new_fact,
            confidence=confidence,
            source=source,
            valid_from=datetime.now(UTC),
        ),
    )


def add_memory_with_contradiction_check(
    store: SemanticMemoryStore,
    namespace: tuple[str, ...],
    new_fact: str,
    confidence: float = 0.9,
    source: MemorySource = MemorySource.INFERRED,
    detector: ContradictionDetector | None = None,
    search_limit: int = 20,
) -> tuple[Memory, ContradictionCheck | None]:
    """
    Add a memory, automatically detecting and resolving contradictions.

    This is the recommended way to add memories when you want
    automatic contradiction handling with version chains.

    Args:
        store: SemanticMemoryStore instance.
        namespace: Memory namespace.
        new_fact: The fact to store.
        confidence: Confidence in the fact.
        source: Source of the fact.
        detector: Optional ContradictionDetector (creates one if not provided).
        search_limit: How many existing memories to check for contradictions.

    Returns:
        Tuple of (created Memory, ContradictionCheck if contradiction was resolved).
    """
    from memento_ai.schema import MemoryCreate

    detector = detector or ContradictionDetector()

    # Search for potentially related memories
    existing = store.search(namespace, new_fact)[:search_limit]

    # Check for contradictions
    check = detector.check(new_fact, existing)

    if check.has_contradiction and check.contradicted_memory_id:
        # Resolve via version chain
        memory = resolve_contradiction(
            store=store,
            namespace=namespace,
            new_fact=new_fact,
            contradicted_memory_id=check.contradicted_memory_id,
            confidence=confidence,
            source=source,
        )
        return memory, check

    # No contradiction, just add
    memory = store.add(
        namespace=namespace,
        memory=MemoryCreate(
            text=new_fact,
            confidence=confidence,
            source=source,
        ),
    )
    return memory, None
