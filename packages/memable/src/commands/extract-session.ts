/**
 * extract-session CLI subcommand
 *
 * Reads a Claude Code Stop hook payload from stdin, parses the JSONL transcript,
 * and stores extracted memories.
 *
 * Usage (invoked by Claude Code Stop hook):
 *   echo '<hook payload JSON>' | npx memable extract-session
 *
 * Hook payload format:
 *   { "transcript_path": "...", "cwd": "...", "session_id": "...", ... }
 */

import { createReadStream } from 'fs';
import { createInterface } from 'readline';
import { randomUUID } from 'crypto';
import path from 'path';
import { isHostedMode, createHostedClient } from '../mcp/hosted-client.js';
import { extractMemories } from '../extraction.js';
import { MemoryStore } from '../store.js';
import { SQLiteMemoryStore } from '../sqlite-store.js';
import { createEmbeddings, type EmbeddingProviderType } from '../embeddings.js';
import { MemorySource } from '../schema.js';

/** Hook payload written to stdin by Claude Code's Stop hook. */
interface StopHookPayload {
  transcript_path: string;
  cwd: string;
  session_id: string;
  hook_event_name?: string;
  reason?: string;
}

/** One line of the JSONL transcript. */
interface TranscriptLine {
  type: string;
  message?: {
    role?: string;
    content?: Array<TranscriptContentItem>;
  };
  sessionId?: string;
  cwd?: string;
}

interface TranscriptContentItem {
  type: string;
  text?: string;
  thinking?: string;
  name?: string;
  input?: unknown;
}

/**
 * Read stdin to completion and return it as a string.
 */
async function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    process.stdin.on('data', (chunk: Buffer) => chunks.push(chunk));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    process.stdin.on('error', reject);
  });
}

/**
 * Read a JSONL file line-by-line and return parsed objects.
 */
async function readJsonlFile(filePath: string): Promise<TranscriptLine[]> {
  const lines: TranscriptLine[] = [];

  const rl = createInterface({
    input: createReadStream(filePath, { encoding: 'utf8' }),
    crlfDelay: Infinity,
  });

  for await (const line of rl) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      lines.push(JSON.parse(trimmed) as TranscriptLine);
    } catch {
      // Skip malformed lines silently
    }
  }

  return lines;
}

/**
 * Build a plain-text conversation string from transcript lines.
 * Only includes user/assistant turns with text content.
 */
function buildConversationText(lines: TranscriptLine[]): string {
  const parts: string[] = [];

  for (const line of lines) {
    if (line.type !== 'user' && line.type !== 'assistant') continue;
    if (!line.message?.content) continue;

    const role = line.type === 'user' ? 'User' : 'Assistant';
    const textParts: string[] = [];

    for (const item of line.message.content) {
      if (item.type === 'text' && item.text) {
        textParts.push(item.text);
      }
      // Skip tool_use, thinking, tool_result, etc.
    }

    if (textParts.length > 0) {
      parts.push(`${role}: ${textParts.join('\n')}`);
    }
  }

  return parts.join('\n\n');
}

/**
 * Run extract-session in hosted mode.
 */
async function runHostedExtractSession(
  conversationText: string,
  projectName: string,
  sessionId: string,
  cwd: string
): Promise<void> {
  const client = createHostedClient();
  const apiUrl = process.env.MEMABLE_API_URL || 'https://api.memable.ai';

  // POST to /mcp/tools/extract
  const extractResult = await client.extract({
    conversation: conversationText,
    store: true,
  });

  const memoriesExtracted = extractResult.count ?? extractResult.memories?.length ?? 0;
  console.error(`[memable] extract-session (hosted): extracted ${memoriesExtracted} memories`);

  // Fire-and-forget POST to /api/sessions/extract (endpoint may not exist yet)
  try {
    const res = await fetch(`${apiUrl}/api/sessions/extract`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': process.env.MEMABLE_API_KEY ?? '',
      },
      body: JSON.stringify({
        project_name: projectName,
        session_id: sessionId,
        cwd,
        memories_extracted: memoriesExtracted,
      }),
    });

    if (!res.ok && res.status !== 404) {
      console.error(`[memable] extract-session: sessions/extract returned ${res.status}`);
    }
  } catch {
    // Silently ignore — endpoint may not exist yet
  }
}

/**
 * Run extract-session in local mode.
 */
async function runLocalExtractSession(
  conversationText: string,
  projectName: string | undefined,
  sessionId: string,
  cwd: string
): Promise<void> {
  const providerType = (process.env.MEMABLE_EMBEDDINGS as EmbeddingProviderType) || 'auto';

  const embeddings = await createEmbeddings(providerType);

  let store: MemoryStore | SQLiteMemoryStore;

  if (process.env.DATABASE_URL) {
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(process.env.DATABASE_URL) as unknown as import('../store.js').SqlExecutor;
    store = new MemoryStore({ sql, embeddings });
  } else {
    const dbPath = process.env.ENGRAM_DB_PATH;
    store = new SQLiteMemoryStore({ embeddings, dbPath });
  }

  await store.setup();

  try {
    const result = await extractMemories(conversationText);
    const namespace = projectName
      ? ['user', 'repos', projectName]
      : ['user', 'projects', path.basename(cwd)];

    let stored = 0;
    for (const memory of result.memories) {
      if (memory.confidence < 0.5) continue;

      await store.add(namespace, {
        text: memory.text,
        memoryType: memory.memoryType,
        durability: memory.durability,
        confidence: memory.confidence,
        source: MemorySource.INFERRED,
        metadata: {
          source: 'claude-code',
          ...(projectName ? { project: projectName } : {}),
          session_id: sessionId,
        },
      });

      stored++;
    }

    console.error(`[memable] extract-session (local): extracted ${result.memories.length}, stored ${stored} memories`);
  } finally {
    if ('close' in store) {
      (store as SQLiteMemoryStore).close();
    }
  }
}

/**
 * Main entry point for the extract-session subcommand.
 */
export async function runExtractSession(): Promise<void> {
  try {
    // 1. Read and parse hook payload from stdin
    const raw = await readStdin();
    const payload = JSON.parse(raw.trim()) as StopHookPayload;

    const { transcript_path, cwd, session_id } = payload;
    const sessionId = session_id || randomUUID();

    if (!transcript_path || !cwd) {
      console.error('[memable] extract-session: missing transcript_path or cwd in payload');
      return;
    }

    // 2. Read and parse the JSONL transcript
    const lines = await readJsonlFile(transcript_path);

    // 3-5. Build conversation text
    const conversationText = buildConversationText(lines);

    if (!conversationText.trim()) {
      console.error('[memable] extract-session: no usable conversation text found in transcript');
      return;
    }

    // 6. Derive project name
    let projectName: string | undefined;
    if (process.env.MEMABLE_PROJECT) {
      projectName = process.env.MEMABLE_PROJECT;
    } else if (isHostedMode()) {
      projectName = path.basename(cwd);
    } else {
      // Local mode: only scope to project namespace if cwd is a git repo
      try {
        const { execFileSync } = await import('child_process');
        execFileSync('git', ['rev-parse', '--git-dir'], { stdio: 'ignore', cwd });
        projectName = path.basename(cwd);
      } catch {
        // Not a git repo — store in global namespace
      }
    }

    // 7/8. Store memories via hosted or local mode
    if (isHostedMode()) {
      await runHostedExtractSession(conversationText, projectName ?? path.basename(cwd), sessionId, cwd);
    } else {
      await runLocalExtractSession(conversationText, projectName, sessionId, cwd);
    }
  } catch (error) {
    // 9. Log errors to stderr, exit 0 so hook doesn't surface errors to user
    console.error('[memable] extract-session error:', error instanceof Error ? error.message : String(error));
  }
}
