/**
 * Memory extraction from conversations using LLM.
 * 
 * Automatically identifies facts, preferences, decisions, and other
 * memorable information from conversation text.
 */

import OpenAI from 'openai';
import { Durability, MemoryType, type MemoryCreate } from './schema.js';

/**
 * Extracted memory from conversation.
 */
export interface ExtractedMemory {
  text: string;
  memoryType: MemoryType;
  durability: Durability;
  confidence: number;
  reasoning?: string;
}

/**
 * Extraction result.
 */
export interface ExtractionResult {
  memories: ExtractedMemory[];
  rawResponse?: string;
}

const EXTRACTION_PROMPT = `You are a memory extraction system. Analyze the conversation and extract memorable information.

IMPORTANT: Extract each distinct fact as a SEPARATE memory. Do NOT combine multiple facts into one memory.
For example, "I'm a developer in Chicago who prefers Python" should become THREE separate memories:
- "User is a developer" (fact)
- "User is located in Chicago" (fact)  
- "User prefers Python" (preference)

For each piece of information worth remembering, identify:
1. The fact/preference/decision/rule itself (ONE atomic piece of information per memory)
2. The type: fact, preference, decision, rule, context, or observation
3. Durability: core (permanent, like name/location/preferences), situational (temporary context), or episodic (one-time events)
4. Confidence (0-1): how certain you are this should be remembered

Focus on:
- User preferences and settings
- Biographical information (name, location, job, experience)
- Decisions and choices made
- Rules or constraints mentioned
- Important context for future conversations

Skip:
- Generic pleasantries
- Temporary task details (unless explicitly asked to remember)
- Information already commonly known

Respond with a JSON array of extracted memories:
[
  {
    "text": "User prefers dark mode",
    "memoryType": "preference",
    "durability": "core",
    "confidence": 0.95,
    "reasoning": "Explicitly stated preference"
  }
]

If nothing worth remembering, return an empty array: []`;

/**
 * Extract memories from conversation text.
 */
export async function extractMemories(
  conversationText: string,
  options?: {
    openai?: OpenAI;
    model?: string;
    apiKey?: string;
  }
): Promise<ExtractionResult> {
  const openai = options?.openai ?? new OpenAI({
    apiKey: options?.apiKey ?? process.env.OPENAI_API_KEY,
  });
  
  const model = options?.model ?? 'gpt-4o-mini';

  const response = await openai.chat.completions.create({
    model,
    messages: [
      { role: 'system', content: EXTRACTION_PROMPT },
      { role: 'user', content: `Extract memories from this conversation:\n\n${conversationText}` },
    ],
    temperature: 0.1,
    response_format: { type: 'json_object' },
  });

  const content = response.choices[0]?.message?.content ?? '[]';
  
  try {
    // Handle both array and object with memories key
    const parsed = JSON.parse(content);
    const memoriesArray = Array.isArray(parsed) ? parsed : (parsed.memories ?? []);
    
    const memories: ExtractedMemory[] = memoriesArray.map((m: Record<string, unknown>) => ({
      text: String(m.text ?? ''),
      memoryType: parseMemoryType(String(m.memoryType ?? 'fact')),
      durability: parseDurability(String(m.durability ?? 'situational')),
      confidence: typeof m.confidence === 'number' ? m.confidence : 0.8,
      reasoning: m.reasoning ? String(m.reasoning) : undefined,
    }));

    return { memories, rawResponse: content };
  } catch {
    return { memories: [], rawResponse: content };
  }
}

function parseMemoryType(type: string): MemoryType {
  const normalized = type.toLowerCase();
  switch (normalized) {
    case 'fact': return MemoryType.FACT;
    case 'rule': return MemoryType.RULE;
    case 'decision': return MemoryType.DECISION;
    case 'preference': return MemoryType.PREFERENCE;
    case 'context': return MemoryType.CONTEXT;
    case 'observation': return MemoryType.OBSERVATION;
    default: return MemoryType.FACT;
  }
}

function parseDurability(durability: string): Durability {
  const normalized = durability.toLowerCase();
  switch (normalized) {
    case 'core': return Durability.CORE;
    case 'situational': return Durability.SITUATIONAL;
    case 'episodic': return Durability.EPISODIC;
    default: return Durability.SITUATIONAL;
  }
}

/**
 * Convert extracted memories to MemoryCreate objects for storage.
 */
export function toMemoryCreates(extracted: ExtractedMemory[]): MemoryCreate[] {
  return extracted.map((m) => ({
    text: m.text,
    memoryType: m.memoryType,
    durability: m.durability,
  }));
}
