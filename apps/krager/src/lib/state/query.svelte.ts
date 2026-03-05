/**
 * Query State Module
 *
 * Reactive query parameter state using Svelte 5 $state rune.
 * Manages: top_k, preset, include_debug, show_sources, retrieve_only.
 * Loads from and persists to config store.
 */

import { configStoreGet, configStoreSet, isConfigStoreReady } from "$lib/services/config-store";
import type { CriticConfig, PresetName, QueryConfig } from "$lib/types";
import { VALID_PRESETS } from "$lib/types";

export interface QueryState {
	top_k: number | null;
	preset: PresetName | null;
	include_debug: boolean;
	show_sources: boolean;
	retrieve_only: boolean;
	critic_enabled: boolean;
	critic_cut_off: number;
}

/** Reactive query state. */
export const queryState = $state<QueryState>({
	top_k: null,
	preset: null,
	include_debug: false,
	show_sources: true,
	retrieve_only: false,
	critic_enabled: false,
	critic_cut_off: 3,
});

/** Persist current query config to store. */
function persistQuery(): void {
	if (!isConfigStoreReady()) return;
	configStoreSet("query", {
		top_k: queryState.top_k,
		preset: queryState.preset,
		include_debug: queryState.include_debug,
		show_sources: queryState.show_sources,
	});
}

/** Set top_k with range validation (1–100, or null for server default). */
export function setTopK(value: number | null): void {
	if (value === null) {
		queryState.top_k = null;
	} else {
		queryState.top_k = Math.max(1, Math.min(100, Math.round(value)));
	}
	persistQuery();
}

/** Set preset with validation. Invalid names reset to null. */
export function setPreset(value: PresetName | null): void {
	if (value === null) {
		queryState.preset = null;
	} else if ((VALID_PRESETS as readonly string[]).includes(value)) {
		queryState.preset = value;
	} else {
		queryState.preset = null;
	}
	persistQuery();
}

/** Set include_debug flag. */
export function setIncludeDebug(value: boolean): void {
	queryState.include_debug = value;
	persistQuery();
}

/** Set show_sources flag. */
export function setShowSources(value: boolean): void {
	queryState.show_sources = value;
	persistQuery();
}

/** Set retrieve_only flag (not persisted — session-only). */
export function setRetrieveOnly(value: boolean): void {
	queryState.retrieve_only = value;
}

/** Persist current critic config to store. */
function persistCritic(): void {
	if (!isConfigStoreReady()) return;
	configStoreSet("critic", {
		enabled: queryState.critic_enabled,
		cut_off: queryState.critic_cut_off,
	});
}

/** Set critic_enabled. Auto-enables include_debug when critic is turned on. */
export function setCriticEnabled(value: boolean): void {
	queryState.critic_enabled = value;
	if (value) {
		queryState.include_debug = true;
		persistQuery();
	}
	persistCritic();
}

/** Set critic_cut_off with range validation (0–5 integer). */
export function setCriticCutOff(value: number): void {
	queryState.critic_cut_off = Math.max(0, Math.min(5, Math.round(value)));
	persistCritic();
}

/** Load query config from config store. */
export async function initQueryFromConfig(): Promise<void> {
	if (!isConfigStoreReady()) return;
	const saved = await configStoreGet<QueryConfig>("query");
	if (saved) {
		if (saved.top_k !== undefined && saved.top_k !== null) {
			queryState.top_k = Math.max(1, Math.min(100, Math.round(saved.top_k)));
		}
		if (saved.preset !== undefined && saved.preset !== null) {
			if ((VALID_PRESETS as readonly string[]).includes(saved.preset)) {
				queryState.preset = saved.preset as PresetName;
			}
		}
		if (saved.include_debug !== undefined) {
			queryState.include_debug = saved.include_debug;
		}
		if (saved.show_sources !== undefined) {
			queryState.show_sources = saved.show_sources;
		}
	}

	const criticSaved = await configStoreGet<CriticConfig>("critic");
	if (criticSaved) {
		if (criticSaved.enabled !== undefined) {
			queryState.critic_enabled = criticSaved.enabled;
		}
		if (criticSaved.cut_off !== undefined && criticSaved.cut_off !== null) {
			queryState.critic_cut_off = Math.max(0, Math.min(5, Math.round(criticSaved.cut_off)));
		}
	}
}
