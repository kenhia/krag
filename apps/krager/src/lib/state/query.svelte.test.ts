import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock config store
vi.mock("$lib/services/config-store", () => ({
	configStoreGet: vi.fn(),
	configStoreSet: vi.fn(),
	isConfigStoreReady: vi.fn(() => true),
}));

import { configStoreGet, configStoreSet } from "$lib/services/config-store";

// Import after mock
import {
	initQueryFromConfig,
	queryState,
	setCriticCutOff,
	setCriticEnabled,
	setIncludeDebug,
	setPreset,
	setRetrieveOnly,
	setShowSources,
	setTopK,
} from "./query.svelte";

describe("query.svelte", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Reset to defaults
		setTopK(null);
		setPreset(null);
		setIncludeDebug(false);
		setShowSources(true);
		setRetrieveOnly(false);
	});

	it("has correct default values", () => {
		expect(queryState.top_k).toBeNull();
		expect(queryState.preset).toBeNull();
		expect(queryState.include_debug).toBe(false);
		expect(queryState.show_sources).toBe(true);
		expect(queryState.retrieve_only).toBe(false);
	});

	describe("setTopK", () => {
		it("sets top_k to a valid value", () => {
			setTopK(5);
			expect(queryState.top_k).toBe(5);
		});

		it("sets top_k to null (server default)", () => {
			setTopK(5);
			setTopK(null);
			expect(queryState.top_k).toBeNull();
		});

		it("clamps top_k below 1 to 1", () => {
			setTopK(0);
			expect(queryState.top_k).toBe(1);
		});

		it("clamps top_k above 100 to 100", () => {
			setTopK(200);
			expect(queryState.top_k).toBe(100);
		});

		it("persists top_k to config store", () => {
			setTopK(10);
			expect(configStoreSet).toHaveBeenCalledWith("query", expect.objectContaining({ top_k: 10 }));
		});
	});

	describe("setPreset", () => {
		it("sets a valid preset", () => {
			setPreset("strict");
			expect(queryState.preset).toBe("strict");
		});

		it("sets preset to null (server default)", () => {
			setPreset("strict");
			setPreset(null);
			expect(queryState.preset).toBeNull();
		});

		it("rejects invalid preset names", () => {
			setPreset("invalid" as any);
			expect(queryState.preset).toBeNull();
		});

		it("persists preset to config store", () => {
			setPreset("code");
			expect(configStoreSet).toHaveBeenCalledWith(
				"query",
				expect.objectContaining({ preset: "code" }),
			);
		});
	});

	describe("setIncludeDebug", () => {
		it("toggles include_debug", () => {
			setIncludeDebug(true);
			expect(queryState.include_debug).toBe(true);
			setIncludeDebug(false);
			expect(queryState.include_debug).toBe(false);
		});

		it("persists include_debug to config store", () => {
			setIncludeDebug(true);
			expect(configStoreSet).toHaveBeenCalledWith(
				"query",
				expect.objectContaining({ include_debug: true }),
			);
		});
	});

	describe("setShowSources", () => {
		it("toggles show_sources", () => {
			setShowSources(false);
			expect(queryState.show_sources).toBe(false);
			setShowSources(true);
			expect(queryState.show_sources).toBe(true);
		});

		it("persists show_sources to config store", () => {
			setShowSources(false);
			expect(configStoreSet).toHaveBeenCalledWith(
				"query",
				expect.objectContaining({ show_sources: false }),
			);
		});
	});

	describe("setRetrieveOnly", () => {
		it("toggles retrieve_only", () => {
			setRetrieveOnly(true);
			expect(queryState.retrieve_only).toBe(true);
		});
	});

	describe("initQueryFromConfig", () => {
		it("loads saved query config", async () => {
			(configStoreGet as ReturnType<typeof vi.fn>).mockResolvedValue({
				top_k: 10,
				preset: "strict",
				include_debug: true,
				show_sources: false,
			});

			await initQueryFromConfig();

			expect(queryState.top_k).toBe(10);
			expect(queryState.preset).toBe("strict");
			expect(queryState.include_debug).toBe(true);
			expect(queryState.show_sources).toBe(false);
		});

		it("keeps defaults when no config saved", async () => {
			(configStoreGet as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

			await initQueryFromConfig();

			expect(queryState.top_k).toBeNull();
			expect(queryState.preset).toBeNull();
			expect(queryState.include_debug).toBe(false);
			expect(queryState.show_sources).toBe(true);
		});
	});

	describe("critic state", () => {
		beforeEach(() => {
			setCriticEnabled(false);
			setCriticCutOff(0.5);
			setIncludeDebug(false);
			vi.clearAllMocks();
		});

		it("has correct critic defaults", () => {
			expect(queryState.critic_enabled).toBe(false);
			expect(queryState.critic_cut_off).toBe(0.5);
		});

		it("setCriticEnabled toggles critic", () => {
			setCriticEnabled(true);
			expect(queryState.critic_enabled).toBe(true);
		});

		it("auto-enables include_debug when critic enabled", () => {
			expect(queryState.include_debug).toBe(false);
			setCriticEnabled(true);
			expect(queryState.include_debug).toBe(true);
		});

		it("does not disable include_debug when critic disabled", () => {
			setIncludeDebug(true);
			vi.clearAllMocks();
			setCriticEnabled(false);
			// include_debug can stay true - user may have enabled it independently
			expect(queryState.include_debug).toBe(true);
		});

		it("setCriticCutOff validates range 0.0–1.0", () => {
			setCriticCutOff(0.7);
			expect(queryState.critic_cut_off).toBe(0.7);
		});

		it("clamps cut_off below 0 to 0", () => {
			setCriticCutOff(-0.1);
			expect(queryState.critic_cut_off).toBe(0);
		});

		it("clamps cut_off above 1 to 1", () => {
			setCriticCutOff(1.5);
			expect(queryState.critic_cut_off).toBe(1);
		});

		it("persists critic config to config store", () => {
			setCriticEnabled(true);
			expect(configStoreSet).toHaveBeenCalledWith(
				"critic",
				expect.objectContaining({ enabled: true, cut_off: 0.5 }),
			);
		});
	});
});
