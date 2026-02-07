"""
engram-ai Demo API

FastAPI backend for the memory demo.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from engram_ai import MemoryCreate, build_postgres_store
from engram_ai.extraction import MemoryExtractor
from engram_ai.schema import Durability, Memory

load_dotenv()

# Global store reference (managed by lifespan)
store = None
store_context = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection lifecycle."""
    global store, store_context
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    
    store_context = build_postgres_store(db_url)
    store = store_context.__enter__()
    store.setup()
    
    yield
    
    store_context.__exit__(None, None, None)


app = FastAPI(title="engram-ai Demo", lifespan=lifespan)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LLM for chat
llm = ChatOpenAI(model="gpt-4.1-mini")
extractor = MemoryExtractor()

# Demo user namespace
USER_ID = "demo_user"
NAMESPACE = (USER_ID, "memories")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    memories_used: list[dict]
    memories_created: list[dict]


class MemoryResponse(BaseModel):
    id: str
    text: str
    durability: str
    confidence: float
    created_at: str
    superseded_by: str | None = None


@app.get("/")
def root():
    return {"status": "ok", "service": "engram-ai demo"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Send a message and get a response with memory context."""
    
    # 1. Retrieve relevant memories
    memories = store.search(NAMESPACE, req.message)
    memories_used = [_memory_to_dict(m) for m in memories[:5]]
    
    # 2. Build context
    memory_context = ""
    if memories:
        memory_lines = [f"- {m.text}" for m in memories[:5]]
        memory_context = "What you know about the user:\n" + "\n".join(memory_lines)
    
    # 3. Chat with LLM
    system = f"""You are a helpful assistant with long-term memory.
Use your memories about the user when relevant. Be conversational and friendly.

{memory_context}"""
    
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": req.message},
    ]
    
    response = llm.invoke(messages)
    assistant_msg = response.content
    
    # 4. Extract and store new memories
    convo = [
        {"role": "user", "content": req.message},
        {"role": "assistant", "content": assistant_msg},
    ]
    
    extracted = extractor.extract(convo)
    memories_created = []
    
    for mem_create in extracted:
        # Check for contradictions (simple version - just add for now)
        stored = store.add(NAMESPACE, mem_create)
        memories_created.append(_memory_to_dict(stored))
    
    return ChatResponse(
        response=assistant_msg,
        memories_used=memories_used,
        memories_created=memories_created,
    )


@app.get("/memories", response_model=list[MemoryResponse])
def list_memories():
    """Get all current memories."""
    memories = store.list_all(NAMESPACE, include_superseded=False)
    return [_memory_to_dict(m) for m in memories]


@app.get("/memories/history", response_model=list[MemoryResponse])
def list_all_memories():
    """Get all memories including superseded (version history)."""
    memories = store.list_all(NAMESPACE, include_superseded=True)
    return [_memory_to_dict(m) for m in memories]


@app.delete("/memories")
def clear_memories():
    """Clear all memories (reset demo)."""
    memories = store.list_all(NAMESPACE, include_superseded=True)
    for mem in memories:
        store.delete(NAMESPACE, mem.id)
    return {"deleted": len(memories)}


@app.get("/memories/{memory_id}/history")
def get_memory_history(memory_id: str):
    """Get version history for a specific memory."""
    history = store.get_version_history(NAMESPACE, memory_id)
    return [_memory_to_dict(m) for m in history]


def _memory_to_dict(m: Memory) -> dict:
    return {
        "id": str(m.id),
        "text": m.text,
        "durability": m.durability.value,
        "confidence": m.confidence,
        "created_at": m.created_at.isoformat(),
        "superseded_by": str(m.superseded_by) if m.superseded_by else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
