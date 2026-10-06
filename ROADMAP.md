# Roadmap

Ideas and planned features for memable.

## Shipped (not originally on this roadmap)

- [x] **SQLite backend** (sqlite-vec) — #1
- [x] **DuckDB backend**
- [x] **Configurable LLM** for extraction and contradiction detection — #2
- [x] **Schema-based tenant isolation** for PostgreSQL — #3
- [x] **Audit fields, patch API, metadata filtering** — #5
- [x] **TypeScript package + MCP server** (local and hosted mode) — `packages/memable`
- [x] **Claude Code integration** (Stop hook, `extract-session`, project namespacing) — #6, #7

## Next — Batch & Async

- [ ] **Batch operations** — `add_many()`, `delete_many()`, `search_many()`
- [ ] **Async-first API** — Full async support (`async with build_postgres_store()`) _(partial: async LangGraph nodes, `aextract`, `acheck`; store is still sync)_
- [ ] **TTL auto-cleanup** — Background job to prune expired memories _(partial: `prune_expired` consolidation strategy exists; no background job)_

## Later — Knowledge Graph

- [ ] **Entity extraction** — Extract entities and relationships from memories
- [ ] **Relationship storage** — `Joel → works_at → Aclaimant` style triples
- [ ] **Graph queries** — "What do I know about Joel's work?"
- [ ] **Mem0-style API** — Compatibility layer for Mem0 users

## Later — Intelligence

- [ ] **Importance scoring** — Beyond confidence, track salience/relevance
- [ ] **Memory reflection** — Periodic self-review and insight generation
- [ ] **Conflict resolution UI** — Surface contradictions for human review
- [ ] **Memory provenance** — Track which conversation/source created each memory _(partial: `created_by`/`updated_by` audit fields + free-form `metadata`, #5)_

## Future / Maybe

- [ ] **Multi-modal memories** — Images, audio references
- [ ] **Memory sharing** — Cross-user or cross-agent memory access
- [ ] **Export/import** — Backup, migration, portability
- [ ] **Hooks/callbacks** — For logging, monitoring, custom logic
- [ ] **Rate limiting** — Built-in OpenAI call management
- [x] **Local embeddings** — No API needed (shipped via Ollama `nomic-embed-text`, not sentence-transformers)

## Docs Improvements

- [ ] **API reference** — Generated from docstrings
- [ ] **Architecture diagram** — How pieces fit together
- [ ] **More examples** — RAG chatbot, multi-agent, etc.
- [ ] **Deployment guide** — Scaling, monitoring, Neon best practices
- [ ] **Migration guide** — From Mem0, Zep, or raw vector stores

---

*Have ideas? Open an issue or PR!*
