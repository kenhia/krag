/**
 * kragd API Type Contracts for krager
 *
 * TypeScript interfaces mirroring kragd/schemas.py exactly.
 * Update this file whenever kragd schemas change.
 *
 * Source: src/kragd/schemas.py
 * Generated: 2026-03-01 | Feature: 013-krager
 */

// ─────────────────────────────────────────────────────────────────
// Enums / Literals
// ─────────────────────────────────────────────────────────────────

export type LLMSlot = 'text' | 'code';
export type IndexMode = 'full' | 'incremental';
export type HealthStatus = 'healthy' | 'degraded';
export type IndexStatus = 'completed' | 'failed' | 'none' | 'running';
export type ConnectionStatus = 'connected' | 'disconnected' | 'error';
export type Theme = 'dark' | 'light';

// ─────────────────────────────────────────────────────────────────
// Request Models
// ─────────────────────────────────────────────────────────────────

/** POST /query request body. */
export interface QueryRequest {
  /** Query text (1–10000 chars) */
  query: string;
  /** Number of results (1–100) */
  top_k?: number | null;
  /** Prompt preset name */
  preset?: string | null;
  /** @deprecated Force specific LLM slot — use mode instead */
  llm?: LLMSlot | null;
  /** Named retrieval mode (e.g. default, code, docs) */
  mode?: string | null;
  /** Include debug metadata in response */
  include_debug?: boolean;
}

/** POST /retrieve request body. */
export interface RetrieveRequest {
  /** Query text (1–10000 chars) */
  query: string;
  /** Number of results (1–100) */
  top_k?: number | null;
  /** Named retrieval mode */
  mode?: string | null;
}

/** POST /debug/query request body. */
export interface DebugQueryRequest {
  /** Query text (1–10000 chars) */
  query: string;
  /** Number of results (1–100) */
  top_k?: number | null;
  /** Prompt preset name */
  preset?: string | null;
  /** @deprecated Force specific LLM slot — use mode instead */
  llm?: LLMSlot | null;
  /** Named retrieval mode */
  mode?: string | null;
}

/** Payload filters for QdrantSearchRequest. */
export interface QdrantFilters {
  /** Filter by file_type payload field */
  file_type?: string | null;
  /** Substring match on file_path (include) */
  file_path_contains?: string | null;
  /** Substring patterns to exclude from file_path */
  file_path_excludes?: string[] | null;
}

/** POST /debug/qdrant request body. */
export interface QdrantSearchRequest {
  /** Query text */
  query: string;
  /** Restrict to one vector space */
  vector_space?: string | null;
  /** Number of results (1–1000, default 10) */
  top_k?: number;
  /** Minimum similarity score (0.0–1.0) */
  score_threshold?: number | null;
  /** Include chunk payloads (default true) */
  with_payload?: boolean;
  /** Payload filtering */
  filters?: QdrantFilters | null;
}

/** POST /index request body. */
export interface IndexRequest {
  /** Indexing mode (default: 'incremental') */
  mode?: IndexMode;
  /** Override configured directories */
  directories?: string[] | null;
  /** Filter file extensions */
  file_types?: string[] | null;
  /** Additional exclusion patterns */
  exclude_patterns?: string[] | null;
  /** Override vector store path */
  vector_store_path?: string | null;
  /** Preview without indexing */
  dry_run?: boolean;
}

// ─────────────────────────────────────────────────────────────────
// Response Models
// ─────────────────────────────────────────────────────────────────

/** A source chunk returned in query/retrieve responses. */
export interface SourceChunk {
  chunk_id: string;
  file_path: string;
  score: number;
  rank: number;
  chunk_content: string;
  file_type: string;
  language?: string | null;
  function_name?: string | null;
  class_name?: string | null;
  start_line?: number | null;
  end_line?: number | null;
  collection?: string | null;
}

/** Debug information returned alongside query responses. */
export interface DebugMetadata {
  llm_used: string;
  llm_model: string;
  route: string;
  auto_routed: boolean;
  route_reason?: string | null;
  preset: string;
  mode?: string | null;
  collections_searched?: string[] | null;
  retrieval_time_ms: number;
  generation_time_ms: number;
  embedding_models_used: string[];
  vector_spaces_searched: string[];
  total_candidates_before_dedup: number;
  total_candidates_after_dedup: number;
  similarity_threshold: number;
  per_space_result_counts: Record<string, number>;
  lexicon_terms_injected: number;
  critic_scores: number[];
  chunks_pre_critic: number;
  chunks_post_critic: number;
}

/** POST /query response. */
export interface QueryResponse {
  answer: string;
  sources: SourceChunk[];
  debug?: DebugMetadata | null;
}

/** POST /debug/query response (debug always present). */
export interface DebugQueryResponse {
  answer: string;
  sources: SourceChunk[];
  debug: DebugMetadata;
}

/** POST /retrieve response. */
export interface RetrieveResponse {
  sources: SourceChunk[];
}

/** Single result from raw Qdrant search. */
export interface QdrantSearchResult {
  chunk_id: string;
  score: number;
  file_path: string;
  file_type: string;
  chunk_content: string;
  chunk_index: number;
  start_line?: number | null;
  end_line?: number | null;
}

/** POST /debug/qdrant response. */
export interface QdrantSearchResponse {
  results: QdrantSearchResult[];
  total_results: number;
  vector_space?: string | null;
}

/** Individual file indexing error. */
export interface IndexingFileError {
  file_path: string;
  error_type: string;
  error_message: string;
}

/** POST /index response and GET /index/status array element. */
export interface IndexResponse {
  job_id: string;
  status: IndexStatus;
  mode: IndexMode;
  files_scanned: number;
  files_processed: number;
  files_skipped: number;
  files_skipped_unchanged: number;
  files_skipped_other: number;
  files_errored: number;
  chunks_created: number;
  vectors_stored: number;
  duration_seconds: number;
  dry_run: boolean;
  errors: IndexingFileError[];
  collections: Record<string, number>;
}

/** Status of a single LLM slot. */
export interface LLMSlotStatus {
  loaded: boolean;
  model?: string | null;
  primary: boolean;
  idle_timeout_s?: number | null;
}

/** Vector store collection status. */
export interface VectorStoreStatus {
  collection: string;
  total_vectors: number;
  named_spaces: string[];
}

/** Per-collection stats for the multi-collection vector store. */
export interface CollectionStatus {
  collection_name: string;
  vectors_count: number;
  status: string;
}

/** GPU memory status. */
export interface VRAMStatus {
  total_mb: number;
  used_mb: number;
  free_mb: number;
}

/** Summary of a registered retrieval mode. */
export interface ModeInfo {
  name: string;
  description: string;
  collections: string[];
  llm_slot: LLMSlot;
  preset: string;
}

/** GET /status response. */
export interface ServiceStatus {
  version: string;
  uptime_seconds: number;
  llm: Record<string, LLMSlotStatus>;
  embedding_models: string[];
  vector_store: VectorStoreStatus;
  collections: Record<string, CollectionStatus>;
  modes: ModeInfo[];
  lexicon_loaded: boolean;
  lexicon_entry_count: number;
  vram?: VRAMStatus | null;
}

/** GET /health response. */
export interface HealthResponse {
  status: HealthStatus;
  version: string;
}

/** POST /shutdown response. */
export interface ShutdownResponse {
  message: string;
}

/** POST /lexicon/refresh response. */
export interface LexiconRefreshResponse {
  entries: number;
  status: string;
}

/** Full detail for a single mode (GET /modes/{name}). */
export interface ModeDetailResponse {
  name: string;
  description: string;
  collections: Record<string, number>;
  llm_slot: LLMSlot;
  preset: string;
  top_k: number;
  similarity_threshold: number;
  critic_enabled: boolean;
  critic_threshold: number;
}

/** GET /modes response. */
export interface ModeListResponse {
  modes: ModeInfo[];
}

// ─────────────────────────────────────────────────────────────────
// SSE Event Types (Sprint 012 streaming endpoints)
// ─────────────────────────────────────────────────────────────────

/**
 * Events from POST /query/stream (SSE over POST).
 *
 * Wire format: each SSE frame has `event: <type>` and `data: <JSON>`.
 * These types represent the parsed data payload per event type.
 *
 * Event sequence: query:sources → query:token* → query:done
 * On failure: query:error (may replace token/done sequence)
 */
export type QueryStreamEvent =
  | { type: 'query:sources'; data: { sources: SourceChunk[] } }
  | { type: 'query:token'; data: { token: string } }
  | { type: 'query:done'; data: { answer: string; sources: SourceChunk[]; debug: DebugMetadata | null } }
  | { type: 'query:error'; data: { error: string } };

/**
 * Events from GET /index/stream (SSE over GET).
 *
 * Wire format: each SSE frame has `event: <type>` and `data: <JSON>`.
 *
 * Event sequence: index:progress* → index:complete
 * If no job active: index:idle (stream closes)
 * On failure: index:error (stream closes)
 */
export type IndexStreamEvent =
  | { type: 'index:idle'; data: { message: string } }
  | { type: 'index:progress'; data: { current: number; total: number; stage: string } }
  | { type: 'index:complete'; data: { job_id: string; status: string; files_processed: number; duration_seconds: number } }
  | { type: 'index:error'; data: { job_id: string; error: string } };

// ─────────────────────────────────────────────────────────────────
// Client-side error types
// ─────────────────────────────────────────────────────────────────

/** Typed kragd API error (wraps HTTP error responses). */
export interface KragdError {
  status: number;
  message: string;
  detail?: unknown;
}

/** Well-known HTTP error codes from kragd. */
export const KRAGD_ERROR_CODES = {
  VALIDATION: 422,
  CONFLICT: 409,
  NOT_READY: 503,
  SERVER_ERROR: 500,
} as const;

// ─────────────────────────────────────────────────────────────────
// API Endpoint Map (documentation only — not runtime)
// ─────────────────────────────────────────────────────────────────

/**
 * Endpoint summary for reference.
 *
 * GET  /health              → HealthResponse
 * GET  /status              → ServiceStatus
 * POST /query               → QueryResponse
 * POST /query/stream        → SSE: QueryStreamEvent[]    (Sprint 012)
 * POST /retrieve            → RetrieveResponse
 * GET  /modes               → ModeListResponse
 * GET  /modes/{name}        → ModeDetailResponse
 * POST /index               → IndexResponse
 * GET  /index/status        → IndexResponse[]
 * GET  /index/stream        → SSE: IndexStreamEvent[]    (Sprint 012)
 * POST /debug/query         → DebugQueryResponse
 * POST /debug/qdrant        → QdrantSearchResponse
 * POST /lexicon/refresh     → LexiconRefreshResponse
 * POST /shutdown            → ShutdownResponse
 */
