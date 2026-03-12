import { render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { connection } from "$lib/state/connection.svelte";
import QueryPanel from "./QueryPanel.svelte";

// Mock all external dependencies
vi.mock("$lib/services/kragd-client", () => ({
	postQuery: vi.fn(),
	postRetrieve: vi.fn(),
	getBaseUrl: vi.fn(() => "http://localhost:8742"),
}));

vi.mock("$lib/services/config-store", () => ({
	configStoreGet: vi.fn(),
	configStoreSet: vi.fn(),
	isConfigStoreReady: vi.fn(() => true),
}));

vi.mock("$lib/state/notifications.svelte", () => ({
	addToast: vi.fn(),
}));

vi.mock("$lib/services/streaming", () => ({
	streamQuerySSE: vi.fn(),
}));

describe("QueryPanel", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Simulate connected state so controls render enabled
		connection.status = "connected";
		connection.version = "1.0.0";
	});

	it("renders query textarea", () => {
		render(QueryPanel, { props: { selectedMode: null } });
		expect(screen.getByPlaceholderText(/ask/i)).toBeInTheDocument();
	});

	it("renders send button", () => {
		render(QueryPanel, { props: { selectedMode: null } });
		expect(screen.getByText("Send")).toBeInTheDocument();
	});

	it("renders top-k slider", () => {
		render(QueryPanel, { props: { selectedMode: null } });
		expect(screen.getByText("Top K")).toBeInTheDocument();
	});

	it("renders preset dropdown", () => {
		render(QueryPanel, { props: { selectedMode: null } });
		expect(screen.getByText("Preset")).toBeInTheDocument();
	});

	it("renders debug toggle", () => {
		render(QueryPanel, { props: { selectedMode: null } });
		expect(screen.getByText("Debug")).toBeInTheDocument();
	});

	it("renders sources toggle", () => {
		render(QueryPanel, { props: { selectedMode: null } });
		expect(screen.getByText("Sources")).toBeInTheDocument();
	});

	it("renders retrieve-only toggle", () => {
		render(QueryPanel, { props: { selectedMode: null } });
		expect(screen.getByText(/retrieve/i)).toBeInTheDocument();
	});
});
