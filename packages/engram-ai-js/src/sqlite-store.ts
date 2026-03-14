/**
 * SQLite memory store using sql.js (WASM).
 * Zero-config, local-first storage for MCP and personal use.
 */

import { v4 as uuidv4 } from 'uuid';
import initSqlJs, { Database } from 'sql.js';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { homedir } from 'os';
import {
  Durability,
  Memory,
  MemoryCreate,
  MemoryQuery,
  MemorySource,
  MemoryType,
  isMemoryCurrent,
  isMemoryValid,
} from './schema.js';
import { EmbeddingsProvider } from './store.js';

/**
 * Configuration for SQLiteMemoryStore.
 */
export interface SQLiteMemoryStoreConfig {
  /** Path to SQLite database file. Defaults to ~/.memento/memories.db */
  dbPath?: string;
  /** Embeddings provider for semantic search. */
  embeddings: EmbeddingsProvider;
}

/**
 * Compute cosine similarity between two vectors.
 */
function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  
  const magnitude = Math.sqrt(normA) * Math.sqrt(normB);
  return magnitude === 0 ? 0 : dotProduct / magnitude;
}

/**
 * SQLite-based memory store with semantic search.
 * 
 * Uses sql.js (WASM) for zero-dependency SQLite.
 * Embeddings stored as JSON, similarity computed in JS.
 * Perfect for personal use / MCP where <100K memories.
 */
export class SQLiteMemoryStore {
  private db: Database | null = null;
  private dbPath: string;
  private embeddings: EmbeddingsProvider;

  constructor(config: SQLiteMemoryStoreConfig) {
    this.dbPath = config.dbPath ?? join(homedir(), '.memento', 'memories.db');
    this.embeddings = config.embeddings;
  }

  /**
   * Initialize the database. Call before any operations.
   */
  async setup(): Promise<void> {
    if (this.db) return;

    // Ensure directory exists
    const dir = dirname(this.dbPath);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }

    // Initialize sql.js
    const SQL = await initSqlJs();

    // Load existing database or create new
    if (existsSync(this.dbPath)) {
      const buffer = readFileSync(this.dbPath);
      this.db = new SQL.Database(buffer);
    } else {
      this.db = new SQL.Database();
    }

    // Create tables
    this.db.run(`
      CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        text TEXT NOT NULL,
        durability TEXT NOT NULL DEFAULT 'situational',
        memory_type TEXT,
        valid_from TEXT,
        valid_until TEXT,
        confidence REAL NOT NULL DEFAULT 1.0,
        source TEXT NOT NULL DEFAULT 'explicit',
        supersedes TEXT,
        superseded_by TEXT,
        superseded_at TEXT,
        embedding TEXT,
        tags TEXT,
        metadata TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_accessed_at TEXT
      )
    `);

    this.db.run(`CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace)`);
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_memories_superseded ON memories(superseded_by)`);

    this.save();
  }

  /**
   * Persist database to disk.
   */
  private save(): void {
    if (!this.db) return;
    const data = this.db.export();
    const buffer = Buffer.from(data);
    writeFileSync(this.dbPath, buffer);
  }

  /**
   * Encode namespace to string.
   */
  private encodeNamespace(namespace: string | string[]): string {
    return Array.isArray(namespace) ? namespace.join('::') : namespace;
  }

  /**
   * Add a memory to the store.
   */
  async add(namespace: string | string[], memory: MemoryCreate): Promise<Memory> {
    if (!this.db) throw new Error('Database not initialized. Call setup() first.');

    const id = uuidv4();
    const now = new Date();
    const ns = this.encodeNamespace(namespace);

    // Generate embedding
    const [embedding] = await this.embeddings.embed([memory.text]);

    // Check for contradictions and create version chain
    let supersedes: string | null = null;
    if (memory.durability === Durability.CORE || memory.durability === Durability.SITUATIONAL) {
      const existing = await this.search(namespace, { query: memory.text, limit: 1 });
      if (existing.length > 0 && existing[0].durability === memory.durability) {
        // Check similarity threshold
        const existingEmbed = await this.getEmbedding(existing[0].id);
        if (existingEmbed && cosineSimilarity(embedding, existingEmbed) > 0.95) {
          supersedes = existing[0].id;
          // Mark old memory as superseded
          this.db.run(
            `UPDATE memories SET superseded_by = ?, superseded_at = ?, updated_at = ? WHERE id = ?`,
            [id, now.toISOString(), now.toISOString(), supersedes]
          );
        }
      }
    }

    const durability = memory.durability ?? Durability.SITUATIONAL;
    const source = memory.source ?? MemorySource.EXPLICIT;

    this.db.run(
      `INSERT INTO memories (id, namespace, text, durability, memory_type, valid_from, valid_until, confidence, source, supersedes, embedding, tags, metadata, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        id,
        ns,
        memory.text,
        durability,
        memory.memoryType ?? null,
        memory.validFrom?.toISOString() ?? now.toISOString(),
        memory.validUntil?.toISOString() ?? null,
        memory.confidence ?? 1.0,
        source,
        supersedes,
        JSON.stringify(embedding),
        memory.tags ? JSON.stringify(memory.tags) : '[]',
        memory.metadata ? JSON.stringify(memory.metadata) : null,
        now.toISOString(),
        now.toISOString(),
      ]
    );

    this.save();

    return {
      id,
      text: memory.text,
      durability,
      memoryType: memory.memoryType,
      validFrom: memory.validFrom ?? now,
      validUntil: memory.validUntil ?? null,
      confidence: memory.confidence ?? 1.0,
      source,
      supersedes: supersedes ?? undefined,
      supersededBy: undefined,
      supersededAt: null,
      tags: memory.tags ?? [],
      metadata: memory.metadata ?? {},
      createdAt: now,
      lastAccessedAt: null,
      accessCount: 0,
    };
  }

  /**
   * Get embedding for a memory.
   */
  private getEmbedding(id: string): number[] | null {
    if (!this.db) return null;
    const stmt = this.db.prepare(`SELECT embedding FROM memories WHERE id = ?`);
    stmt.bind([id]);
    if (stmt.step()) {
      const row = stmt.getAsObject() as Record<string, unknown>;
      stmt.free();
      return JSON.parse(row.embedding as string) as number[];
    }
    stmt.free();
    return null;
  }

  /**
   * Search for memories by semantic similarity.
   */
  async search(namespace: string | string[], query: MemoryQuery): Promise<Memory[]> {
    if (!this.db) throw new Error('Database not initialized. Call setup() first.');

    const { 
      query: queryText, 
      limit = 10, 
      includeSuperseded = false,
      includeExpired = false,
      minConfidence,
      durability: filterDurability,
      memoryType: filterType,
      validAt,
    } = query;
    
    const ns = this.encodeNamespace(namespace);
    const checkTime = validAt ?? new Date();

    // Generate query embedding
    const [queryEmbedding] = await this.embeddings.embed([queryText]);

    // Fetch memories in namespace
    const sqlQuery = includeSuperseded
      ? `SELECT * FROM memories WHERE namespace = ?`
      : `SELECT * FROM memories WHERE namespace = ? AND superseded_by IS NULL`;
    
    const stmt = this.db.prepare(sqlQuery);
    stmt.bind([ns]);

    const results: Array<{ memory: Memory; score: number }> = [];

    while (stmt.step()) {
      const row = stmt.getAsObject() as Record<string, unknown>;
      const embedding = JSON.parse(row.embedding as string) as number[];
      const score = cosineSimilarity(queryEmbedding, embedding);
      const memory = this.rowToMemory(row);

      // Apply filters
      if (!includeSuperseded && !isMemoryCurrent(memory)) continue;
      if (!includeExpired && !isMemoryValid(memory, checkTime)) continue;
      if (minConfidence && memory.confidence < minConfidence) continue;
      if (filterDurability && !filterDurability.includes(memory.durability)) continue;
      if (filterType && (!memory.memoryType || !filterType.includes(memory.memoryType))) continue;

      results.push({ memory, score });
    }
    stmt.free();

    // Sort by score descending and limit
    results.sort((a, b) => b.score - a.score);
    return results.slice(0, limit).map(r => r.memory);
  }

  /**
   * List all memories in namespace.
   */
  async listAll(
    namespace: string | string[],
    options?: { includeSuperseded?: boolean; includeExpired?: boolean }
  ): Promise<Memory[]> {
    if (!this.db) throw new Error('Database not initialized. Call setup() first.');

    const ns = this.encodeNamespace(namespace);
    const includeSuperseded = options?.includeSuperseded ?? false;
    const includeExpired = options?.includeExpired ?? false;

    const query = includeSuperseded
      ? `SELECT * FROM memories WHERE namespace = ? ORDER BY created_at DESC`
      : `SELECT * FROM memories WHERE namespace = ? AND superseded_by IS NULL ORDER BY created_at DESC`;

    const stmt = this.db.prepare(query);
    stmt.bind([ns]);

    const memories: Memory[] = [];
    const now = new Date();
    
    while (stmt.step()) {
      const row = stmt.getAsObject() as Record<string, unknown>;
      const memory = this.rowToMemory(row);
      
      if (!includeExpired && !isMemoryValid(memory, now)) continue;
      
      memories.push(memory);
    }
    stmt.free();

    return memories;
  }

  /**
   * Delete a memory.
   */
  async delete(namespace: string | string[], id: string): Promise<boolean> {
    if (!this.db) throw new Error('Database not initialized. Call setup() first.');

    const ns = this.encodeNamespace(namespace);
    const before = this.db.getRowsModified();
    this.db.run(`DELETE FROM memories WHERE id = ? AND namespace = ?`, [id, ns]);
    const after = this.db.getRowsModified();
    this.save();
    return after > before;
  }

  /**
   * Close the database connection.
   */
  close(): void {
    if (this.db) {
      this.save();
      this.db.close();
      this.db = null;
    }
  }

  /**
   * Convert a database row to Memory object.
   */
  private rowToMemory(row: Record<string, unknown>): Memory {
    return {
      id: row.id as string,
      text: row.text as string,
      durability: row.durability as Durability,
      memoryType: row.memory_type as MemoryType | undefined,
      validFrom: new Date(row.valid_from as string),
      validUntil: row.valid_until ? new Date(row.valid_until as string) : null,
      confidence: row.confidence as number,
      source: row.source as MemorySource,
      supersedes: row.supersedes as string | undefined,
      supersededBy: row.superseded_by as string | undefined,
      supersededAt: row.superseded_at ? new Date(row.superseded_at as string) : null,
      tags: row.tags ? JSON.parse(row.tags as string) : [],
      metadata: row.metadata ? JSON.parse(row.metadata as string) : {},
      createdAt: new Date(row.created_at as string),
      lastAccessedAt: row.last_accessed_at ? new Date(row.last_accessed_at as string) : null,
      accessCount: (row.access_count as number) ?? 0,
    };
  }
}

/**
 * Create a SQLite memory store with default settings.
 * Zero-config: uses ~/.memento/memories.db
 */
export function createSQLiteStore(embeddings: EmbeddingsProvider, dbPath?: string): SQLiteMemoryStore {
  return new SQLiteMemoryStore({ embeddings, dbPath });
}
