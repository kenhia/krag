import { render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ServiceStatus } from "$lib/types";
import SystemStatus from "./SystemStatus.svelte";

// Mock notifications
vi.mock("$lib/state/notifications.svelte", () => ({
	addToast: vi.fn(),
}));

// Mock kragd-client
const mockGetStatus = vi.fn();
const mockRefreshLexicon = vi.fn();

vi.mock("$lib/services/kragd-client", () => ({
	getStatus: (...args: unknown[]) => mockGetStatus(...args),
	refreshLexicon: (...args: unknown[]) => mockRefreshLexicon(...args),
}));

function makeStatus(overrides: Partial<ServiceStatus> = {}): ServiceStatus {
	return {
		version: "1.0.0",
		uptime_seconds: 3600,
		llm: {
			text: {
				loaded: true,
				model: "llama3",
				primary: true,
			},
		},
		embedding_models: ["nomic-embed-text"],
		vector_store: { collection: "default", total_vectors: 100, named_spaces: ["dense"] },
		collections: {
			docs: { collection_name: "docs", vectors_count: 100, status: "green" },
		},
		modes: [
			{
				name: "default",
				description: "Default mode",
				collections: ["docs"],
				llm_slot: "text",
				preset: "balanced",
			},
		],
		lexicon_loaded: true,
		lexicon_entry_count: 500,
		vram: null,
		...overrides,
	};
}

describe("SystemStatus", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("displays a single embedding model", async () => {
		mockGetStatus.mockResolvedValue(makeStatus({ embedding_models: ["model-a"] }));
		render(SystemStatus);
		await waitFor(() => {
			expect(screen.getByText("model-a")).toBeInTheDocument();
		});
	});

	it("displays multiple embedding models", async () => {
		mockGetStatus.mockResolvedValue(
			makeStatus({ embedding_models: ["model-a", "model-b", "model-c"] }),
		);
		render(SystemStatus);
		await waitFor(() => {
			expect(screen.getByText("model-a")).toBeInTheDocument();
			expect(screen.getByText("model-b")).toBeInTheDocument();
			expect(screen.getByText("model-c")).toBeInTheDocument();
		});
	});

	it("handles empty embedding models list", async () => {
		mockGetStatus.mockResolvedValue(makeStatus({ embedding_models: [] }));
		render(SystemStatus);
		await waitFor(() => {
			expect(screen.getByText("No embedding models loaded")).toBeInTheDocument();
		});
	});
});
