# memento-ai Demo

Interactive demo with chat interface and live memory visualization.

## Quick Start

### 1. Backend

```bash
cd backend

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install deps (including memento-ai from parent)
pip install fastapi uvicorn python-dotenv
pip install -e ../..

# Set up env
cp ../../examples/simple_agent/.env .env
# Or create .env with:
# DATABASE_URL=postgresql://...
# OPENAI_API_KEY=sk-...

# Run
python main.py
# or: uvicorn main:app --reload
```

Backend runs at http://localhost:8000

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173

## Features

- **Chat interface** — Talk to an AI that remembers you
- **Memory panel** — See what it knows (live updating)
- **Version history** — Toggle to see superseded memories
- **Durability tags** — Core (purple), situational (blue), episodic (gray)
- **Clear button** — Reset all memories

## Screenshot

```
┌─────────────────────────────────────────────────────┐
│  🧠 memento-ai demo                      [Clear]     │
├─────────────────────────┬───────────────────────────┤
│                         │  🧠 Memories (3)          │
│  You: I'm Joel          │  ┌─────────────────────┐  │
│                         │  │ User's name is Joel │  │
│  AI: Nice to meet you,  │  │ [core] 95%          │  │
│      Joel!              │  └─────────────────────┘  │
│                         │  ┌─────────────────────┐  │
│  You: I work at Acme    │  │ Works at Acme Corp  │  │
│                         │  │ [core] 90%          │  │
│  AI: Cool! What do you  │  └─────────────────────┘  │
│      do there?          │                           │
│                         │                           │
├─────────────────────────┴───────────────────────────┤
│  [Type a message...]                         [Send] │
└─────────────────────────────────────────────────────┘
```
