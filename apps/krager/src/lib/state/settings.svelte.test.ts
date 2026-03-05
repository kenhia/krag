import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock config store
vi.mock("$lib/services/config-store", () => ({
	configStoreGet: vi.fn(),
	configStoreSet: vi.fn(),
	isConfigStoreReady: vi.fn(() => true),
}));

import { configStoreGet, configStoreSet } from "$lib/services/config-store";

import {
	initSettingsFromConfig,
	resetSettings,
	setOpacity,
	setTheme,
	settingsState,
} from "./settings.svelte";

describe("settings.svelte", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		resetSettings();
	});

	it("has correct default values", () => {
		expect(settingsState.opacity).toBe(1.0);
		expect(settingsState.theme).toBeNull();
	});

	describe("setOpacity", () => {
		it("sets opacity to a valid value", () => {
			setOpacity(0.7);
			expect(settingsState.opacity).toBe(0.7);
		});

		it("clamps opacity below 0.3 to 0.3", () => {
			setOpacity(0.1);
			expect(settingsState.opacity).toBe(0.3);
		});

		it("clamps opacity above 1.0 to 1.0", () => {
			setOpacity(1.5);
			expect(settingsState.opacity).toBe(1.0);
		});

		it("persists opacity to config store", () => {
			setOpacity(0.8);
			expect(configStoreSet).toHaveBeenCalledWith(
				"display",
				expect.objectContaining({ opacity: 0.8 }),
			);
		});
	});

	describe("setTheme", () => {
		it("sets theme to dark", () => {
			setTheme("dark");
			expect(settingsState.theme).toBe("dark");
		});

		it("sets theme to light", () => {
			setTheme("light");
			expect(settingsState.theme).toBe("light");
		});

		it("sets theme to null (follow OS)", () => {
			setTheme("dark");
			setTheme(null);
			expect(settingsState.theme).toBeNull();
		});

		it("persists theme to config store", () => {
			setTheme("light");
			expect(configStoreSet).toHaveBeenCalledWith(
				"display",
				expect.objectContaining({ theme: "light" }),
			);
		});
	});

	describe("initSettingsFromConfig", () => {
		it("loads saved display config", async () => {
			(configStoreGet as ReturnType<typeof vi.fn>).mockResolvedValue({
				opacity: 0.6,
				theme: "dark",
			});

			await initSettingsFromConfig();

			expect(settingsState.opacity).toBe(0.6);
			expect(settingsState.theme).toBe("dark");
		});

		it("keeps defaults when no config saved", async () => {
			(configStoreGet as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

			await initSettingsFromConfig();

			expect(settingsState.opacity).toBe(1.0);
			expect(settingsState.theme).toBeNull();
		});

		it("clamps saved opacity within range", async () => {
			(configStoreGet as ReturnType<typeof vi.fn>).mockResolvedValue({
				opacity: 0.1,
				theme: null,
			});

			await initSettingsFromConfig();

			expect(settingsState.opacity).toBe(0.3);
		});
	});

	describe("resetSettings", () => {
		it("resets to defaults", () => {
			setOpacity(0.5);
			setTheme("light");

			resetSettings();

			expect(settingsState.opacity).toBe(1.0);
			expect(settingsState.theme).toBeNull();
		});
	});
});
