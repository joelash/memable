/**
 * Embeddings providers for engram-ai.
 */

import type { EmbeddingsProvider } from './store.js';

/**
 * OpenAI embeddings configuration.
 */
export interface OpenAIEmbeddingsConfig {
  /** OpenAI API key (defaults to OPENAI_API_KEY env var). */
  apiKey?: string;
  /** Model name (default: text-embedding-3-small). */
  model?: string;
  /** Embedding dimensions (default: 1536). */
  dimensions?: number;
  /** Base URL for API (e.g., for Helicone or other proxies). */
  baseUrl?: string;
  /** Additional headers (e.g., for Helicone auth). */
  headers?: Record<string, string>;
}

/**
 * OpenAI embeddings provider.
 */
export function openaiEmbeddings(config: OpenAIEmbeddingsConfig = {}): EmbeddingsProvider {
  const apiKey = config.apiKey ?? process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OpenAI API key required. Pass apiKey or set OPENAI_API_KEY.');
  }

  const model = config.model ?? 'text-embedding-3-small';
  const dimensions = config.dimensions ?? 1536;
  const baseUrl = config.baseUrl ?? 'https://api.openai.com/v1';

  return {
    dimensions,

    async embed(texts: string[]): Promise<number[][]> {
      const response = await fetch(`${baseUrl}/embeddings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
          ...config.headers,
        },
        body: JSON.stringify({
          model,
          input: texts,
          dimensions,
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`OpenAI embeddings failed: ${response.status} ${error}`);
      }

      const data = (await response.json()) as {
        data: Array<{ embedding: number[] }>;
      };
      return data.data.map((item) => item.embedding);
    },
  };
}

/**
 * Helicone-proxied OpenAI embeddings.
 */
export function heliconeEmbeddings(config: {
  heliconeKey: string;
  openaiKey?: string;
  model?: string;
  dimensions?: number;
}): EmbeddingsProvider {
  return openaiEmbeddings({
    apiKey: config.openaiKey,
    model: config.model,
    dimensions: config.dimensions,
    baseUrl: 'https://oai.helicone.ai/v1',
    headers: {
      'Helicone-Auth': `Bearer ${config.heliconeKey}`,
    },
  });
}

/**
 * Mock embeddings for testing (random vectors).
 */
export function mockEmbeddings(dimensions = 1536): EmbeddingsProvider {
  return {
    dimensions,
    async embed(texts: string[]): Promise<number[][]> {
      return texts.map(() => {
        const vec = Array.from({ length: dimensions }, () => Math.random() * 2 - 1);
        // Normalize
        const norm = Math.sqrt(vec.reduce((sum, v) => sum + v * v, 0));
        return vec.map((v) => v / norm);
      });
    },
  };
}
