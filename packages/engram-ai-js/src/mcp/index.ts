/**
 * MCP (Model Context Protocol) server for engram-ai.
 * 
 * Exposes memory operations as MCP tools that can be used by
 * Claude Desktop, Cursor, and other MCP-compatible AI tools.
 * 
 * @example
 * ```typescript
 * import { createMcpServer } from 'engram-ai/mcp';
 * import { createMemoryStore, openaiEmbeddings } from 'engram-ai';
 * import { neon } from '@neondatabase/serverless';
 * 
 * const store = createMemoryStore({
 *   sql: neon(process.env.DATABASE_URL!),
 *   embeddings: openaiEmbeddings(),
 * });
 * 
 * const server = createMcpServer({ store });
 * server.listen();
 * ```
 */

import type { MemoryStore } from '../store.js';
import { Durability, MemoryType } from '../schema.js';
import { extractMemories, toMemoryCreates } from '../extraction.js';

/**
 * MCP Server configuration.
 */
export interface McpServerConfig {
  /** Memory store instance. */
  store: MemoryStore;
  /** Default namespace for memories (default: ['default']). */
  defaultNamespace?: string[];
  /** Server name (default: 'engram-ai'). */
  name?: string;
  /** Server version (default: '0.1.0'). */
  version?: string;
}

/**
 * MCP Tool definition.
 */
interface McpTool {
  name: string;
  description: string;
  inputSchema: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}

/**
 * MCP Server for engram-ai memories.
 * 
 * Implements the Model Context Protocol to expose memory operations
 * as tools for AI assistants.
 */
export class McpServer {
  private store: MemoryStore;
  private namespace: string[];
  private name: string;
  private version: string;

  constructor(config: McpServerConfig) {
    this.store = config.store;
    this.namespace = config.defaultNamespace ?? ['default'];
    this.name = config.name ?? 'engram-ai';
    this.version = config.version ?? '0.1.0';
  }

  /**
   * Get server info for MCP handshake.
   */
  getServerInfo() {
    return {
      name: this.name,
      version: this.version,
      description: 'Semantic memory for AI agents. Remember facts, preferences, and context across sessions.',
      icons: [
        {
          // Purple brain SVG icon
          src: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0OCIgaGVpZ2h0PSI0OCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNhODU1ZjciIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTIgNWEzIDMgMCAxIDAtNS45OTcuMTI1IDQgNCAwIDAgMC0yLjUyNiA1Ljc3IDQgNCAwIDAgMCAuNTU2IDYuNTg4QTQgNCAwIDEgMCAxMiAxOFoiLz48cGF0aCBkPSJNMTIgNWEzIDMgMCAxIDEgNS45OTcuMTI1IDQgNCAwIDAgMSAyLjUyNiA1Ljc3IDQgNCAwIDAgMS0uNTU2IDYuNTg4QTQgNCAwIDEgMSAxMiAxOFoiLz48cGF0aCBkPSJNMTUgMTNhNC41IDQuNSAwIDAgMS0zLTQgNC41IDQuNSAwIDAgMS0zIDQiLz48cGF0aCBkPSJNMTcuNTk5IDYuNWEzIDMgMCAwIDAgLjM5OS0xLjM3NSIvPjxwYXRoIGQ9Ik02LjAwMyA1LjEyNUEzIDMgMCAwIDAgNi40MDEgNi41Ii8+PHBhdGggZD0iTTMuNDc3IDEwLjg5NmE0IDQgMCAwIDEgLjU4NS0uMzk2Ii8+PHBhdGggZD0iTTE5LjkzOCAxMC41YTQgNCAwIDAgMSAuNTg1LjM5NiIvPjxwYXRoIGQ9Ik02IDE4YTQgNCAwIDAgMS0xLjk2Ny0uNTE2Ii8+PHBhdGggZD0iTTE5Ljk2NyAxNy40ODRBNCA0IDAgMCAxIDE4IDE4Ii8+PC9zdmc+',
          mimeType: 'image/svg+xml',
          sizes: ['48x48'],
        },
      ],
      capabilities: {
        tools: {},
      },
    };
  }

  /**
   * Get available tools.
   */
  getTools(): McpTool[] {
    return [
      {
        name: 'remember',
        description: 'Store a new memory. Use this to remember facts, rules, decisions, preferences, or context for later.',
        inputSchema: {
          type: 'object',
          properties: {
            text: {
              type: 'string',
              description: 'The memory content to store',
            },
            type: {
              type: 'string',
              enum: ['fact', 'rule', 'decision', 'preference', 'context', 'observation'],
              description: 'Semantic type of this memory',
            },
            durability: {
              type: 'string',
              enum: ['core', 'situational', 'episodic'],
              description: 'How permanent this memory is (core = permanent, situational = temporary, episodic = decays)',
            },
            tags: {
              type: 'array',
              items: { type: 'string' },
              description: 'Optional tags for categorization',
            },
          },
          required: ['text'],
        },
      },
      {
        name: 'recall',
        description: 'Search memories by semantic similarity. Use this to find relevant context before responding.',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'What to search for',
            },
            limit: {
              type: 'number',
              description: 'Maximum number of memories to return (default: 5)',
            },
            type: {
              type: 'string',
              enum: ['fact', 'rule', 'decision', 'preference', 'context', 'observation'],
              description: 'Filter by memory type',
            },
          },
          required: ['query'],
        },
      },
      {
        name: 'list_memories',
        description: 'List all memories, optionally filtered by type or durability.',
        inputSchema: {
          type: 'object',
          properties: {
            type: {
              type: 'string',
              enum: ['fact', 'rule', 'decision', 'preference', 'context', 'observation'],
              description: 'Filter by memory type',
            },
            durability: {
              type: 'string',
              enum: ['core', 'situational', 'episodic'],
              description: 'Filter by durability',
            },
          },
        },
      },
      {
        name: 'forget',
        description: 'Delete a specific memory by ID.',
        inputSchema: {
          type: 'object',
          properties: {
            id: {
              type: 'string',
              description: 'Memory ID to delete',
            },
          },
          required: ['id'],
        },
      },
      {
        name: 'extract',
        description: 'Automatically extract and store memories from conversation text. Uses AI to identify facts, preferences, decisions, and other memorable information.',
        inputSchema: {
          type: 'object',
          properties: {
            conversation: {
              type: 'string',
              description: 'The conversation text to extract memories from',
            },
            store: {
              type: 'boolean',
              description: 'Whether to automatically store extracted memories (default: true)',
            },
          },
          required: ['conversation'],
        },
      },
    ];
  }

  /**
   * Handle a tool call.
   */
  async handleToolCall(
    name: string,
    args: Record<string, unknown>
  ): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
    try {
      let result: unknown;

      switch (name) {
        case 'remember':
          result = await this.handleRemember(args);
          break;
        case 'recall':
          result = await this.handleRecall(args);
          break;
        case 'list_memories':
          result = await this.handleListMemories(args);
          break;
        case 'forget':
          result = await this.handleForget(args);
          break;
        case 'extract':
          result = await this.handleExtract(args);
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

  private async handleRemember(args: Record<string, unknown>) {
    const text = args.text as string;
    const memoryType = args.type
      ? (args.type as string).toUpperCase() as keyof typeof MemoryType
      : undefined;
    const durability = args.durability
      ? (args.durability as string).toUpperCase() as keyof typeof Durability
      : undefined;
    const tags = args.tags as string[] | undefined;

    const memory = await this.store.add(this.namespace, {
      text,
      memoryType: memoryType ? MemoryType[memoryType] : undefined,
      durability: durability ? Durability[durability] : undefined,
      tags,
    });

    return {
      success: true,
      memory: {
        id: memory.id,
        text: memory.text,
        type: memory.memoryType,
        durability: memory.durability,
      },
    };
  }

  private async handleRecall(args: Record<string, unknown>) {
    const query = args.query as string;
    const limit = (args.limit as number) ?? 5;
    const memoryType = args.type
      ? (args.type as string).toUpperCase() as keyof typeof MemoryType
      : undefined;

    const memories = await this.store.search(this.namespace, {
      query,
      limit,
      memoryType: memoryType ? [MemoryType[memoryType]] : undefined,
    });

    return {
      count: memories.length,
      memories: memories.map((m) => ({
        id: m.id,
        text: m.text,
        type: m.memoryType,
        durability: m.durability,
        confidence: m.confidence,
      })),
    };
  }

  private async handleListMemories(args: Record<string, unknown>) {
    const memories = await this.store.listAll(this.namespace);

    // Filter in JS
    let filtered = memories;

    if (args.type) {
      const memoryType = (args.type as string).toUpperCase() as keyof typeof MemoryType;
      filtered = filtered.filter((m) => m.memoryType === MemoryType[memoryType]);
    }

    if (args.durability) {
      const durability = (args.durability as string).toUpperCase() as keyof typeof Durability;
      filtered = filtered.filter((m) => m.durability === Durability[durability]);
    }

    return {
      count: filtered.length,
      memories: filtered.map((m) => ({
        id: m.id,
        text: m.text,
        type: m.memoryType,
        durability: m.durability,
      })),
    };
  }

  private async handleForget(args: Record<string, unknown>) {
    const id = args.id as string;
    const deleted = await this.store.delete(this.namespace, id);

    return {
      success: deleted,
      message: deleted ? 'Memory deleted' : 'Memory not found',
    };
  }

  private async handleExtract(args: Record<string, unknown>) {
    const conversation = args.conversation as string;
    const shouldStore = args.store !== false; // default true

    // Extract memories from conversation
    const result = await extractMemories(conversation);

    if (result.memories.length === 0) {
      return {
        extracted: 0,
        stored: 0,
        memories: [],
        message: 'No memorable information found in the conversation.',
      };
    }

    // Store memories if requested
    const storedMemories: Array<{ id: string; text: string; type: string; durability: string }> = [];

    if (shouldStore) {
      const memoryCreates = toMemoryCreates(result.memories);
      for (const create of memoryCreates) {
        const memory = await this.store.add(this.namespace, create);
        storedMemories.push({
          id: memory.id,
          text: memory.text,
          type: memory.memoryType ?? 'fact',
          durability: memory.durability ?? 'situational',
        });
      }
    }

    return {
      extracted: result.memories.length,
      stored: storedMemories.length,
      memories: shouldStore ? storedMemories : result.memories.map((m) => ({
        text: m.text,
        type: m.memoryType,
        durability: m.durability,
        confidence: m.confidence,
      })),
      message: shouldStore 
        ? `Extracted and stored ${storedMemories.length} memories.`
        : `Extracted ${result.memories.length} memories (not stored).`,
    };
  }

  /**
   * Handle incoming MCP JSON-RPC message.
   */
  async handleMessage(message: {
    jsonrpc: '2.0';
    id: string | number;
    method: string;
    params?: unknown;
  }): Promise<{
    jsonrpc: '2.0';
    id: string | number;
    result?: unknown;
    error?: { code: number; message: string };
  }> {
    const { id, method, params } = message;

    try {
      let result: unknown;

      switch (method) {
        case 'initialize':
          result = {
            protocolVersion: '2024-11-05',
            serverInfo: this.getServerInfo(),
            capabilities: { tools: {} },
          };
          break;

        case 'tools/list':
          result = { tools: this.getTools() };
          break;

        case 'tools/call':
          const { name, arguments: args } = params as {
            name: string;
            arguments: Record<string, unknown>;
          };
          result = await this.handleToolCall(name, args);
          break;

        default:
          return {
            jsonrpc: '2.0',
            id,
            error: { code: -32601, message: `Method not found: ${method}` },
          };
      }

      return { jsonrpc: '2.0', id, result };
    } catch (error) {
      return {
        jsonrpc: '2.0',
        id,
        error: {
          code: -32603,
          message: error instanceof Error ? error.message : String(error),
        },
      };
    }
  }
}

/**
 * Create an MCP server for engram-ai memories.
 */
export function createMcpServer(config: McpServerConfig): McpServer {
  return new McpServer(config);
}
