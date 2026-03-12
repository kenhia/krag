/**
 * Config Store Schema — TypeScript interface for the persisted configuration.
 *
 * This file defines the shape of `settings.json` stored by the Tauri Store plugin.
 * It is the contract between the config-store service and all state modules.
 *
 * File: specs/014-krager-enhancements/contracts/config-schema.ts
 */

// ─── Persisted Configuration ─────────────────────────────────────────────────

/** Connection settings persisted between sessions. */
export interface ConnectionConfig {
  /** Last successful connection host. Default: "localhost" */
  host: string;
  /** Last successful connection port. Default: 8742. Range: 1–65535 */
  port: number;
}

/** Query parameter defaults persisted between sessions. */
export interface QueryConfig {
  /** Default top-k results. null = use server default. Range: 1–100 */
  top_k: number | null;
  /** Default preset name. null = use server default. One of: strict, balanced, verbose, code */
  preset: string | null;
  /** Include debug metadata in query responses. Default: false */
  include_debug: boolean;
  /** Display source chunks in answer view. Default: true */
  show_sources: boolean;
}

/** Critic display configuration. */
export interface CriticConfig {
  /** Enable critic score display. Default: false */
  enabled: boolean;
  /** Critic score threshold for flagging low-quality answers. Range: 0.0–1.0. Default: 0.5 */
  cut_off: number;
}

/** Display/UI preferences. */
export interface DisplayConfig {
  /** Window opacity. Range: 0.3–1.0. Default: 1.0 */
  opacity: number;
  /** Theme preference override. null = follow OS. */
  theme: 'light' | 'dark' | null;
}

/** Root configuration object — shape of settings.json on disk. */
export interface UserConfig {
  connection: ConnectionConfig;
  query: QueryConfig;
  critic: CriticConfig;
  display: DisplayConfig;
}

// ─── Defaults ────────────────────────────────────────────────────────────────

/** Hardcoded default configuration values. Used when no config file exists or on corruption. */
export const USER_CONFIG_DEFAULTS: UserConfig = {
  connection: {
    host: 'localhost',
    port: 8742,
  },
  query: {
    top_k: null,
    preset: null,
    include_debug: false,
    show_sources: true,
  },
  critic: {
    enabled: false,
    cut_off: 0.5,
  },
  display: {
    opacity: 1.0,
    theme: null,
  },
};

// ─── Validation ──────────────────────────────────────────────────────────────

/** Valid preset names (must match kragd VALID_PRESETS). */
export const VALID_PRESETS = ['strict', 'balanced', 'verbose', 'code'] as const;
export type PresetName = (typeof VALID_PRESETS)[number];

/** Preset metadata for dropdown display. */
export interface PresetOption {
  value: PresetName;
  label: string;
  description: string;
}

/** Static preset options for the UI dropdown. */
export const PRESET_OPTIONS: PresetOption[] = [
  { value: 'strict', label: 'Strict', description: 'Concise, source-grounded answers only' },
  { value: 'balanced', label: 'Balanced', description: 'Detailed answers with numbered citations (default)' },
  { value: 'verbose', label: 'Verbose', description: 'Exploratory answers with full context' },
  { value: 'code', label: 'Code', description: 'Code-focused answers with snippets and file references' },
];

// ─── Config Store Service Interface ──────────────────────────────────────────

/** Interface for the config store service. */
export interface ConfigStoreService {
  /** Whether the store has been initialized. */
  readonly ready: boolean;

  /**
   * Load config from disk. Call once at app startup.
   * Falls back to defaults on corruption or missing file.
   */
  init(): Promise<void>;

  /**
   * Get a config value by dot-path key.
   * @example store.get('connection.host') => 'karch9'
   */
  get<T>(key: string): Promise<T | undefined>;

  /**
   * Set a config value by dot-path key. Persists with debounced auto-save.
   * @example store.set('connection.host', 'karch9')
   */
  set(key: string, value: unknown): Promise<void>;

  /**
   * Get the full config object (for hydrating state modules at startup).
   */
  getAll(): Promise<UserConfig>;

  /**
   * Release resources. Call on app shutdown.
   */
  destroy(): Promise<void>;
}

// ─── Source Reference (display projection) ───────────────────────────────────

/** Compact source reference for the query answer view (no chunk text). */
export interface SourceReference {
  file_path: string;
  score: number;
  collection: string;
  rank: number;
}
