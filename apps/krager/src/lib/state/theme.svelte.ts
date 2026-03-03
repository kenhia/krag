/**
 * Theme State Module
 *
 * Reactive theme state using Svelte 5 $state rune.
 * Initialized from Tauri getCurrentWindow().theme() with
 * window.matchMedia fallback for Linux (where theme() returns null).
 */

import type { Theme } from "$lib/types";

/** Reactive theme state. */
export const appTheme = $state<{ current: Theme }>({
	current: "dark",
});

/**
 * Initialize theme from Tauri API or system preference.
 *
 * 1. Try getCurrentWindow().theme() (Tauri native)
 * 2. Fall back to window.matchMedia('(prefers-color-scheme: dark)')
 * 3. Subscribe to live theme changes via onThemeChanged() + matchMedia listener
 *
 * Returns cleanup function to unsubscribe listeners.
 */
export async function initTheme(): Promise<() => void> {
	const cleanups: Array<() => void> = [];

	try {
		// Try Tauri API first
		const { getCurrentWindow } = await import("@tauri-apps/api/window");
		const win = getCurrentWindow();
		const tauriTheme = await win.theme();

		if (tauriTheme) {
			appTheme.current = tauriTheme as Theme;
		} else {
			// Linux fallback — Tauri theme() returns null
			appTheme.current = getSystemTheme();
		}

		// Subscribe to Tauri theme changes
		const unlisten = await win.onThemeChanged((event) => {
			appTheme.current = event.payload as Theme;
		});
		cleanups.push(unlisten);
	} catch {
		// Tauri API not available (e.g. in tests) — use matchMedia
		appTheme.current = getSystemTheme();
	}

	// Also listen to matchMedia as a fallback (covers Linux GTK theme changes)
	if (typeof window !== "undefined" && window.matchMedia) {
		const mq = window.matchMedia("(prefers-color-scheme: dark)");
		const handler = (e: MediaQueryListEvent) => {
			appTheme.current = e.matches ? "dark" : "light";
		};
		mq.addEventListener("change", handler);
		cleanups.push(() => mq.removeEventListener("change", handler));
	}

	return () => {
		for (const cleanup of cleanups) cleanup();
	};
}

/** Get system theme preference via matchMedia. */
function getSystemTheme(): Theme {
	if (typeof window !== "undefined" && window.matchMedia) {
		return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
	}
	return "dark";
}
