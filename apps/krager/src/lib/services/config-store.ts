/**
 * ConfigStoreService — Tauri Store wrapper for persistent configuration.
 *
 * Wraps @tauri-apps/plugin-store with:
 * - autoSave debounce (300ms)
 * - defaults hydration on first load
 * - try/catch with createNew fallback on corruption
 * - module-level singleton pattern (matches existing state modules)
 *
 * File: apps/krager/src/lib/services/config-store.ts
 */

import { load, type Store } from "@tauri-apps/plugin-store";
import type { UserConfig } from "$lib/types";
import { USER_CONFIG_DEFAULTS } from "$lib/types";

const STORE_FILENAME = "settings.json";
const AUTO_SAVE_MS = 300;

let store: Store | null = null;
let ready = false;

/**
 * Initialize the config store. Call once at app startup.
 * Falls back to creating a new store on corruption.
 */
export async function initConfigStore(): Promise<void> {
	if (ready && store) return; // Already initialized

	try {
		store = await load(STORE_FILENAME, {
			autoSave: AUTO_SAVE_MS,
			defaults: USER_CONFIG_DEFAULTS as unknown as Record<string, unknown>,
		});
	} catch (err) {
		console.warn("[config-store] Store corrupted, creating new:", err);
		store = await load(STORE_FILENAME, {
			autoSave: AUTO_SAVE_MS,
			defaults: USER_CONFIG_DEFAULTS as unknown as Record<string, unknown>,
			createNew: true,
		});
	}
	ready = true;
}

/** Whether the config store has been initialized. */
export function isConfigStoreReady(): boolean {
	return ready;
}

/**
 * Get a config value by key.
 * @example configStoreGet<ConnectionConfig>('connection')
 */
export async function configStoreGet<T>(key: string): Promise<T | undefined> {
	if (!store) {
		console.warn("[config-store] get() called before init, returning undefined");
		return undefined;
	}
	return store.get<T>(key);
}

/**
 * Set a config value by key. Persisted via autoSave debounce.
 * @example configStoreSet('connection', { host: 'karch9', port: 9999 })
 */
export async function configStoreSet(key: string, value: unknown): Promise<void> {
	if (!store) {
		console.warn("[config-store] set() called before init, ignoring");
		return;
	}
	await store.set(key, value);
}

/**
 * Get the full config object by reading all entries.
 * Falls back to defaults for missing keys.
 */
export async function configStoreGetAll(): Promise<UserConfig> {
	if (!store) {
		console.warn("[config-store] getAll() called before init, returning defaults");
		return { ...USER_CONFIG_DEFAULTS };
	}

	const entries = await store.entries();
	const map = Object.fromEntries(entries);

	return {
		connection: (map.connection as UserConfig["connection"]) ?? USER_CONFIG_DEFAULTS.connection,
		query: (map.query as UserConfig["query"]) ?? USER_CONFIG_DEFAULTS.query,
		critic: (map.critic as UserConfig["critic"]) ?? USER_CONFIG_DEFAULTS.critic,
		display: (map.display as UserConfig["display"]) ?? USER_CONFIG_DEFAULTS.display,
	};
}

/**
 * Release store resources. Call on app shutdown.
 */
export async function destroyConfigStore(): Promise<void> {
	if (store) {
		await store.save();
		await store.close();
		store = null;
	}
	ready = false;
}
