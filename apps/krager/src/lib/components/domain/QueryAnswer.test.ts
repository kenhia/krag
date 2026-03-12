import { render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import type { TranscriptEntry } from "$lib/types";
import QueryAnswer from "./QueryAnswer.svelte";

// Mock config store for query state
vi.mock("$lib/services/config-store", () => ({
	configStoreGet: vi.fn(),
	configStoreSet: vi.fn(),
	isConfigStoreReady: vi.fn(() => true),
}));

function makeEntry(overrides: Partial<TranscriptEntry> = {}): TranscriptEntry {
	return {
		id: "test-1",
		timestamp: new Date(),
		type: "query",
		request: { query: "test" },
		response: {
			answer: "This is the answer.",
			sources: [
				{
					file_path: "/docs/readme.md",
					score: 0.95,
					collection: "docs",
					rank: 1,
					chunk_content: "Some chunk text",
				},
				{
					file_path: "/docs/guide.md",
					score: 0.88,
					collection: "docs",
					rank: 2,
					chunk_content: "Another chunk",
				},
			],
		},
		durationMs: 1200,
		error: null,
		loading: false,
		...overrides,
	};
}

describe("QueryAnswer", () => {
	it("renders answer text", () => {
		render(QueryAnswer, { props: { entry: makeEntry() } });
		expect(screen.getByText("This is the answer.")).toBeInTheDocument();
	});

	it("renders folded source toggle with count", () => {
		render(QueryAnswer, { props: { entry: makeEntry() } });
		expect(screen.getByText(/2 sources/)).toBeInTheDocument();
		// Sources initially collapsed
		expect(screen.queryByText("/docs/readme.md")).not.toBeInTheDocument();
	});

	it("expands sources on toggle click", async () => {
		const { fireEvent } = await import("@testing-library/svelte");
		render(QueryAnswer, { props: { entry: makeEntry() } });
		const toggle = screen.getByText(/2 sources/);
		await fireEvent.click(toggle);
		expect(screen.getByText("/docs/readme.md")).toBeInTheDocument();
		expect(screen.getByText("0.95")).toBeInTheDocument();
		expect(screen.getByText("/docs/guide.md")).toBeInTheDocument();
	});

	it("does NOT render chunk_content", () => {
		render(QueryAnswer, { props: { entry: makeEntry() } });
		expect(screen.queryByText("Some chunk text")).not.toBeInTheDocument();
		expect(screen.queryByText("Another chunk")).not.toBeInTheDocument();
	});

	it("handles empty sources", () => {
		const entry = makeEntry({
			response: { answer: "No sources.", sources: [] },
		});
		render(QueryAnswer, { props: { entry } });
		expect(screen.getByText("No sources.")).toBeInTheDocument();
	});

	it("handles null response", () => {
		const entry = makeEntry({ response: null, loading: true });
		render(QueryAnswer, { props: { entry } });
		// Should not crash
		expect(screen.queryByText("This is the answer.")).not.toBeInTheDocument();
	});

	it("shows low-confidence warning when critic scores below cut_off", () => {
		const entry = makeEntry({
			response: {
				answer: "A flagged answer.",
				sources: [],
				debug: {
					critic_scores: [1, 2],
					chunks_pre_critic: 5,
					chunks_post_critic: 2,
					embedding_models_used: ["model-a"],
				},
			},
		});
		render(QueryAnswer, {
			props: { entry, criticEnabled: true, criticCutOff: 3 },
		});
		expect(screen.getByText(/low.confidence/i)).toBeInTheDocument();
	});

	it("does NOT show warning when critic scores above cut_off", () => {
		const entry = makeEntry({
			response: {
				answer: "A good answer.",
				sources: [],
				debug: {
					critic_scores: [4, 5],
					chunks_pre_critic: 5,
					chunks_post_critic: 5,
					embedding_models_used: ["model-a"],
				},
			},
		});
		render(QueryAnswer, {
			props: { entry, criticEnabled: true, criticCutOff: 3 },
		});
		expect(screen.queryByText(/low.confidence/i)).not.toBeInTheDocument();
	});

	it("does NOT show warning when critic is disabled", () => {
		const entry = makeEntry({
			response: {
				answer: "Answer.",
				sources: [],
				debug: {
					critic_scores: [1],
					chunks_pre_critic: 5,
					chunks_post_critic: 1,
					embedding_models_used: ["model-a"],
				},
			},
		});
		render(QueryAnswer, {
			props: { entry, criticEnabled: false, criticCutOff: 3 },
		});
		expect(screen.queryByText(/low.confidence/i)).not.toBeInTheDocument();
	});
});
