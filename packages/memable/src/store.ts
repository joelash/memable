/**
 * Memory store implementations for different database drivers.
 */

import { v4 as uuidv4 } from 'uuid';
import {
  Durability,
  Memory,
  MemoryCreate,
  MemoryQuery,
  MemorySource,
  MemoryUpdate,
  Namespace,
  isMemoryCurrent,
  isMemoryValid,
} from './schema.js';

/**
 * Embeddings provider interface.
 */
export interface EmbeddingsProvider {
  /** Generate embeddings for the given texts. */
  embed(texts: string[]): Promise<number[][]>;
  /** Embedding dimensions. */
  dimensions: number;
}

/**
 * SQL executor interface - compatible with pg, @neondatabase/serverless, etc.
 */
export interface SqlExecutor {
  <T extends Record<string, unknown>>(
    strings: TemplateStringsArray,
    ...values: unknown[]
  ): Promise<T[]>;
}

/**
 * Configuration for MemoryStore.
 */
export interface MemoryStoreConfig {
  /** SQL executor (neon() or pg pool.query). */
  sql: SqlExecutor;
  /** Embeddings provider for semantic search. */
  embeddings: EmbeddingsProvider;
  /** Table name prefix (default: 'engram'). */
  tablePrefix?: string;
}

/**
 * Memory store with semantic search and version chains.
 * 
 * Compatible with Python engram-ai schema for cross-language use.
 */
export class MemoryStore {
  private sql: SqlExecutor;
  private embeddings: EmbeddingsProvider;
  private tablePrefix: string;

  constructor(config: MemoryStoreConfig) {
    this.sql = config.sql;
    this.embeddings = config.embeddings;
    this.tablePrefix = config.tablePrefix ?? 'engram';
  }

  private get tableName(): string {
    return `${this.tablePrefix}_memories`;
  }

  /**
   * Create tables and indexes. Call once at startup.
   */
  async setup(): Promise<void> {
    // Create pgvector extension if not exists
    await this.sql`CREATE EXTENSION IF NOT EXISTS vector`;

    // Create memories table
    await this.sql`
      CREATE TABLE IF NOT EXISTS ${this.sql`${this.tableName}`} (
        id UUID PRIMARY KEY,
        namespace TEXT[] NOT NULL,
        text TEXT NOT NULL,
        durability VARCHAR(20) NOT NULL DEFAULT 'episodic',
        memory_type VARCHAR(20),
        confidence REAL NOT NULL DEFAULT 0.8,
        source VARCHAR(20) NOT NULL DEFAULT 'inferred',
        valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        valid_until TIMESTAMPTZ,
        supersedes UUID,
        superseded_by UUID,
        superseded_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_accessed_at TIMESTAMPTZ,
        access_count INTEGER NOT NULL DEFAULT 0,
        tags TEXT[] NOT NULL DEFAULT '{}',
        metadata JSONB NOT NULL DEFAULT '{}',
        embedding vector(${this.embeddings.dimensions})
      )
    `;

    // Create indexes
    await this.sql`
      CREATE INDEX IF NOT EXISTS ${this.sql`idx_${this.tableName}_namespace`}
      ON ${this.sql`${this.tableName}`} USING GIN (namespace)
    `;

    await this.sql`
      CREATE INDEX IF NOT EXISTS ${this.sql`idx_${this.tableName}_embedding`}
      ON ${this.sql`${this.tableName}`} 
      USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100)
    `;
  }

  /**
   * Add a new memory.
   */
  async add(namespace: Namespace, input: MemoryCreate): Promise<Memory> {
    const id = uuidv4();
    const now = new Date();

    const memory: Memory = {
      id,
      text: input.text,
      durability: input.durability ?? Durability.EPISODIC,
      memoryType: input.memoryType ?? null,
      confidence: input.confidence ?? 0.8,
      source: input.source ?? MemorySource.INFERRED,
      validFrom: input.validFrom ?? now,
      validUntil: input.validUntil ?? null,
      supersedes: null,
      supersededBy: null,
      supersededAt: null,
      createdAt: now,
      lastAccessedAt: null,
      accessCount: 0,
      tags: input.tags ?? [],
      metadata: input.metadata ?? {},
    };

    // Generate embedding
    const [embedding] = await this.embeddings.embed([memory.text]);

    await this.sql`
      INSERT INTO ${this.sql`${this.tableName}`} (
        id, namespace, text, durability, memory_type, confidence, source,
        valid_from, valid_until, supersedes, superseded_by, superseded_at,
        created_at, last_accessed_at, access_count, tags, metadata, embedding
      ) VALUES (
        ${id}::uuid,
        ${namespace},
        ${memory.text},
        ${memory.durability},
        ${memory.memoryType},
        ${memory.confidence},
        ${memory.source},
        ${memory.validFrom.toISOString()},
        ${memory.validUntil?.toISOString() ?? null},
        ${memory.supersedes}::uuid,
        ${memory.supersededBy}::uuid,
        ${memory.supersededAt?.toISOString() ?? null},
        ${memory.createdAt.toISOString()},
        ${memory.lastAccessedAt?.toISOString() ?? null},
        ${memory.accessCount},
        ${memory.tags},
        ${JSON.stringify(memory.metadata)},
        ${JSON.stringify(embedding)}::vector
      )
    `;

    return memory;
  }

  /**
   * Get a memory by ID.
   */
  async get(namespace: Namespace, id: string): Promise<Memory | null> {
    const rows = await this.sql<MemoryRow>`
      SELECT * FROM ${this.sql`${this.tableName}`}
      WHERE id = ${id}::uuid AND namespace = ${namespace}
      LIMIT 1
    `;

    if (rows.length === 0) return null;
    return this.rowToMemory(rows[0]);
  }

  /**
   * Update a memory by creating a new version (version chain).
   */
  async update(
    namespace: Namespace,
    id: string,
    update: MemoryUpdate
  ): Promise<Memory> {
    const oldMemory = await this.get(namespace, id);
    if (!oldMemory) {
      throw new Error(`Memory ${id} not found`);
    }

    // Create new version
    const newMemory = await this.add(namespace, {
      text: update.text,
      durability: oldMemory.durability,
      confidence: update.confidence ?? 0.9,
      source: update.source ?? MemorySource.EXPLICIT,
      validFrom: update.validFrom,
      validUntil: update.validUntil,
      tags: oldMemory.tags,
      metadata: { ...oldMemory.metadata, previousVersion: oldMemory.id },
    });

    // Mark old memory as superseded
    const now = new Date();
    await this.sql`
      UPDATE ${this.sql`${this.tableName}`}
      SET 
        superseded_by = ${newMemory.id}::uuid,
        superseded_at = ${now.toISOString()}
      WHERE id = ${id}::uuid AND namespace = ${namespace}
    `;

    // Update new memory with supersedes reference
    await this.sql`
      UPDATE ${this.sql`${this.tableName}`}
      SET supersedes = ${id}::uuid
      WHERE id = ${newMemory.id}::uuid
    `;

    return { ...newMemory, supersedes: id };
  }

  /**
   * Delete a memory.
   */
  async delete(namespace: Namespace, id: string): Promise<boolean> {
    const result = await this.sql`
      DELETE FROM ${this.sql`${this.tableName}`}
      WHERE id = ${id}::uuid AND namespace = ${namespace}
    `;
    return (result as any).count > 0;
  }

  /**
   * Semantic search for memories.
   */
  async search(namespace: Namespace, query: MemoryQuery): Promise<Memory[]> {
    // Generate query embedding
    const [queryEmbedding] = await this.embeddings.embed([query.query]);
    const limit = query.limit ?? 10;
    const checkTime = query.validAt ?? new Date();

    // Search with cosine similarity
    const rows = await this.sql<MemoryRow & { similarity: number }>`
      SELECT *, 
        1 - (embedding <=> ${JSON.stringify(queryEmbedding)}::vector) as similarity
      FROM ${this.sql`${this.tableName}`}
      WHERE namespace = ${namespace}
      ORDER BY embedding <=> ${JSON.stringify(queryEmbedding)}::vector
      LIMIT ${limit * 2}
    `;

    // Apply filters in JS (more flexible than SQL)
    const memories: Memory[] = [];
    for (const row of rows) {
      const memory = this.rowToMemory(row);

      if (!query.includeSuperseded && !isMemoryCurrent(memory)) {
        continue;
      }

      if (!query.includeExpired && !isMemoryValid(memory, checkTime)) {
        continue;
      }

      if (query.minConfidence && memory.confidence < query.minConfidence) {
        continue;
      }

      if (query.durability && !query.durability.includes(memory.durability)) {
        continue;
      }

      if (
        query.memoryType &&
        (!memory.memoryType || !query.memoryType.includes(memory.memoryType))
      ) {
        continue;
      }

      if (query.tags && !query.tags.some((t) => memory.tags.includes(t))) {
        continue;
      }

      memories.push(memory);

      if (memories.length >= limit) {
        break;
      }
    }

    return memories;
  }

  /**
   * List all memories in a namespace.
   */
  async listAll(
    namespace: Namespace,
    options?: { includeSuperseded?: boolean; includeExpired?: boolean }
  ): Promise<Memory[]> {
    const rows = await this.sql<MemoryRow>`
      SELECT * FROM ${this.sql`${this.tableName}`}
      WHERE namespace = ${namespace}
      ORDER BY created_at DESC
    `;

    const now = new Date();
    return rows
      .map((row) => this.rowToMemory(row))
      .filter((memory) => {
        if (!options?.includeSuperseded && !isMemoryCurrent(memory)) {
          return false;
        }
        if (!options?.includeExpired && !isMemoryValid(memory, now)) {
          return false;
        }
        return true;
      });
  }

  /**
   * Convert database row to Memory object.
   */
  private rowToMemory(row: MemoryRow): Memory {
    return {
      id: row.id,
      text: row.text,
      durability: row.durability as Durability,
      memoryType: row.memory_type as Memory['memoryType'],
      confidence: row.confidence,
      source: row.source as MemorySource,
      validFrom: new Date(row.valid_from),
      validUntil: row.valid_until ? new Date(row.valid_until) : null,
      supersedes: row.supersedes,
      supersededBy: row.superseded_by,
      supersededAt: row.superseded_at ? new Date(row.superseded_at) : null,
      createdAt: new Date(row.created_at),
      lastAccessedAt: row.last_accessed_at
        ? new Date(row.last_accessed_at)
        : null,
      accessCount: row.access_count,
      tags: row.tags,
      metadata: row.metadata,
    };
  }
}

/**
 * Database row type.
 */
interface MemoryRow extends Record<string, unknown> {
  id: string;
  namespace: string[];
  text: string;
  durability: string;
  memory_type: string | null;
  confidence: number;
  source: string;
  valid_from: string;
  valid_until: string | null;
  supersedes: string | null;
  superseded_by: string | null;
  superseded_at: string | null;
  created_at: string;
  last_accessed_at: string | null;
  access_count: number;
  tags: string[];
  metadata: Record<string, unknown>;
}

/**
 * Create a memory store with Neon serverless driver.
 */
export function createMemoryStore(config: MemoryStoreConfig): MemoryStore {
  return new MemoryStore(config);
}
