/**
 * engram-ai: Long-term semantic memory for AI agents (TypeScript)
 * 
 * @example
 * ```typescript
 * import { neon } from '@neondatabase/serverless';
 * import { createMemoryStore, openaiEmbeddings, Durability, MemoryType } from 'engram-ai';
 * 
 * const sql = neon(process.env.DATABASE_URL!);
 * const store = createMemoryStore({
 *   sql,
 *   embeddings: openaiEmbeddings(),
 * });
 * 
 * await store.setup(); // Run once to create tables
 * 
 * // Add a memory
 * await store.add(['user_123', 'preferences'], {
 *   text: 'User prefers dark mode',
 *   durability: Durability.CORE,
 *   memoryType: MemoryType.PREFERENCE,
 * });
 * 
 * // Search memories
 * const memories = await store.search(['user_123', 'preferences'], {
 *   query: 'UI settings',
 *   limit: 5,
 * });
 * ```
 */

// Schema types
export {
  Durability,
  MemorySource,
  MemoryType,
  isMemoryCurrent,
  isMemoryValid,
} from './schema.js';

export type {
  Memory,
  MemoryCreate,
  MemoryQuery,
  MemoryUpdate,
  Namespace,
} from './schema.js';

// Store
export { createMemoryStore, MemoryStore } from './store.js';

export type {
  EmbeddingsProvider,
  MemoryStoreConfig,
  SqlExecutor,
} from './store.js';

// Embeddings providers
export {
  heliconeEmbeddings,
  mockEmbeddings,
  openaiEmbeddings,
} from './embeddings.js';

export type { OpenAIEmbeddingsConfig } from './embeddings.js';

// SQLite store (for local/MCP use)
export { createSQLiteStore, SQLiteMemoryStore } from './sqlite-store.js';

export type { SQLiteMemoryStoreConfig } from './sqlite-store.js';

// Memory extraction
export { extractMemories, toMemoryCreates } from './extraction.js';

export type { ExtractedMemory, ExtractionResult } from './extraction.js';
