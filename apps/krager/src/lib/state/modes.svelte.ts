/**
 * Modes State Module
 *
 * Reactive modes state using Svelte 5 $state rune.
 * Tracks available retrieval modes and the currently selected mode.
 */

import type { ModeInfo } from "$lib/types";

export interface ModesState {
	available: ModeInfo[];
	selected: string | null;
	loading: boolean;
	error: string | null;
}

/** Reactive modes state. */
export const modesState = $state<ModesState>({
	available: [],
	selected: null,
	loading: false,
	error: null,
});

/** Set the selected mode by name. */
export function setSelected(name: string | null): void {
	modesState.selected = name;
}

/** Clear all modes and reset selection. */
export function clearModes(): void {
	modesState.available.length = 0;
	modesState.selected = null;
	modesState.loading = false;
	modesState.error = null;
}

/** Set available modes from API response. */
export function setModes(modes: ModeInfo[]): void {
	modesState.available.length = 0;
	modesState.available.push(...modes);
	modesState.loading = false;
	modesState.error = null;
}

/** Set loading state. */
export function setModesLoading(): void {
	modesState.loading = true;
	modesState.error = null;
}

/** Set error state. */
export function setModesError(msg: string): void {
	modesState.loading = false;
	modesState.error = msg;
}
