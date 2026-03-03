/**
 * SSE Streaming Helpers
 *
 * SSE POST helper for POST /query/stream using @tauri-apps/plugin-http
 * fetch + ReadableStream text line parser.
 *
 * SSE GET helper for GET /index/stream using the same approach
 * (EventSource won't work with Tauri plugin-http on Linux due to WebKitGTK buffering).
 *
 * Typed event parsers returning QueryStreamEvent and IndexStreamEvent
 * discriminated unions.
 */

import { fetch as tauriFetch } from "@tauri-apps/plugin-http";
import type { QueryRequest, QueryStreamEvent, IndexStreamEvent } from "$lib/types";

// ─────────────────────────────────────────────────────────────────
// Known SSE event types
// ─────────────────────────────────────────────────────────────────

const QUERY_EVENT_TYPES = new Set(["query:sources", "query:token", "query:done", "query:error"]);
const INDEX_EVENT_TYPES = new Set(["index:idle", "index:progress", "index:complete", "index:error"]);

// ─────────────────────────────────────────────────────────────────
// SSE line parser
// ─────────────────────────────────────────────────────────────────

/**
 * Parse an SSE event type and data payload into a typed event object.
 * Returns null if the event type is unknown or JSON is malformed.
 */
export function parseSSELine(
	eventType: string,
	dataString: string,
): QueryStreamEvent | IndexStreamEvent | null {
	if (!QUERY_EVENT_TYPES.has(eventType) && !INDEX_EVENT_TYPES.has(eventType)) {
		return null;
	}

	try {
		const data = JSON.parse(dataString);
		return { type: eventType, data } as QueryStreamEvent | IndexStreamEvent;
	} catch {
		return null;
	}
}

// ─────────────────────────────────────────────────────────────────
// Stream reader — parses SSE text frames from a ReadableStream
// ─────────────────────────────────────────────────────────────────

async function readSSEStream<T extends QueryStreamEvent | IndexStreamEvent>(
	body: ReadableStream<Uint8Array>,
	onEvent: (event: T) => void,
	signal?: AbortSignal,
): Promise<void> {
	const reader = body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";
	let currentEvent = "";
	let currentData = "";

	try {
		while (true) {
			if (signal?.aborted) break;

			const { done, value } = await reader.read();
			if (done) break;

			buffer += decoder.decode(value, { stream: true });
			const lines = buffer.split("\n");
			// Keep incomplete last line in buffer
			buffer = lines.pop() ?? "";

			for (const line of lines) {
				if (line.startsWith("event: ")) {
					currentEvent = line.slice(7).trim();
				} else if (line.startsWith("data: ")) {
					currentData = line.slice(6);
				} else if (line === "" && currentEvent && currentData) {
					// Empty line = end of SSE frame
					const parsed = parseSSELine(currentEvent, currentData);
					if (parsed) {
						onEvent(parsed as T);
					}
					currentEvent = "";
					currentData = "";
				}
			}
		}

		// Process any remaining buffered data
		if (currentEvent && currentData) {
			const parsed = parseSSELine(currentEvent, currentData);
			if (parsed) {
				onEvent(parsed as T);
			}
		}
	} finally {
		reader.releaseLock();
	}
}

// ─────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────

export interface StreamOptions {
	signal?: AbortSignal;
	onError?: (error: Error) => void;
}

/**
 * Stream query results from POST /query/stream.
 *
 * Uses @tauri-apps/plugin-http fetch with ReadableStream to parse
 * SSE events. Calls onEvent for each parsed QueryStreamEvent.
 */
export async function streamQuerySSE(
	baseUrl: string,
	request: QueryRequest,
	onEvent: (event: QueryStreamEvent) => void,
	options?: StreamOptions,
): Promise<void> {
	try {
		const response = await tauriFetch(`${baseUrl}/query/stream`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(request),
			signal: options?.signal,
		});

		if (!response.ok) {
			throw new Error(`SSE connection failed: HTTP ${response.status}`);
		}

		if (!response.body) {
			throw new Error("SSE response has no body stream");
		}

		await readSSEStream<QueryStreamEvent>(response.body, onEvent, options?.signal);
	} catch (err) {
		if (options?.onError) {
			options.onError(err instanceof Error ? err : new Error(String(err)));
		} else {
			throw err;
		}
	}
}

/**
 * Stream index progress from GET /index/stream.
 *
 * Uses @tauri-apps/plugin-http fetch with ReadableStream to parse
 * SSE events. Calls onEvent for each parsed IndexStreamEvent.
 */
export async function streamIndexSSE(
	baseUrl: string,
	onEvent: (event: IndexStreamEvent) => void,
	options?: StreamOptions,
): Promise<void> {
	try {
		const response = await tauriFetch(`${baseUrl}/index/stream`, {
			method: "GET",
			headers: { Accept: "text/event-stream" },
			signal: options?.signal,
		});

		if (!response.ok) {
			throw new Error(`SSE connection failed: HTTP ${response.status}`);
		}

		if (!response.body) {
			throw new Error("SSE response has no body stream");
		}

		await readSSEStream<IndexStreamEvent>(response.body, onEvent, options?.signal);
	} catch (err) {
		if (options?.onError) {
			options.onError(err instanceof Error ? err : new Error(String(err)));
		} else {
			throw err;
		}
	}
}
