import { render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPanel from "./SettingsPanel.svelte";

// Mock config store
vi.mock("$lib/services/config-store", () => ({
	configStoreGet: vi.fn(),
	configStoreSet: vi.fn(),
	isConfigStoreReady: vi.fn(() => true),
}));

// Mock kragd-client
vi.mock("$lib/services/kragd-client", () => ({
	getHealth: vi.fn(),
	getStatus: vi.fn(),
	postQuery: vi.fn(),
	postRetrieve: vi.fn(),
	getModes: vi.fn(),
	getModeDetail: vi.fn(),
	triggerIndex: vi.fn(),
	getIndexStatus: vi.fn(),
	postDebugQuery: vi.fn(),
	postDebugQdrant: vi.fn(),
	refreshLexicon: vi.fn(),
}));

// Mock streaming
vi.mock("$lib/services/streaming", () => ({
	streamQuerySSE: vi.fn(),
}));

describe("SettingsPanel", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders 4 section headings", () => {
		render(SettingsPanel);
		expect(screen.getByText("Connection")).toBeInTheDocument();
		expect(screen.getByText("Query")).toBeInTheDocument();
		// "Critic" appears as both heading and toggle label
		expect(screen.getAllByText("Critic").length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText("Display")).toBeInTheDocument();
	});

	it("renders connection fields", () => {
		render(SettingsPanel);
		expect(screen.getByLabelText("Host")).toBeInTheDocument();
		expect(screen.getByLabelText("Port")).toBeInTheDocument();
	});

	it("renders query controls", () => {
		render(SettingsPanel);
		// The Slider and Select controls should have labels
		expect(screen.getByText("Top K")).toBeInTheDocument();
		expect(screen.getByText("Preset")).toBeInTheDocument();
	});

	it("renders critic section with toggle", () => {
		render(SettingsPanel);
		// Both the section heading and toggle label contain "Critic"
		const critics = screen.getAllByText("Critic");
		expect(critics.length).toBeGreaterThanOrEqual(2);
	});

	it("renders display controls", () => {
		render(SettingsPanel);
		expect(screen.getByText("Opacity")).toBeInTheDocument();
	});
});
