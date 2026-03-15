# Roadmap

Ideas and planned features for memento-ai.

## v0.2.0 — Batch & Async

- [ ] **Batch operations** — `add_many()`, `delete_many()`, `search_many()`
- [ ] **Async-first API** — Full async support (`async with build_postgres_store()`)
- [ ] **TTL auto-cleanup** — Background job to prune expired memories

## v0.3.0 — Knowledge Graph

- [ ] **Entity extraction** — Extract entities and relationships from memories
- [ ] **Relationship storage** — `Joel → works_at → Aclaimant` style triples
- [ ] **Graph queries** — "What do I know about Joel's work?"
- [ ] **Mem0-style API** — Compatibility layer for Mem0 users

## v0.4.0 — Intelligence

- [ ] **Importance scoring** — Beyond confidence, track salience/relevance
- [ ] **Memory reflection** — Periodic self-review and insight generation
- [ ] **Conflict resolution UI** — Surface contradictions for human review
- [ ] **Memory provenance** — Track which conversation/source created each memory

## Future / Maybe

- [ ] **Multi-modal memories** — Images, audio references
- [ ] **Memory sharing** — Cross-user or cross-agent memory access
- [ ] **Export/import** — Backup, migration, portability
- [ ] **Hooks/callbacks** — For logging, monitoring, custom logic
- [ ] **Rate limiting** — Built-in OpenAI call management
- [ ] **Local embeddings** — Sentence-transformers fallback (no API needed)

## Docs Improvements

- [ ] **API reference** — Generated from docstrings
- [ ] **Architecture diagram** — How pieces fit together
- [ ] **More examples** — RAG chatbot, multi-agent, etc.
- [ ] **Deployment guide** — Scaling, monitoring, Neon best practices
- [ ] **Migration guide** — From Mem0, Zep, or raw vector stores

---

*Have ideas? Open an issue or PR!*
