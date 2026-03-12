/**
 * Settings State Module
 *
 * Reactive display settings state using Svelte 5 $state rune.
 * Manages: opacity (0.3–1.0), theme (light/dark/null).
 * Loads from and persists to config store.
 */

import { configStoreGet, configStoreSet, isConfigStoreReady } from "$lib/services/config-store";
import type { DisplayConfig } from "$lib/types";

export interface SettingsState {
	opacity: number;
	theme: "light" | "dark" | null;
}

/** Reactive settings state. */
export const settingsState = $state<SettingsState>({
	opacity: 1.0,
	theme: null,
});

/** Persist current display config to store. */
function persistDisplay(): void {
	if (!isConfigStoreReady()) return;
	configStoreSet("display", {
		opacity: settingsState.opacity,
		theme: settingsState.theme,
	});
}

/** Set opacity with range clamping (0.3–1.0). */
export function setOpacity(value: number): void {
	settingsState.opacity = Math.max(0.3, Math.min(1.0, value));
	persistDisplay();
}

/** Set theme preference. null = follow OS. */
export function setTheme(value: "light" | "dark" | null): void {
	settingsState.theme = value;
	persistDisplay();
}

/** Load display config from config store. */
export async function initSettingsFromConfig(): Promise<void> {
	if (!isConfigStoreReady()) return;
	const saved = await configStoreGet<DisplayConfig>("display");
	if (!saved) return;

	if (saved.opacity !== undefined && saved.opacity !== null) {
		settingsState.opacity = Math.max(0.3, Math.min(1.0, saved.opacity));
	}
	if (saved.theme !== undefined) {
		settingsState.theme = saved.theme;
	}
}

/** Reset settings to defaults. */
export function resetSettings(): void {
	settingsState.opacity = 1.0;
	settingsState.theme = null;
}
