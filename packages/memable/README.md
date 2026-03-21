# memento-ai (TypeScript)

Long-term semantic memory for AI agents. TypeScript implementation compatible with Python [memento-ai](https://github.com/joelash/memento-ai).

## Features

- **Zero-config MCP** — just `npx memento-ai-mcp` with Claude Desktop/Cursor
- **SQLite local storage** — no database setup required
- **Postgres support** — scale up when you need it
- **Semantic search** — find memories by meaning, not keywords
- **Durability tiers** — core facts vs situational context vs episodic memories
- **Version chains** — audit trail for memory updates
- **Cross-language** — shares schema with Python memento-ai

## Quick Start: MCP Server

Add memory to Claude Desktop, Cursor, or any MCP tool — **zero config**:

```json
{
  "mcpServers": {
    "memento": {
      "command": "npx",
      "args": ["memento-ai-mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

That's it! Memories are stored locally in `~/.memento/memories.db`.

### MCP with Postgres (optional)

For cloud sync or multi-device, add `DATABASE_URL`:

```json
{
  "mcpServers": {
    "memento": {
      "command": "npx",
      "args": ["memento-ai-mcp"],
      "env": {
        "DATABASE_URL": "postgresql://...",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `boot` | Load memory context at session start — call this first! |
| `remember` | Store a new memory |
| `recall` | Search memories by semantic similarity |
| `extract` | Auto-extract memories from conversation text |
| `list_memories` | List all memories with optional filters |
| `forget` | Delete a memory by ID |

### Recommended System Prompt

Add this to your Claude Desktop / Cursor system prompt for best results:

```
You have access to a memory system. Use your MCP tools:
- Call "boot" at the start of every conversation to load what you know
- Use "remember" to store facts, preferences, or decisions the user shares
- Use "recall" to search memories before answering personal questions
- Use "extract" to capture multiple memories from a conversation

Be proactive — if the user tells you something worth remembering, store it without being asked.
```

The `boot` tool returns:
- **Core memories** — permanent facts (always loaded)
- **Recent memories** — things learned in the last 24 hours
- **Contextual memories** — relevant to what you're discussing (if context provided)

## Installation

```bash
npm install memento-ai
# or
pnpm add memento-ai
```

## Programmatic Usage

### SQLite (Zero Config)

```typescript
import { SQLiteMemoryStore, openaiEmbeddings, Durability, MemoryType } from 'memento-ai';

const store = new SQLiteMemoryStore({
  embeddings: openaiEmbeddings({ apiKey: process.env.OPENAI_API_KEY }),
  // dbPath: '~/.memento/memories.db'  // optional, this is the default
});

await store.setup();

// Add a memory
await store.add(['user_123', 'preferences'], {
  text: 'User prefers dark mode',
  durability: Durability.CORE,
  memoryType: MemoryType.PREFERENCE,
});

// Search memories
const memories = await store.search(['user_123', 'preferences'], {
  query: 'UI settings',
  limit: 5,
});

// Don't forget to close
store.close();
```

### Postgres (Neon Serverless)

```typescript
import { neon } from '@neondatabase/serverless';
import { MemoryStore, openaiEmbeddings, Durability, MemoryType } from 'memento-ai';

const sql = neon(process.env.DATABASE_URL!);
const store = new MemoryStore({
  sql,
  embeddings: openaiEmbeddings({ apiKey: process.env.OPENAI_API_KEY }),
});

await store.setup();

// Same API as SQLite
await store.add(['user_123'], {
  text: 'User prefers dark mode',
  durability: Durability.CORE,
});
```

## Embeddings Providers

```typescript
// OpenAI (default)
import { openaiEmbeddings } from 'memento-ai';
const embeddings = openaiEmbeddings();

// Via Helicone (observability)
import { heliconeEmbeddings } from 'memento-ai';
const embeddings = heliconeEmbeddings({
  heliconeKey: process.env.HELICONE_API_KEY!,
});

// Custom provider
const embeddings: EmbeddingsProvider = {
  dimensions: 1536,
  async embed(texts) {
    // Your implementation
    return texts.map(() => new Array(1536).fill(0));
  },
};
```

## Schema

Memories have the following structure:

```typescript
interface Memory {
  id: string;
  text: string;
  durability: 'core' | 'situational' | 'episodic';
  memoryType?: 'fact' | 'rule' | 'decision' | 'preference' | 'context' | 'observation';
  confidence: number;
  source: 'explicit' | 'inferred' | 'system';
  validFrom: Date;
  validUntil?: Date;
  supersedes?: string;      // Previous version ID
  supersededBy?: string;    // Next version ID
  tags: string[];
  metadata: Record<string, unknown>;
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Required for embeddings | — |
| `DATABASE_URL` | Postgres connection (optional) | Uses SQLite |
| `ENGRAM_DB_PATH` | Custom SQLite path | `~/.memento/memories.db` |
| `ENGRAM_NAMESPACE` | Default namespace (comma-separated) | `default` |

## Cross-Language Compatibility

This package uses the same database schema as Python memento-ai. You can:

- Write memories from Python, read from TypeScript
- Share a database between Python and TypeScript services
- Migrate between languages without data changes

## License

MIT
