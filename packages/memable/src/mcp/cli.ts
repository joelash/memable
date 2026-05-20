#!/usr/bin/env node
/**
 * memable MCP CLI
 * 
 * Zero-config memory server for Claude Desktop, Cursor, and other MCP tools.
 * 
 * Usage:
 *   npx memable
 * 
 * Environment variables:
 *   # Hosted mode (recommended):
 *   MEMABLE_API_URL  - Hosted API URL (e.g. https://api.memable.ai)
 *   MEMABLE_API_KEY  - Your API key from the dashboard (mem_xxx)
 * 
 *   # Local mode:
 *   DATABASE_URL       - PostgreSQL connection string (optional, uses SQLite if not set)
 *   MEMABLE_EMBEDDINGS - Force embedding provider: 'ollama', 'openai', or 'auto' (default)
 *   OPENAI_API_KEY     - Required if using OpenAI embeddings
 *   OLLAMA_HOST        - Ollama server URL (default: http://localhost:11434)
 *   ENGRAM_DB_PATH     - Custom SQLite path (default: ~/.engram/memories.db)
 *   ENGRAM_NAMESPACE   - Default namespace (default: 'default')
 */

import { createInterface } from 'readline';
import path from 'path';
import { MemoryStore } from '../store.js';
import { SQLiteMemoryStore } from '../sqlite-store.js';
import { createEmbeddings, type EmbeddingProviderType } from '../embeddings.js';
import { McpServer } from './index.js';
import { isHostedMode, createHostedClient, HostedMcpClient } from './hosted-client.js';
import { runExtractSession } from '../commands/extract-session.js';

type AnyStore = MemoryStore | SQLiteMemoryStore;

/**
 * Run in hosted mode - proxy requests to the hosted API.
 */
async function runHostedMode() {
  const client = createHostedClient();
  const apiUrl = process.env.MEMABLE_API_URL || 'https://api.memable.ai';
  console.error(`[memable] Hosted mode: ${apiUrl}`);

  // Create a minimal MCP handler that proxies to hosted API
  const handleMessage = async (message: {
    jsonrpc: '2.0';
    id: string | number;
    method: string;
    params?: unknown;
  }) => {
    const { id, method, params } = message;

    try {
      let result: unknown;

      switch (method) {
        case 'initialize':
          result = {
            protocolVersion: '2024-11-05',
            serverInfo: {
              name: 'memable',
              version: '0.1.0',
              description: 'Semantic memory for AI agents (hosted mode).',
              capabilities: { tools: {} },
            },
            capabilities: { tools: {} },
          };
          break;

        case 'tools/list':
          result = {
            tools: [
              {
                name: 'boot',
                description: 'Load memory context at session start. Call this at the beginning of every conversation to recall what you know about the user.',
                inputSchema: {
                  type: 'object',
                  properties: {
                    context: { type: 'string', description: 'Optional context about the current conversation topic' },
                    include_recent: { type: 'boolean', description: 'Include memories from last 24 hours (default: true)' },
                  },
                },
              },
              {
                name: 'remember',
                description: 'Store a new memory.',
                inputSchema: {
                  type: 'object',
                  properties: {
                    text: { type: 'string', description: 'The memory content to store' },
                    type: {
                      type: 'string',
                      enum: ['fact', 'rule', 'decision', 'preference', 'context', 'observation'],
                      description: 'Semantic type of this memory',
                    },
                    durability: {
                      type: 'string',
                      enum: ['core', 'situational', 'episodic'],
                      description: 'How permanent this memory is',
                    },
                  },
                  required: ['text'],
                },
              },
              {
                name: 'recall',
                description: 'Search memories by semantic similarity.',
                inputSchema: {
                  type: 'object',
                  properties: {
                    query: { type: 'string', description: 'What to search for' },
                    limit: { type: 'number', description: 'Maximum results (default: 5)' },
                  },
                  required: ['query'],
                },
              },
              {
                name: 'list_memories',
                description: 'List all memories.',
                inputSchema: { type: 'object', properties: {} },
              },
              {
                name: 'forget',
                description: 'Delete a memory by ID.',
                inputSchema: {
                  type: 'object',
                  properties: { id: { type: 'string', description: 'Memory ID to delete' } },
                  required: ['id'],
                },
              },
              {
                name: 'extract',
                description: 'Extract memories from conversation text.',
                inputSchema: {
                  type: 'object',
                  properties: {
                    conversation: { type: 'string', description: 'Conversation to extract from' },
                  },
                  required: ['conversation'],
                },
              },
            ],
          };
          break;

        case 'tools/call':
          const { name, arguments: args } = params as {
            name: string;
            arguments: Record<string, unknown>;
          };
          result = await handleHostedToolCall(client, name, args);
          break;

        default:
          return {
            jsonrpc: '2.0' as const,
            id,
            error: { code: -32601, message: `Method not found: ${method}` },
          };
      }

      return { jsonrpc: '2.0' as const, id, result };
    } catch (error) {
      return {
        jsonrpc: '2.0' as const,
        id,
        error: {
          code: -32603,
          message: error instanceof Error ? error.message : String(error),
        },
      };
    }
  };

  // Handle JSON-RPC over stdio
  runStdioLoop(handleMessage);
  console.error('[memable] MCP server ready (hosted mode)');
}

async function handleHostedToolCall(
  client: HostedMcpClient,
  name: string,
  args: Record<string, unknown>
): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  try {
    let result: unknown;

    switch (name) {
      case 'boot':
        result = await client.boot({
          context: args.context as string | undefined,
          include_recent: args.include_recent as boolean | undefined,
        });
        break;
      case 'remember':
        result = await client.remember({
          text: args.text as string,
          type: args.type as string | undefined,
          durability: args.durability as string | undefined,
        });
        break;
      case 'recall':
        result = await client.recall({
          query: args.query as string,
          limit: args.limit as number | undefined,
          type: args.type as string | undefined,
        });
        break;
      case 'list_memories':
        result = await client.listMemories({
          limit: args.limit as number | undefined,
        });
        break;
      case 'forget':
        result = await client.forget({ id: args.id as string });
        break;
      case 'extract':
        result = await client.extract({
          conversation: args.conversation as string,
          store: args.store as boolean | undefined,
        });
        break;
      default:
        throw new Error(`Unknown tool: ${name}`);
    }

    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
    };
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${error instanceof Error ? error.message : String(error)}`,
        },
      ],
    };
  }
}

/**
 * Run in local mode - use local SQLite or Postgres storage.
 */
async function runLocalMode() {
  // Auto-detect embeddings provider (Ollama or OpenAI)
  const providerType = (process.env.MEMABLE_EMBEDDINGS as EmbeddingProviderType) || 'auto';
  
  let embeddings;
  try {
    embeddings = await createEmbeddings(providerType);
  } catch (error) {
    console.error(`[memable] ${error instanceof Error ? error.message : String(error)}`);
    console.error('[memable] Hint: For hosted mode, set MEMABLE_API_KEY instead.');
    process.exit(1);
  }

  let store: AnyStore;

  // Auto-detect: Postgres if DATABASE_URL, else SQLite
  if (process.env.DATABASE_URL) {
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(process.env.DATABASE_URL) as unknown as import('../store.js').SqlExecutor;
    store = new MemoryStore({ sql, embeddings });
  } else {
    const dbPath = process.env.ENGRAM_DB_PATH;
    store = new SQLiteMemoryStore({ embeddings, dbPath });
    console.error(`[memable] Using SQLite: ${dbPath ?? '~/.engram/memories.db'}`);
  }

  await store.setup();

  const namespace = process.env.ENGRAM_NAMESPACE?.split(',') ?? ['default'];
  const projectName = process.env.MEMABLE_PROJECT || path.basename(process.cwd());
  const projectNamespace = ['user', 'repos', projectName];
  const server = new McpServer({
    store: store as MemoryStore,
    defaultNamespace: namespace,
    projectNamespace,
  });

  runStdioLoop(async (message) => server.handleMessage(message));

  // Cleanup on close
  process.on('SIGINT', () => {
    if ('close' in store) {
      (store as SQLiteMemoryStore).close();
    }
    process.exit(0);
  });

  console.error('[memable] MCP server ready (local mode)');
}

/**
 * Common stdio JSON-RPC loop.
 */
function runStdioLoop(
  handleMessage: (message: {
    jsonrpc: '2.0';
    id: string | number;
    method: string;
    params?: unknown;
  }) => Promise<unknown>
) {
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

      const response = await handleMessage(message);
      console.log(JSON.stringify(response));
    } catch (e) {
      if (!(e instanceof SyntaxError)) {
        console.error('[memable] Error:', e);
      }
    }
  });

  rl.on('close', () => {
    process.exit(0);
  });
}

async function main() {
  if (process.argv[2] === 'extract-session') {
    await runExtractSession();
    process.exit(0);
  }

  if (isHostedMode()) {
    await runHostedMode();
  } else {
    await runLocalMode();
  }
}

main().catch((error) => {
  console.error('[memable] Fatal error:', error);
  process.exit(1);
});
