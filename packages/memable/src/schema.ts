/**
 * Memory schema - matches Python engram-ai for cross-language compatibility.
 */

/**
 * Memory durability tier.
 */
export enum Durability {
  /** Stable facts that rarely change (name, preferences, biographical). */
  CORE = 'core',
  /** Temporary context with explicit end date (traveling, project work). */
  SITUATIONAL = 'situational',
  /** Things that happened, decays over time (conversations, events). */
  EPISODIC = 'episodic',
}

/**
 * Semantic type of memory content.
 */
export enum MemoryType {
  /** A factual statement (e.g., 'API rate limit is 100/min'). */
  FACT = 'fact',
  /** A rule or guideline to follow (e.g., 'Always use TypeScript strict mode'). */
  RULE = 'rule',
  /** A decision that was made (e.g., 'Chose Tailwind for utility-first CSS'). */
  DECISION = 'decision',
  /** A preference or like/dislike (e.g., 'Prefers dark mode'). */
  PREFERENCE = 'preference',
  /** Background context (e.g., 'Currently working on authentication refactor'). */
  CONTEXT = 'context',
  /** An observation or insight (e.g., 'User tends to ask follow-up questions'). */
  OBSERVATION = 'observation',
}

/**
 * How the memory was created.
 */
export enum MemorySource {
  /** User directly stated this fact. */
  EXPLICIT = 'explicit',
  /** Extracted/inferred from conversation. */
  INFERRED = 'inferred',
  /** Created by system (consolidation, migration, etc.). */
  SYSTEM = 'system',
}

/**
 * A memory item with full metadata.
 */
export interface Memory {
  /** Unique identifier for this memory. */
  id: string;
  /** The memory content (what we're remembering). */
  text: string;
  /** How permanent this memory is. */
  durability: Durability;
  /** Semantic type of this memory (fact, rule, decision, etc.). */
  memoryType?: MemoryType | null;
  /** Confidence score (0-1) for inferred memories. */
  confidence: number;
  /** How this memory was created. */
  source: MemorySource;
  /** When this fact became true. */
  validFrom: Date;
  /** When this fact expires (null = permanent). */
  validUntil?: Date | null;
  /** ID of the memory this one replaces (previous version). */
  supersedes?: string | null;
  /** ID of the memory that replaced this one (next version). */
  supersededBy?: string | null;
  /** When this memory was superseded. */
  supersededAt?: Date | null;
  /** When this memory was stored. */
  createdAt: Date;
  /** Last time this memory was retrieved (for decay calculations). */
  lastAccessedAt?: Date | null;
  /** Number of times this memory was retrieved. */
  accessCount: number;
  /** Optional tags for categorization. */
  tags: string[];
  /** Additional metadata. */
  metadata: Record<string, unknown>;
}

/**
 * Input for creating a new memory.
 */
export interface MemoryCreate {
  text: string;
  durability?: Durability;
  memoryType?: MemoryType | null;
  confidence?: number;
  source?: MemorySource;
  validFrom?: Date;
  validUntil?: Date | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

/**
 * Input for updating a memory (creates new version in chain).
 */
export interface MemoryUpdate {
  text: string;
  confidence?: number;
  source?: MemorySource;
  validFrom?: Date;
  validUntil?: Date | null;
}

/**
 * Query parameters for memory retrieval.
 */
export interface MemoryQuery {
  /** Semantic search query. */
  query: string;
  /** Maximum number of results. */
  limit?: number;
  /** Minimum confidence threshold. */
  minConfidence?: number;
  /** Filter by durability tier(s). */
  durability?: Durability[];
  /** Filter by memory type(s). */
  memoryType?: MemoryType[];
  /** Include superseded (old version) memories. */
  includeSuperseded?: boolean;
  /** Include memories past their validUntil date. */
  includeExpired?: boolean;
  /** Filter by tags (any match). */
  tags?: string[];
  /** Check validity at this time (default: now). */
  validAt?: Date;
}

/**
 * Namespace tuple for scoping memories.
 */
export type Namespace = string[];

/**
 * Check if a memory is valid at a given time.
 */
export function isMemoryValid(memory: Memory, at: Date = new Date()): boolean {
  // Superseded memories are not valid
  if (memory.supersededBy != null) {
    return false;
  }

  // Check temporal validity
  if (memory.validFrom && at < memory.validFrom) {
    return false;
  }
  if (memory.validUntil && at > memory.validUntil) {
    return false;
  }

  return true;
}

/**
 * Check if this is the current version (not superseded).
 */
export function isMemoryCurrent(memory: Memory): boolean {
  return memory.supersededBy == null;
}
