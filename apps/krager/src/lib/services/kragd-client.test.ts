import { beforeEach, describe, expect, it, vi } from "vitest";

// Must use vi.hoisted() so the variable exists when the hoisted vi.mock factory runs
const { mockFetch } = vi.hoisted(() => ({
	mockFetch: vi.fn(),
}));
vi.mock("@tauri-apps/plugin-http", () => ({
	fetch: mockFetch,
}));

import { KragdError } from "$lib/types";
import {
	getBaseUrl,
	getHealth,
	getIndexStatus,
	getModeDetail,
	getModes,
	getStatus,
	kragdFetch,
	postDebugQdrant,
	postDebugQuery,
	postQuery,
	postRetrieve,
	refreshLexicon,
	setBaseUrl,
	triggerIndex,
} from "./kragd-client";

function jsonResponse(data: unknown, status = 200, ok = true): Response {
	return {
		ok,
		status,
		statusText: ok ? "OK" : "Error",
		headers: new Headers({ "content-type": "application/json" }),
		json: () => Promise.resolve(data),
		text: () => Promise.resolve(JSON.stringify(data)),
	} as unknown as Response;
}

describe("kragd-client", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		setBaseUrl("http://localhost:8742");
	});

	describe("getBaseUrl / setBaseUrl", () => {
		it("returns default base URL", () => {
			expect(getBaseUrl()).toBe("http://localhost:8742");
		});

		it("updates base URL", () => {
			setBaseUrl("http://myhost:9999");
			expect(getBaseUrl()).toBe("http://myhost:9999");
		});
	});

	describe("kragdFetch", () => {
		it("makes GET request and returns typed JSON", async () => {
			const data = { status: "healthy", version: "1.0.0" };
			mockFetch.mockResolvedValue(jsonResponse(data));

			const result = await kragdFetch<{ status: string; version: string }>("/health");

			expect(mockFetch).toHaveBeenCalledWith("http://localhost:8742/health", {
				method: "GET",
				headers: { "Content-Type": "application/json" },
			});
			expect(result).toEqual(data);
		});

		it("makes POST request with body", async () => {
			const reqBody = { query: "test query" };
			const resData = { answer: "test answer", sources: [] };
			mockFetch.mockResolvedValue(jsonResponse(resData));

			const result = await kragdFetch("/query", {
				method: "POST",
				body: JSON.stringify(reqBody),
			});

			expect(mockFetch).toHaveBeenCalledWith("http://localhost:8742/query", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(reqBody),
			});
			expect(result).toEqual(resData);
		});

		it("throws KragdError on 422 validation error", async () => {
			const detail = [{ loc: ["body", "query"], msg: "field required", type: "missing" }];
			mockFetch.mockResolvedValue(jsonResponse({ detail }, 422, false));

			await expect(kragdFetch("/query")).rejects.toThrow(KragdError);
			try {
				await kragdFetch("/query");
			} catch (e) {
				expect(e).toBeInstanceOf(KragdError);
				const err = e as KragdError;
				expect(err.status).toBe(422);
				expect(err.detail).toEqual(detail);
				expect(err.message).toContain("Validation error");
			}
		});

		it("throws KragdError on 409 conflict", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "Already indexing" }, 409, false));

			try {
				await kragdFetch("/index");
			} catch (e) {
				expect(e).toBeInstanceOf(KragdError);
				const err = e as KragdError;
				expect(err.status).toBe(409);
				expect(err.message).toContain("Conflict");
			}
		});

		it("throws KragdError on 503 not ready", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "Service not ready" }, 503, false));

			try {
				await kragdFetch("/status");
			} catch (e) {
				expect(e).toBeInstanceOf(KragdError);
				const err = e as KragdError;
				expect(err.status).toBe(503);
				expect(err.message).toContain("not ready");
			}
		});

		it("throws KragdError on 500 server error", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "Internal server error" }, 500, false));

			try {
				await kragdFetch("/query");
			} catch (e) {
				expect(e).toBeInstanceOf(KragdError);
				const err = e as KragdError;
				expect(err.status).toBe(500);
				expect(err.message).toContain("Server error");
			}
		});

		it("throws KragdError on network error", async () => {
			mockFetch.mockRejectedValue(new TypeError("Failed to fetch"));

			try {
				await kragdFetch("/health");
			} catch (e) {
				expect(e).toBeInstanceOf(KragdError);
				const err = e as KragdError;
				expect(err.status).toBe(0);
				expect(err.message).toContain("Cannot reach kragd");
			}
		});

		it("handles non-JSON response gracefully", async () => {
			const res = {
				ok: true,
				status: 200,
				statusText: "OK",
				headers: new Headers({ "content-type": "text/plain" }),
				json: () => Promise.reject(new SyntaxError("Unexpected token")),
				text: () => Promise.resolve("not json"),
			} as unknown as Response;
			mockFetch.mockResolvedValue(res);

			try {
				await kragdFetch("/health");
			} catch (e) {
				expect(e).toBeInstanceOf(KragdError);
				const err = e as KragdError;
				expect(err.message).toContain("schema mismatch");
			}
		});

		it("passes through custom init options", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ ok: true }));
			const controller = new AbortController();

			await kragdFetch("/health", { signal: controller.signal });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/health",
				expect.objectContaining({ signal: controller.signal }),
			);
		});
	});

	describe("getHealth", () => {
		it("calls /health on the specified host:port with AbortSignal and returns HealthResponse", async () => {
			const data = { status: "healthy", version: "2.0.0" };
			mockFetch.mockResolvedValue(jsonResponse(data));

			const result = await getHealth("myhost", 9999);

			expect(mockFetch).toHaveBeenCalledWith(
				"http://myhost:9999/health",
				expect.objectContaining({
					method: "GET",
					headers: { "Content-Type": "application/json" },
					signal: expect.any(AbortSignal),
				}),
			);
			expect(result).toEqual(data);
		});

		it("throws KragdError on network failure", async () => {
			mockFetch.mockRejectedValue(new TypeError("Connection refused"));

			await expect(getHealth("badhost", 1234)).rejects.toThrow(KragdError);
			try {
				await getHealth("badhost", 1234);
			} catch (e) {
				const err = e as KragdError;
				expect(err.status).toBe(0);
				expect(err.message).toContain("Cannot reach kragd at badhost:1234");
			}
		});

		it("throws KragdError on non-OK response", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "error" }, 500, false));

			await expect(getHealth("localhost", 8742)).rejects.toThrow(KragdError);
		});

		it("throws KragdError on invalid JSON response", async () => {
			const res = {
				ok: true,
				status: 200,
				statusText: "OK",
				headers: new Headers(),
				json: () => Promise.reject(new SyntaxError("bad json")),
				text: () => Promise.resolve("not json"),
			} as unknown as Response;
			mockFetch.mockResolvedValue(res);

			await expect(getHealth("localhost", 8742)).rejects.toThrow(KragdError);
		});
	});

	describe("getStatus", () => {
		it("calls /status using module baseUrl", async () => {
			const data = { version: "1.0.0", uptime_seconds: 3600 };
			mockFetch.mockResolvedValue(jsonResponse(data));

			const result = await getStatus();

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/status",
				expect.objectContaining({ method: "GET" }),
			);
			expect(result).toEqual(data);
		});
	});

	describe("postQuery", () => {
		it("sends POST /query with request body and returns QueryResponse", async () => {
			const resData = {
				answer: "The answer is 42.",
				sources: [
					{
						chunk_id: "c1",
						file_path: "/a.py",
						score: 0.95,
						rank: 1,
						chunk_content: "code",
						file_type: "python",
					},
				],
			};
			mockFetch.mockResolvedValue(jsonResponse(resData));

			const result = await postQuery({ query: "What is the answer?", top_k: 5 });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/query",
				expect.objectContaining({
					method: "POST",
					body: JSON.stringify({ query: "What is the answer?", top_k: 5 }),
				}),
			);
			expect(result).toEqual(resData);
		});

		it("includes mode when provided", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ answer: "ok", sources: [] }));

			await postQuery({ query: "test", mode: "code" });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/query",
				expect.objectContaining({
					body: JSON.stringify({ query: "test", mode: "code" }),
				}),
			);
		});

		it("throws KragdError on server error", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "LLM not ready" }, 503, false));

			await expect(postQuery({ query: "test" })).rejects.toThrow(KragdError);
		});
	});

	describe("postRetrieve", () => {
		it("sends POST /retrieve with request body and returns RetrieveResponse", async () => {
			const resData = {
				sources: [
					{
						chunk_id: "c1",
						file_path: "/a.py",
						score: 0.9,
						rank: 1,
						chunk_content: "def foo(): pass",
						file_type: "python",
					},
				],
			};
			mockFetch.mockResolvedValue(jsonResponse(resData));

			const result = await postRetrieve({ query: "foo function" });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/retrieve",
				expect.objectContaining({
					method: "POST",
					body: JSON.stringify({ query: "foo function" }),
				}),
			);
			expect(result).toEqual(resData);
		});

		it("includes mode and top_k when provided", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ sources: [] }));

			await postRetrieve({ query: "test", mode: "docs", top_k: 10 });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/retrieve",
				expect.objectContaining({
					body: JSON.stringify({ query: "test", mode: "docs", top_k: 10 }),
				}),
			);
		});
	});

	describe("getModes", () => {
		it("calls GET /modes and returns ModeListResponse", async () => {
			const data = {
				modes: [
					{
						name: "default",
						description: "Default",
						collections: ["main"],
						llm_slot: "text",
						preset: "standard",
					},
				],
			};
			mockFetch.mockResolvedValue(jsonResponse(data));

			const result = await getModes();

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/modes",
				expect.objectContaining({ method: "GET" }),
			);
			expect(result).toEqual(data);
		});

		it("throws KragdError on failure", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "error" }, 500, false));
			await expect(getModes()).rejects.toThrow(KragdError);
		});
	});

	describe("getModeDetail", () => {
		it("calls GET /modes/{name} and returns ModeDetailResponse", async () => {
			const data = {
				name: "code",
				description: "Code mode",
				collections: { code: 500 },
				llm_slot: "code",
				preset: "code",
				top_k: 10,
				similarity_threshold: 0.3,
				critic_enabled: true,
				critic_threshold: 0.5,
			};
			mockFetch.mockResolvedValue(jsonResponse(data));

			const result = await getModeDetail("code");

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/modes/code",
				expect.objectContaining({ method: "GET" }),
			);
			expect(result).toEqual(data);
		});

		it("encodes special characters in mode name", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ name: "my mode" }));
			await getModeDetail("my mode");

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/modes/my%20mode",
				expect.objectContaining({ method: "GET" }),
			);
		});

		it("throws KragdError on 404", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "Mode not found" }, 404, false));
			await expect(getModeDetail("nonexistent")).rejects.toThrow(KragdError);
		});
	});

	describe("triggerIndex", () => {
		it("sends POST /index with request body and returns IndexResponse", async () => {
			const resData = {
				job_id: "job-001",
				status: "running",
				mode: "incremental",
				files_scanned: 0,
				files_processed: 0,
				files_skipped: 0,
				files_skipped_unchanged: 0,
				files_skipped_other: 0,
				files_errored: 0,
				chunks_created: 0,
				vectors_stored: 0,
				duration_seconds: 0,
				dry_run: false,
				errors: [],
				collections: {},
			};
			mockFetch.mockResolvedValue(jsonResponse(resData));

			const result = await triggerIndex({ mode: "incremental" });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/index",
				expect.objectContaining({
					method: "POST",
					body: JSON.stringify({ mode: "incremental" }),
				}),
			);
			expect(result).toEqual(resData);
		});

		it("sends full mode with options", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ job_id: "j" }));
			await triggerIndex({ mode: "full", dry_run: true });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/index",
				expect.objectContaining({
					body: JSON.stringify({ mode: "full", dry_run: true }),
				}),
			);
		});

		it("throws KragdError on conflict", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "Job already running" }, 409, false));
			await expect(triggerIndex({ mode: "full" })).rejects.toThrow(KragdError);
		});
	});

	describe("getIndexStatus", () => {
		it("calls GET /index/status and returns IndexResponse array", async () => {
			const data = [
				{
					job_id: "job-001",
					status: "completed",
					mode: "incremental",
					files_scanned: 100,
					files_processed: 95,
					files_skipped: 5,
					files_skipped_unchanged: 3,
					files_skipped_other: 2,
					files_errored: 0,
					chunks_created: 200,
					vectors_stored: 200,
					duration_seconds: 12.5,
					dry_run: false,
					errors: [],
					collections: { main: 200 },
				},
			];
			mockFetch.mockResolvedValue(jsonResponse(data));

			const result = await getIndexStatus();

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/index/status",
				expect.objectContaining({ method: "GET" }),
			);
			expect(result).toEqual(data);
			expect(result).toHaveLength(1);
		});

		it("returns empty array when no jobs", async () => {
			mockFetch.mockResolvedValue(jsonResponse([]));
			const result = await getIndexStatus();
			expect(result).toEqual([]);
		});
	});

	describe("postDebugQuery", () => {
		it("calls POST /debug/query and returns DebugQueryResponse", async () => {
			const resData = {
				answer: "debug answer",
				sources: [
					{
						chunk_id: "c1",
						file_path: "/a.py",
						score: 0.9,
						rank: 1,
						chunk_content: "x",
						file_type: "python",
					},
				],
				debug: {
					llm_used: "text",
					llm_model: "gpt-4",
					route: "code",
					auto_routed: true,
					route_reason: "matched code pattern",
					preset: "default",
					mode: "code",
					collections_searched: ["main"],
					retrieval_time_ms: 120,
					generation_time_ms: 800,
					embedding_models_used: ["all-MiniLM-L6-v2"],
					vector_spaces_searched: ["dense"],
					total_candidates_before_dedup: 50,
					total_candidates_after_dedup: 30,
					similarity_threshold: 0.7,
					per_space_result_counts: { dense: 30 },
					lexicon_terms_injected: 3,
					critic_scores: [0.8, 0.9, 0.7],
					chunks_pre_critic: 30,
					chunks_post_critic: 10,
				},
			};
			mockFetch.mockResolvedValue(jsonResponse(resData));

			const result = await postDebugQuery({ query: "test debug", top_k: 5 });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/debug/query",
				expect.objectContaining({
					method: "POST",
					body: JSON.stringify({ query: "test debug", top_k: 5 }),
				}),
			);
			expect(result).toEqual(resData);
			expect(result.debug.llm_used).toBe("text");
		});

		it("sends minimal request with only query", async () => {
			const resData = {
				answer: "a",
				sources: [],
				debug: {
					llm_used: "text",
					llm_model: "m",
					route: "r",
					auto_routed: false,
					preset: "default",
					retrieval_time_ms: 0,
					generation_time_ms: 0,
					embedding_models_used: [],
					vector_spaces_searched: [],
					total_candidates_before_dedup: 0,
					total_candidates_after_dedup: 0,
					similarity_threshold: 0,
					per_space_result_counts: {},
					lexicon_terms_injected: 0,
					critic_scores: [],
					chunks_pre_critic: 0,
					chunks_post_critic: 0,
				},
			};
			mockFetch.mockResolvedValue(jsonResponse(resData));

			await postDebugQuery({ query: "hello" });

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/debug/query",
				expect.objectContaining({
					body: JSON.stringify({ query: "hello" }),
				}),
			);
		});

		it("throws KragdError on server error", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "Internal error" }, 500, false));
			await expect(postDebugQuery({ query: "fail" })).rejects.toThrow(KragdError);
		});
	});

	describe("postDebugQdrant", () => {
		it("calls POST /debug/qdrant and returns QdrantSearchResponse", async () => {
			const resData = {
				results: [
					{
						chunk_id: "c1",
						score: 0.95,
						file_path: "/a.py",
						file_type: "python",
						chunk_content: "def foo():",
						chunk_index: 0,
						start_line: 1,
						end_line: 5,
					},
				],
				total_results: 1,
				vector_space: "dense",
			};
			mockFetch.mockResolvedValue(jsonResponse(resData));

			const result = await postDebugQdrant({
				query: "vector search",
				vector_space: "dense",
				top_k: 10,
			});

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/debug/qdrant",
				expect.objectContaining({
					method: "POST",
					body: JSON.stringify({ query: "vector search", vector_space: "dense", top_k: 10 }),
				}),
			);
			expect(result).toEqual(resData);
			expect(result.total_results).toBe(1);
		});

		it("sends request with filters", async () => {
			const resData = { results: [], total_results: 0 };
			mockFetch.mockResolvedValue(jsonResponse(resData));

			await postDebugQdrant({
				query: "filtered",
				filters: { file_type: "python", file_path_contains: "src/" },
				score_threshold: 0.5,
			});

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/debug/qdrant",
				expect.objectContaining({
					body: JSON.stringify({
						query: "filtered",
						filters: { file_type: "python", file_path_contains: "src/" },
						score_threshold: 0.5,
					}),
				}),
			);
		});

		it("throws KragdError on 422 validation error", async () => {
			mockFetch.mockResolvedValue(
				jsonResponse({ detail: [{ loc: ["body", "query"], msg: "required" }] }, 422, false),
			);
			await expect(postDebugQdrant({ query: "" })).rejects.toThrow(KragdError);
		});
	});

	describe("refreshLexicon", () => {
		it("calls POST /lexicon/refresh and returns LexiconRefreshResponse", async () => {
			const resData = { entries: 1234, status: "refreshed" };
			mockFetch.mockResolvedValue(jsonResponse(resData));

			const result = await refreshLexicon();

			expect(mockFetch).toHaveBeenCalledWith(
				"http://localhost:8742/lexicon/refresh",
				expect.objectContaining({ method: "POST" }),
			);
			expect(result).toEqual(resData);
			expect(result.entries).toBe(1234);
		});

		it("throws KragdError on server error", async () => {
			mockFetch.mockResolvedValue(jsonResponse({ detail: "Lexicon file not found" }, 500, false));
			await expect(refreshLexicon()).rejects.toThrow(KragdError);
		});
	});
});
