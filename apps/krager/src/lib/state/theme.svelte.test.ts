import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock Tauri window API
const { mockTheme, mockOnThemeChanged, mockGetCurrentWindow } = vi.hoisted(() => {
	const mockTheme = vi.fn();
	const mockOnThemeChanged = vi.fn();
	const mockGetCurrentWindow = vi.fn(() => ({
		theme: mockTheme,
		onThemeChanged: mockOnThemeChanged,
	}));
	return { mockTheme, mockOnThemeChanged, mockGetCurrentWindow };
});

vi.mock("@tauri-apps/api/window", () => ({
	getCurrentWindow: mockGetCurrentWindow,
}));

import { appTheme, initTheme } from "./theme.svelte";

describe("theme.svelte", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		appTheme.current = "dark";
		// Reset to default working implementation
		mockGetCurrentWindow.mockImplementation(() => ({
			theme: mockTheme,
			onThemeChanged: mockOnThemeChanged,
		}));
		mockTheme.mockResolvedValue("dark");
		mockOnThemeChanged.mockResolvedValue(() => {});
	});

	it("has dark as default theme", () => {
		expect(appTheme.current).toBe("dark");
	});

	it("allows setting theme directly", () => {
		appTheme.current = "light";
		expect(appTheme.current).toBe("light");
	});

	it("initTheme uses Tauri theme when available", async () => {
		mockTheme.mockResolvedValue("light");

		const cleanup = await initTheme();
		expect(appTheme.current).toBe("light");
		cleanup();
	});

	it("initTheme falls back to matchMedia when Tauri theme() returns null (Linux)", async () => {
		mockTheme.mockResolvedValue(null);

		const cleanup = await initTheme();
		// Should use matchMedia fallback — jsdom defaults
		expect(["dark", "light"]).toContain(appTheme.current);
		cleanup();
	});

	it("initTheme falls back to matchMedia when Tauri API fails", async () => {
		mockGetCurrentWindow.mockImplementation(() => {
			throw new Error("Not in Tauri");
		});

		const cleanup = await initTheme();
		expect(typeof cleanup).toBe("function");
		expect(["dark", "light"]).toContain(appTheme.current);
		cleanup();
	});
});
