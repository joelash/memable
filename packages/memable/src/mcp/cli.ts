#!/usr/bin/env node
/**
 * engram-ai MCP CLI
 * 
 * Zero-config memory server for Claude Desktop, Cursor, and other MCP tools.
 * 
 * Usage:
 *   npx engram-ai-mcp
 * 
 * Environment variables:
 *   DATABASE_URL    - PostgreSQL connection string (optional, uses SQLite if not set)
 *   OPENAI_API_KEY  - Required for embeddings
 *   ENGRAM_DB_PATH  - Custom SQLite path (default: ~/.engram/memories.db)
 *   ENGRAM_NAMESPACE - Default namespace (default: 'default')
 */

import { createInterface } from 'readline';
import { MemoryStore } from '../store.js';
import { SQLiteMemoryStore } from '../sqlite-store.js';
import { openaiEmbeddings } from '../embeddings.js';
import { McpServer } from './index.js';

type AnyStore = MemoryStore | SQLiteMemoryStore;

async function main() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('Error: OPENAI_API_KEY environment variable is required');
    process.exit(1);
  }

  const embeddings = openaiEmbeddings({ apiKey });
  let store: AnyStore;

  // Auto-detect: Postgres if DATABASE_URL, else SQLite
  if (process.env.DATABASE_URL) {
    // Dynamic import for Postgres (avoid bundling if not needed)
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(process.env.DATABASE_URL) as unknown as import('../store.js').SqlExecutor;
    store = new MemoryStore({ sql, embeddings });
  } else {
    // SQLite - zero config
    const dbPath = process.env.ENGRAM_DB_PATH;
    store = new SQLiteMemoryStore({ embeddings, dbPath });
    console.error(`[engram-ai] Using SQLite: ${dbPath ?? '~/.engram/memories.db'}`);
  }

  // Initialize store
  await store.setup();

  // Create MCP server
  const namespace = process.env.ENGRAM_NAMESPACE?.split(',') ?? ['default'];
  const server = new McpServer({
    store: store as MemoryStore, // Type assertion - interfaces are compatible
    defaultNamespace: namespace,
  });

  // Handle JSON-RPC over stdio
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false,
  });

  let buffer = '';

  rl.on('line', async (line) => {
    buffer += line;
    
    try {
      const message = JSON.parse(buffer);
      buffer = '';

      const response = await server.handleMessage(message);
      console.log(JSON.stringify(response));
    } catch (e) {
      // Incomplete JSON, wait for more lines
      if (!(e instanceof SyntaxError)) {
        console.error('[engram-ai] Error:', e);
      }
    }
  });

  rl.on('close', () => {
    if ('close' in store) {
      (store as SQLiteMemoryStore).close();
    }
    process.exit(0);
  });

  // Handle graceful shutdown
  process.on('SIGINT', () => {
    if ('close' in store) {
      (store as SQLiteMemoryStore).close();
    }
    process.exit(0);
  });

  console.error('[engram-ai] MCP server ready');
}

main().catch((error) => {
  console.error('[engram-ai] Fatal error:', error);
  process.exit(1);
});
