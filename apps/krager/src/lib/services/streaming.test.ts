import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockFetch } = vi.hoisted(() => ({
	mockFetch: vi.fn(),
}));
vi.mock("@tauri-apps/plugin-http", () => ({
	fetch: mockFetch,
}));

import type { IndexStreamEvent, QueryStreamEvent } from "$lib/types";
import { parseSSELine, streamIndexSSE, streamQuerySSE } from "./streaming";

// Helper to create a ReadableStream from lines
function createSSEStream(lines: string[]): ReadableStream<Uint8Array> {
	const encoder = new TextEncoder();
	return new ReadableStream({
		start(controller) {
			for (const line of lines) {
				controller.enqueue(encoder.encode(`${line}\n`));
			}
			controller.close();
		},
	});
}

describe("streaming", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe("parseSSELine", () => {
		it("parses event and data lines into an SSE event", () => {
			const result = parseSSELine("query:sources", '{"sources": []}');
			expect(result).toEqual({ type: "query:sources", data: { sources: [] } });
		});

		it("returns null for unknown event types", () => {
			const result = parseSSELine("unknown:event", '{"foo": "bar"}');
			expect(result).toBeNull();
		});

		it("returns null for malformed JSON data", () => {
			const result = parseSSELine("query:token", "not json");
			expect(result).toBeNull();
		});

		it("parses query:token event", () => {
			const result = parseSSELine("query:token", '{"token": "hello"}');
			expect(result).toEqual({ type: "query:token", data: { token: "hello" } });
		});

		it("parses query:done event", () => {
			const data = '{"answer": "hi", "sources": [], "debug": null}';
			const result = parseSSELine("query:done", data);
			expect(result).toEqual({
				type: "query:done",
				data: { answer: "hi", sources: [], debug: null },
			});
		});

		it("parses query:error event", () => {
			const result = parseSSELine("query:error", '{"error": "bad request"}');
			expect(result).toEqual({ type: "query:error", data: { error: "bad request" } });
		});

		it("parses index:idle event", () => {
			const result = parseSSELine("index:idle", '{"message": "No active job"}');
			expect(result).toEqual({ type: "index:idle", data: { message: "No active job" } });
		});

		it("parses index:progress event", () => {
			const data = '{"current": 5, "total": 10, "stage": "scanning"}';
			const result = parseSSELine("index:progress", data);
			expect(result).toEqual({
				type: "index:progress",
				data: { current: 5, total: 10, stage: "scanning" },
			});
		});

		it("parses index:complete event", () => {
			const data =
				'{"job_id": "j1", "status": "completed", "files_processed": 10, "duration_seconds": 5.2}';
			const result = parseSSELine("index:complete", data);
			expect(result).toEqual({
				type: "index:complete",
				data: { job_id: "j1", status: "completed", files_processed: 10, duration_seconds: 5.2 },
			});
		});

		it("parses index:error event", () => {
			const result = parseSSELine("index:error", '{"job_id": "j1", "error": "disk full"}');
			expect(result).toEqual({
				type: "index:error",
				data: { job_id: "j1", error: "disk full" },
			});
		});
	});

	describe("streamQuerySSE", () => {
		it("streams query events from POST /query/stream", async () => {
			const sseLines = [
				"event: query:sources",
				'data: {"sources": [{"chunk_id": "c1", "file_path": "/a.py", "score": 0.9, "rank": 1, "chunk_content": "code", "file_type": "python"}]}',
				"",
				"event: query:token",
				'data: {"token": "Hello"}',
				"",
				"event: query:token",
				'data: {"token": " world"}',
				"",
				"event: query:done",
				'data: {"answer": "Hello world", "sources": [], "debug": null}',
				"",
			];

			mockFetch.mockResolvedValue({
				ok: true,
				status: 200,
				body: createSSEStream(sseLines),
			});

			const events: QueryStreamEvent[] = [];
			await streamQuerySSE("http://localhost:8742", { query: "test" }, (event) =>
				events.push(event),
			);

			expect(events.length).toBe(4);
			expect(events[0].type).toBe("query:sources");
			expect(events[1].type).toBe("query:token");
			expect((events[1] as { type: "query:token"; data: { token: string } }).data.token).toBe(
				"Hello",
			);
			expect(events[2].type).toBe("query:token");
			expect(events[3].type).toBe("query:done");
		});

		it("calls onError callback on network failure", async () => {
			mockFetch.mockRejectedValue(new TypeError("Failed to fetch"));

			const events: QueryStreamEvent[] = [];
			const errors: Error[] = [];
			await streamQuerySSE(
				"http://localhost:8742",
				{ query: "test" },
				(event) => events.push(event),
				{ onError: (err) => errors.push(err) },
			);

			expect(events).toHaveLength(0);
			expect(errors).toHaveLength(1);
			expect(errors[0].message).toContain("Failed to fetch");
		});

		it("respects AbortSignal", async () => {
			const controller = new AbortController();
			controller.abort();

			mockFetch.mockRejectedValue(new DOMException("Aborted", "AbortError"));

			const events: QueryStreamEvent[] = [];
			const errors: Error[] = [];
			await streamQuerySSE(
				"http://localhost:8742",
				{ query: "test" },
				(event) => events.push(event),
				{ signal: controller.signal, onError: (err) => errors.push(err) },
			);

			expect(events).toHaveLength(0);
			expect(errors).toHaveLength(1);
		});
	});

	describe("streamIndexSSE", () => {
		it("streams index events from GET /index/stream", async () => {
			const sseLines = [
				"event: index:progress",
				'data: {"current": 3, "total": 10, "stage": "indexing"}',
				"",
				"event: index:complete",
				'data: {"job_id": "j1", "status": "completed", "files_processed": 10, "duration_seconds": 2.5}',
				"",
			];

			mockFetch.mockResolvedValue({
				ok: true,
				status: 200,
				body: createSSEStream(sseLines),
			});

			const events: IndexStreamEvent[] = [];
			await streamIndexSSE("http://localhost:8742", (event) => events.push(event));

			expect(events.length).toBe(2);
			expect(events[0].type).toBe("index:progress");
			expect(events[1].type).toBe("index:complete");
		});

		it("handles index:idle event", async () => {
			const sseLines = ["event: index:idle", 'data: {"message": "No active indexing job"}', ""];

			mockFetch.mockResolvedValue({
				ok: true,
				status: 200,
				body: createSSEStream(sseLines),
			});

			const events: IndexStreamEvent[] = [];
			await streamIndexSSE("http://localhost:8742", (event) => events.push(event));

			expect(events.length).toBe(1);
			expect(events[0].type).toBe("index:idle");
		});
	});
});
