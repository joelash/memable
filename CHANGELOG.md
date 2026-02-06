# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-06

### Added
- Memory schema with durability tiers (core/situational/episodic)
- Version chains for contradiction handling with full audit trail
- Temporal validity (valid_from/valid_until) for time-bounded memories
- PostgresStore wrapper with semantic search via pgvector
- LLM-based memory extraction with automatic durability classification
- Contradiction detection and resolution
- Memory consolidation strategies (prune, decay, summarize, dedupe)
- LangGraph nodes (retrieve_memories, store_memories, consolidate_memories)
- Pre-built memory graph for quick integration
- Example app with Neon integration
