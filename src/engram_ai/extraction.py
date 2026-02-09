"""
Memory extraction from conversations using LLM.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from engram_ai.schema import Durability, MemoryCreate, MemorySource

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

# Default extraction model
DEFAULT_MODEL = "gpt-4.1-mini"


class ExtractedFact(BaseModel):
    """A fact extracted from conversation."""

    text: str
    """The fact content."""

    durability: Durability
    """Suggested durability tier."""

    confidence: float = Field(ge=0.0, le=1.0)
    """Confidence in this extraction (0-1)."""

    valid_days: int | None = None
    """For situational facts, how many days until expiry."""

    category: str | None = None
    """Optional category (preference, biographical, project, etc.)."""

    reasoning: str | None = None
    """Why this was extracted (for debugging)."""


class ExtractionResult(BaseModel):
    """Result of memory extraction."""

    facts: list[ExtractedFact] = Field(default_factory=list)
    """Extracted facts."""


EXTRACTION_SYSTEM_PROMPT = """\
You are a memory extraction system. Your job is to identify facts from conversations
that should be stored as long-term memories.

Extract facts that are:
- About the user (preferences, biographical info, opinions, projects)
- Stable enough to be useful later
- Not just transient conversation (greetings, acknowledgments)

For each fact, classify its durability:
- "core": Stable facts that rarely change (name, location, job, strong preferences)
- "situational": Temporary context with a natural end (trips, projects, temporary states)
- "episodic": Things that happened or were discussed (meetings, decisions, events)

For situational facts, estimate how many days until they expire (valid_days).

Return a JSON object with this structure:
{
  "facts": [
    {
      "text": "User's name is Joel",
      "durability": "core",
      "confidence": 0.95,
      "valid_days": null,
      "category": "biographical",
      "reasoning": "Explicit self-identification"
    },
    {
      "text": "User is visiting brother in Ohio this week",
      "durability": "situational",
      "confidence": 0.9,
      "valid_days": 7,
      "category": "travel",
      "reasoning": "Temporary travel context with implicit duration"
    }
  ]
}

If there are no facts worth storing, return: {"facts": []}

Be selective. Not every conversation needs memories extracted.
"""


class MemoryExtractor:
    """
    Extracts memorable facts from conversations using an LLM.

    Handles:
    - Durability classification (core/situational/episodic)
    - Confidence scoring
    - Temporal estimation for situational facts
    - Category tagging
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        llm: "BaseChatModel | None" = None,
    ):
        """
        Initialize the extractor.

        Args:
            model: OpenAI model name (only used if llm not provided).
            llm: LangChain chat model. If None, uses ChatOpenAI.

        Examples:
            # Default (OpenAI)
            extractor = MemoryExtractor()

            # AWS Bedrock
            from langchain_aws import ChatBedrock
            extractor = MemoryExtractor(llm=ChatBedrock(model_id="anthropic.claude-3-5-sonnet..."))

            # Anthropic direct
            from langchain_anthropic import ChatAnthropic
            extractor = MemoryExtractor(llm=ChatAnthropic(model="claude-3-5-sonnet-20241022"))

            # Via AI Gateway
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4.1-mini", base_url="https://gateway.ai.cloudflare.com/v1/...")
            extractor = MemoryExtractor(llm=llm)
        """
        if llm is not None:
            self.llm = llm
        else:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model=model, temperature=0)

    def extract(
        self,
        messages: list[dict[str, Any]] | list[BaseMessage],
        context: str | None = None,
    ) -> list[MemoryCreate]:
        """
        Extract memorable facts from a conversation.

        Args:
            messages: Conversation messages (dicts or LangChain messages).
            context: Optional additional context about the user/situation.

        Returns:
            List of MemoryCreate objects ready to store.
        """
        # Format messages for the prompt
        formatted = self._format_messages(messages)

        user_prompt = f"Extract memories from this conversation:\n\n{formatted}"
        if context:
            user_prompt += f"\n\nAdditional context:\n{context}"

        extraction_messages = [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(extraction_messages)
        content = response.content if isinstance(response.content, str) else str(response.content)

        # Parse JSON response
        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = ExtractionResult.model_validate(json.loads(content.strip()))
        except (json.JSONDecodeError, ValueError):
            # Failed to parse, return empty
            return []

        # Convert to MemoryCreate objects
        return self._to_memory_creates(result.facts)

    async def aextract(
        self,
        messages: list[dict[str, Any]] | list[BaseMessage],
        context: str | None = None,
    ) -> list[MemoryCreate]:
        """Async version of extract."""
        formatted = self._format_messages(messages)

        user_prompt = f"Extract memories from this conversation:\n\n{formatted}"
        if context:
            user_prompt += f"\n\nAdditional context:\n{context}"

        extraction_messages = [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = await self.llm.ainvoke(extraction_messages)
        content = response.content if isinstance(response.content, str) else str(response.content)

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = ExtractionResult.model_validate(json.loads(content.strip()))
        except (json.JSONDecodeError, ValueError):
            return []

        return self._to_memory_creates(result.facts)

    def _format_messages(
        self,
        messages: list[dict[str, Any]] | list[BaseMessage],
    ) -> str:
        """Format messages into a readable string for the LLM."""
        lines = []
        for msg in messages:
            if isinstance(msg, BaseMessage):
                role = msg.type.upper()
                content = msg.content
            else:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _to_memory_creates(self, facts: list[ExtractedFact]) -> list[MemoryCreate]:
        """Convert extracted facts to MemoryCreate objects."""
        creates: list[MemoryCreate] = []

        for fact in facts:
            valid_until = None
            if fact.valid_days is not None:
                valid_until = datetime.now(UTC) + timedelta(days=fact.valid_days)

            tags = []
            if fact.category:
                tags.append(fact.category)

            creates.append(
                MemoryCreate(
                    text=fact.text,
                    durability=fact.durability,
                    confidence=fact.confidence,
                    source=MemorySource.INFERRED,
                    valid_until=valid_until,
                    tags=tags,
                    metadata={
                        "extraction_reasoning": fact.reasoning,
                    },
                )
            )

        return creates


# Convenience function
def extract_memories(
    messages: list[dict[str, Any]] | list[BaseMessage],
    model: str = DEFAULT_MODEL,
    llm: "BaseChatModel | None" = None,
    context: str | None = None,
) -> list[MemoryCreate]:
    """
    Extract memories from a conversation (convenience function).

    Args:
        messages: Conversation messages.
        model: OpenAI model to use (only if llm not provided).
        llm: LangChain chat model. If None, uses ChatOpenAI.
        context: Optional additional context.

    Returns:
        List of MemoryCreate objects.

    Examples:
        # Default (OpenAI)
        memories = extract_memories(messages)

        # With custom LLM (AWS Bedrock)
        from langchain_aws import ChatBedrock
        llm = ChatBedrock(model_id="anthropic.claude-3-5-sonnet...")
        memories = extract_memories(messages, llm=llm)
    """
    extractor = MemoryExtractor(model=model, llm=llm)
    return extractor.extract(messages, context=context)
