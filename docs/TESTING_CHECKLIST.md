# engram-ai Testing Checklist

Complete testing guide for Python library, TypeScript client, and MCP server.

---

## Prerequisites

- [ ] Neon database provisioned (or local Postgres with pgvector)
- [ ] `OPENAI_API_KEY` set in environment
- [ ] `DATABASE_URL` set to Postgres connection string

---

## 1. Python Library Tests

### Unit Tests (No DB Required)
```bash
cd ~/src/personal/engram-ai
source .venv/bin/activate
pytest tests/unit/ -v
```

**Expected:** 78+ tests passing

### Integration Tests (Requires Postgres + pgvector)
```bash
# Set DATABASE_URL first
export DATABASE_URL="postgresql://..."
pytest tests/integration/ -v
```

**Expected:** 19+ tests passing

### Full Test Suite
```bash
pytest tests/ -v
```

---

## 2. engram-ai-js TypeScript Tests

### Build Check
```bash
cd ~/src/personal/engram-ai/packages/engram-ai-js
pnpm install
pnpm build
```

**Expected:** Clean build, no TS errors

### Manual Integration Test

Create a test file `test-integration.ts`:

```typescript
import { MemoryStore, createOpenAIEmbeddings } from './src';
import { neon } from '@neondatabase/serverless';

async function test() {
  const sql = neon(process.env.DATABASE_URL!);
  const embeddings = createOpenAIEmbeddings(process.env.OPENAI_API_KEY!);
  
  const store = new MemoryStore(sql, embeddings);
  
  // 1. Setup (run migrations)
  await store.setup();
  console.log('✓ Setup complete');
  
  // 2. Add a memory
  const namespace = ['test', 'user_123'];
  const memory = await store.add(namespace, {
    text: 'User prefers dark mode',
    durability: 'core',
    memoryType: 'preference',
    confidence: 0.95,
    source: 'explicit',
  });
  console.log('✓ Memory added:', memory.key);
  
  // 3. Search for it
  const results = await store.search(namespace, 'user preferences');
  console.log('✓ Search results:', results.length);
  console.log('  First result:', results[0]?.value.text);
  
  // 4. Get by key
  const retrieved = await store.get(namespace, memory.key);
  console.log('✓ Get by key:', retrieved?.value.text);
  
  // 5. List all
  const all = await store.list(namespace);
  console.log('✓ List all:', all.length, 'memories');
  
  // 6. Delete
  await store.delete(namespace, memory.key);
  console.log('✓ Deleted');
  
  // 7. Verify deletion
  const afterDelete = await store.get(namespace, memory.key);
  console.log('✓ After delete:', afterDelete === null ? 'null (correct)' : 'STILL EXISTS (bug!)');
  
  console.log('\n✅ All tests passed!');
}

test().catch(console.error);
```

Run with:
```bash
npx tsx test-integration.ts
```

---

## 3. MCP Server Tests

### Build MCP Server
```bash
cd ~/src/personal/engram-ai/packages/engram-ai-js
pnpm build
```

### Test with MCP Inspector (if available)
```bash
npx @anthropic/mcp-inspector dist/mcp/index.js
```

### Manual Tool Tests

The MCP server exposes these tools:

| Tool | Description | Test |
|------|-------------|------|
| `remember` | Store a memory | Add "User is Joel" |
| `recall` | Semantic search | Search "who is the user" |
| `list_memories` | List recent memories | List last 10 |
| `forget` | Delete a memory | Delete by key |

---

## 4. ColorGenie Integration Test

### Setup
```bash
cd ~/src/personal/one_silly_app/colorGenie

# Add engram-ai-js as dependency
pnpm add file:../../engram-ai/packages/engram-ai-js

# Or link for development
pnpm link ../../engram-ai/packages/engram-ai-js
```

### Integration Points to Test

1. **Feedback storage** — When user submits feedback, store as memory
2. **Context retrieval** — Before generating, recall relevant memories
3. **Preference learning** — Track user color preferences over time

### Test Flow
```typescript
// In ColorGenie backend
import { MemoryStore, createOpenAIEmbeddings } from 'engram-ai-js';
import { neon } from '@neondatabase/serverless';

// During feedback submission
const store = new MemoryStore(sql, embeddings);
await store.add(['colorgenie', 'user', userId], {
  text: `User likes warm sunset colors for living room`,
  durability: 'situational',
  memoryType: 'preference',
  confidence: 0.8,
  source: 'inferred',
});

// Before generating
const prefs = await store.search(
  ['colorgenie', 'user', userId],
  `color preferences for ${roomType}`
);
// Inject into prompt
```

---

## 5. Schema Isolation Tests (PR #3)

### Setup Multiple Schemas
```sql
-- In Neon/Postgres
CREATE SCHEMA tenant_a;
CREATE SCHEMA tenant_b;
```

### Python Test
```python
from engram_ai import build_store, MemoryCreate

# Tenant A
with build_store("postgresql://...", schema="tenant_a") as store_a:
    store_a.setup()
    store_a.add(["test"], MemoryCreate(text="Tenant A data"))

# Tenant B
with build_store("postgresql://...", schema="tenant_b") as store_b:
    store_b.setup()
    store_b.add(["test"], MemoryCreate(text="Tenant B data"))

# Verify isolation - Tenant A shouldn't see Tenant B's data
with build_store("postgresql://...", schema="tenant_a") as store_a:
    results = store_a.search(["test"], "Tenant B")
    assert len(results) == 0  # Should not find Tenant B's data
```

---

## 6. Cross-Language Compatibility

### Test: Python writes, TypeScript reads

1. **Python: Add memory**
```python
from engram_ai import build_store, MemoryCreate

with build_store("postgresql://...") as store:
    store.setup()
    store.add(["shared", "user_123"], MemoryCreate(
        text="User's favorite color is blue",
        durability="core",
        memory_type="preference",
    ))
```

2. **TypeScript: Read it back**
```typescript
const results = await store.search(['shared', 'user_123'], 'favorite color');
console.log(results[0]?.value.text);
// Should output: "User's favorite color is blue"
```

---

## 7. Performance Baseline

### Run Performance Tests
```bash
cd ~/src/personal/engram-ai
pytest tests/performance/ -v -s
```

### Key Metrics to Track
- Embedding cost per memory
- Search latency (p50, p95)
- Storage growth per 1K memories

---

## Known Issues / Gotchas

1. **pgvector extension** — Must be enabled in Postgres: `CREATE EXTENSION vector;`
2. **Schema must exist** — For multi-tenant, create schema before calling `setup()`
3. **Neon serverless** — Use `@neondatabase/serverless` driver, not `pg`
4. **Embedding dimensions** — Default is 1536 (text-embedding-3-small). Must match across clients.

---

## CI/CD Status

- **GitHub Actions:** `.github/workflows/ci.yml`
- **Runs on:** Push to main, PRs
- **Services:** PostgreSQL 15 with pgvector

Check status: https://github.com/joelash/engram-ai/actions

---

## Deployment Options for Landing Page

| Option | Pros | Cons |
|--------|------|------|
| **GitHub Pages** | Free, auto-deploy | Repo must be public |
| **Vercel** | Free tier, works with private repos | Another account |
| **Cloudflare Pages** | Free, fast CDN | Another account |
| **Netlify** | Free tier, drag-drop deploy | Another account |

### Recommended: Vercel (quickest)
```bash
cd ~/src/personal/engram-ai/site
npx vercel
```

Or drag-drop `site/` folder to [vercel.com/new](https://vercel.com/new)

---

*Last updated: 2026-03-14*
