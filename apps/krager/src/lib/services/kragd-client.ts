/**
 * kragd HTTP Client
 *
 * Singleton HTTP client wrapping @tauri-apps/plugin-http fetch.
 * All requests go through kragdFetch<T> which handles JSON parsing,
 * error extraction, and typed responses.
 */

import { fetch as tauriFetch } from "@tauri-apps/plugin-http";
import type {
	DebugQueryRequest,
	DebugQueryResponse,
	HealthResponse,
	IndexRequest,
	IndexResponse,
	LexiconRefreshResponse,
	ModeDetailResponse,
	ModeListResponse,
	QdrantSearchRequest,
	QdrantSearchResponse,
	QueryRequest,
	QueryResponse,
	RetrieveRequest,
	RetrieveResponse,
	ServiceStatus,
} from "$lib/types";
import { KragdError } from "$lib/types";

// ─────────────────────────────────────────────────────────────────
// Base URL management
// ─────────────────────────────────────────────────────────────────

let baseUrl = "http://localhost:8742";

export function getBaseUrl(): string {
	return baseUrl;
}

export function setBaseUrl(url: string): void {
	baseUrl = url;
}

// ─────────────────────────────────────────────────────────────────
// Core fetch helper
// ─────────────────────────────────────────────────────────────────

/**
 * Typed HTTP fetch helper for kragd API calls.
 *
 * - Prepends baseUrl to path
 * - Sets Content-Type: application/json
 * - Deserializes JSON response
 * - Maps HTTP errors to KragdError with human-readable messages
 * - Catches network errors (fetch rejection)
 * - Catches JSON parse failures (schema mismatch)
 */
export async function kragdFetch<T>(path: string, init?: RequestInit): Promise<T> {
	const url = `${baseUrl}${path}`;
	const options: RequestInit = {
		method: "GET",
		...init,
		headers: {
			"Content-Type": "application/json",
			...init?.headers,
		},
	};

	const startTime = performance.now();
	let response: Response;
	try {
		response = await tauriFetch(url, options);
	} catch (err) {
		// Network error — server unreachable
		throw new KragdError(
			0,
			`Cannot reach kragd at ${baseUrl}`,
			err instanceof Error ? err.message : String(err),
		);
	}

	if (!response.ok) {
		return handleHttpError(response);
	}

	// Parse JSON — catch schema mismatches
	try {
		const data = await response.json();
		const overheadMs = performance.now() - startTime;
		if (typeof console !== "undefined") {
			console.debug(`[kragdFetch] ${options.method} ${path} — ${overheadMs.toFixed(1)}ms`);
			if (overheadMs > 500) {
				console.warn(
					`[kragdFetch] High client overhead: ${options.method} ${path} took ${overheadMs.toFixed(1)}ms (>500ms threshold)`,
				);
			}
		}
		return data as T;
	} catch {
		const text = await response.text().catch(() => "(unreadable body)");
		throw new KragdError(
			response.status,
			`Response schema mismatch: expected JSON but got: ${text.slice(0, 200)}`,
			text,
		);
	}
}

// ─────────────────────────────────────────────────────────────────
// Error handling
// ─────────────────────────────────────────────────────────────────

async function handleHttpError(response: Response): Promise<never> {
	let body: Record<string, unknown> | null = null;
	try {
		body = await response.json();
	} catch {
		// non-JSON error body — continue with null
	}

	const detail = body?.detail;
	const status = response.status;

	switch (status) {
		case 422: {
			// FastAPI validation error — detail is an array of {loc, msg, type}
			const msg = formatValidationDetail(detail);
			throw new KragdError(422, `Validation error: ${msg}`, detail);
		}
		case 409:
			throw new KragdError(409, `Conflict: ${detailString(detail)}`, detail);
		case 503:
			throw new KragdError(503, `kragd is not ready: ${detailString(detail)}`, detail);
		case 500:
			throw new KragdError(500, `Server error: ${detailString(detail)}`, detail);
		default:
			throw new KragdError(
				status,
				`HTTP ${status}: ${detailString(detail) || response.statusText}`,
				detail,
			);
	}
}

function formatValidationDetail(detail: unknown): string {
	if (Array.isArray(detail)) {
		return detail
			.map((d: { loc?: unknown[]; msg?: string }) => {
				const loc = Array.isArray(d.loc) ? d.loc.join(".") : "";
				return loc ? `${loc}: ${d.msg}` : String(d.msg);
			})
			.join("; ");
	}
	return detailString(detail);
}

function detailString(detail: unknown): string {
	if (typeof detail === "string") return detail;
	if (detail == null) return "";
	return JSON.stringify(detail);
}

// ─────────────────────────────────────────────────────────────────
// API endpoint functions
// ─────────────────────────────────────────────────────────────────

/** Connection timeout for health checks (ms). */
const HEALTH_TIMEOUT_MS = 15_000;

/**
 * Check kragd health at a specific host:port.
 * Uses a custom baseUrl (not the module-level one) for initial connection probing.
 * Aborts after HEALTH_TIMEOUT_MS to avoid hanging on unreachable hosts.
 */
export async function getHealth(host: string, port: number): Promise<HealthResponse> {
	const url = `http://${host}:${port}/health`;
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
	let response: Response;
	try {
		response = await tauriFetch(url, {
			method: "GET",
			headers: { "Content-Type": "application/json" },
			signal: controller.signal,
		});
	} catch (err) {
		if (controller.signal.aborted) {
			throw new KragdError(
				0,
				`Connection timed out after ${HEALTH_TIMEOUT_MS / 1000}s — ${host}:${port} is unreachable`,
				"timeout",
			);
		}
		const detail = err instanceof Error ? err.message : String(err);
		throw new KragdError(0, `Cannot reach kragd at ${host}:${port} — ${detail}`, detail);
	} finally {
		clearTimeout(timer);
	}

	if (!response.ok) {
		throw new KragdError(response.status, `Health check failed: HTTP ${response.status}`);
	}

	try {
		return (await response.json()) as HealthResponse;
	} catch {
		throw new KragdError(0, "Invalid health response from kragd");
	}
}

/**
 * Get full system status from kragd.
 * Uses the module-level baseUrl.
 */
export async function getStatus(): Promise<ServiceStatus> {
	return kragdFetch<ServiceStatus>("/status");
}

/**
 * Submit a query to kragd.
 * Returns answer text and source chunks.
 */
export async function postQuery(req: QueryRequest): Promise<QueryResponse> {
	return kragdFetch<QueryResponse>("/query", {
		method: "POST",
		body: JSON.stringify(req),
	});
}

/**
 * Retrieve source chunks without LLM generation.
 */
export async function postRetrieve(req: RetrieveRequest): Promise<RetrieveResponse> {
	return kragdFetch<RetrieveResponse>("/retrieve", {
		method: "POST",
		body: JSON.stringify(req),
	});
}

/**
 * List available retrieval modes.
 */
export async function getModes(): Promise<ModeListResponse> {
	return kragdFetch<ModeListResponse>("/modes");
}

/**
 * Get detailed configuration for a specific mode.
 */
export async function getModeDetail(name: string): Promise<ModeDetailResponse> {
	return kragdFetch<ModeDetailResponse>(`/modes/${encodeURIComponent(name)}`);
}

/**
 * Trigger an indexing job.
 */
export async function triggerIndex(req: IndexRequest): Promise<IndexResponse> {
	return kragdFetch<IndexResponse>("/index", {
		method: "POST",
		body: JSON.stringify(req),
	});
}

/**
 * Get status of recent indexing jobs.
 */
export async function getIndexStatus(): Promise<IndexResponse[]> {
	return kragdFetch<IndexResponse[]>("/index/status");
}

/**
 * Submit a debug query to kragd.
 * Returns answer, sources, and full debug metadata.
 */
export async function postDebugQuery(req: DebugQueryRequest): Promise<DebugQueryResponse> {
	return kragdFetch<DebugQueryResponse>("/debug/query", {
		method: "POST",
		body: JSON.stringify(req),
	});
}

/**
 * Submit a raw Qdrant vector search.
 * Returns scored search results directly from the vector store.
 */
export async function postDebugQdrant(req: QdrantSearchRequest): Promise<QdrantSearchResponse> {
	return kragdFetch<QdrantSearchResponse>("/debug/qdrant", {
		method: "POST",
		body: JSON.stringify(req),
	});
}

/**
 * Refresh the lexicon from disk.
 * Returns the updated entry count.
 */
export async function refreshLexicon(): Promise<LexiconRefreshResponse> {
	return kragdFetch<LexiconRefreshResponse>("/lexicon/refresh", {
		method: "POST",
	});
}
