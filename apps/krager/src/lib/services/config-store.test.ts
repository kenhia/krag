import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { UserConfig } from "$lib/types";
import { USER_CONFIG_DEFAULTS } from "$lib/types";

// ─── Mock Tauri Store ────────────────────────────────────────────────────────

const mockStore = {
	get: vi.fn(),
	set: vi.fn(),
	save: vi.fn(),
	close: vi.fn(),
	entries: vi.fn(),
	onChange: vi.fn(() => Promise.resolve(vi.fn())),
};

vi.mock("@tauri-apps/plugin-store", () => ({
	load: vi.fn(() => Promise.resolve(mockStore)),
}));

// ─── Import after mock ───────────────────────────────────────────────────────

let configStore: typeof import("./config-store");

beforeEach(async () => {
	vi.clearAllMocks();
	// Reset module state between tests
	vi.resetModules();
	configStore = await import("./config-store");
});

afterEach(async () => {
	try {
		await configStore.destroyConfigStore();
	} catch {
		// ignore if not initialized
	}
});

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("ConfigStoreService", () => {
	describe("init", () => {
		it("should load the store with autoSave and defaults", async () => {
			const { load } = await import("@tauri-apps/plugin-store");

			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));

			await configStore.initConfigStore();

			expect(load).toHaveBeenCalledWith("settings.json", {
				autoSave: 300,
				defaults: USER_CONFIG_DEFAULTS,
			});
		});

		it("should set ready to true after successful init", async () => {
			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));

			expect(configStore.isConfigStoreReady()).toBe(false);
			await configStore.initConfigStore();
			expect(configStore.isConfigStoreReady()).toBe(true);
		});

		it("should fallback with createNew:true on corruption", async () => {
			const { load } = await import("@tauri-apps/plugin-store");

			// First call fails (corruption), second succeeds
			(load as ReturnType<typeof vi.fn>)
				.mockRejectedValueOnce(new Error("corrupt store"))
				.mockResolvedValueOnce(mockStore);

			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));

			await configStore.initConfigStore();

			expect(load).toHaveBeenCalledTimes(2);
			expect(load).toHaveBeenLastCalledWith("settings.json", {
				autoSave: 300,
				defaults: USER_CONFIG_DEFAULTS,
				createNew: true,
			});
			expect(configStore.isConfigStoreReady()).toBe(true);
		});
	});

	describe("get", () => {
		it("should return a config value by dot-path key", async () => {
			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));
			await configStore.initConfigStore();

			mockStore.get.mockResolvedValue({ host: "karch9", port: 9999 });

			const connection = await configStore.configStoreGet<{
				host: string;
				port: number;
			}>("connection");
			expect(connection).toEqual({ host: "karch9", port: 9999 });
			expect(mockStore.get).toHaveBeenCalledWith("connection");
		});

		it("should return undefined for missing keys", async () => {
			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));
			await configStore.initConfigStore();

			mockStore.get.mockResolvedValue(undefined);

			const result = await configStore.configStoreGet("nonexistent");
			expect(result).toBeUndefined();
		});
	});

	describe("set", () => {
		it("should set a config value by key", async () => {
			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));
			await configStore.initConfigStore();

			await configStore.configStoreSet("connection", {
				host: "karch9",
				port: 9999,
			});
			expect(mockStore.set).toHaveBeenCalledWith("connection", {
				host: "karch9",
				port: 9999,
			});
		});
	});

	describe("getAll", () => {
		it("should return the full config object", async () => {
			const customConfig: UserConfig = {
				...USER_CONFIG_DEFAULTS,
				connection: { host: "myhost", port: 1234 },
			};
			mockStore.entries.mockResolvedValue(Object.entries(customConfig));

			await configStore.initConfigStore();

			const all = await configStore.configStoreGetAll();
			expect(all).toEqual(customConfig);
		});

		it("should fallback to defaults for missing keys", async () => {
			// Store only has connection, missing other keys
			mockStore.entries.mockResolvedValue([["connection", { host: "partial", port: 5555 }]]);

			await configStore.initConfigStore();

			const all = await configStore.configStoreGetAll();
			expect(all.connection).toEqual({ host: "partial", port: 5555 });
			expect(all.query).toEqual(USER_CONFIG_DEFAULTS.query);
			expect(all.critic).toEqual(USER_CONFIG_DEFAULTS.critic);
			expect(all.display).toEqual(USER_CONFIG_DEFAULTS.display);
		});
	});

	describe("destroy", () => {
		it("should close the store and reset ready state", async () => {
			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));

			await configStore.initConfigStore();
			expect(configStore.isConfigStoreReady()).toBe(true);

			await configStore.destroyConfigStore();
			expect(mockStore.save).toHaveBeenCalled();
			expect(mockStore.close).toHaveBeenCalled();
			expect(configStore.isConfigStoreReady()).toBe(false);
		});
	});

	describe("error handling", () => {
		it("should not throw on set when store not initialized", async () => {
			// Should log warning but not throw
			await expect(
				configStore.configStoreSet("connection", { host: "x", port: 1 }),
			).resolves.not.toThrow();
		});

		it("should return defaults from getAll when store not initialized", async () => {
			const all = await configStore.configStoreGetAll();
			expect(all).toEqual(USER_CONFIG_DEFAULTS);
		});
	});

	describe("edge cases", () => {
		it("should handle rapid sequential sets without error", async () => {
			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));
			await configStore.initConfigStore();

			// Simulate rapid toggles — all should succeed (autoSave debounces disk writes)
			const promises = [];
			for (let i = 0; i < 20; i++) {
				promises.push(configStore.configStoreSet("query", { top_k: i }));
			}
			await Promise.all(promises);

			expect(mockStore.set).toHaveBeenCalledTimes(20);
		});

		it("should handle get after destroy gracefully", async () => {
			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));
			await configStore.initConfigStore();
			await configStore.destroyConfigStore();

			// Should return undefined, not throw
			const result = await configStore.configStoreGet("connection");
			expect(result).toBeUndefined();
		});

		it("should not double-init if already initialized", async () => {
			const { load } = await import("@tauri-apps/plugin-store");
			mockStore.entries.mockResolvedValue(Object.entries(USER_CONFIG_DEFAULTS));

			await configStore.initConfigStore();
			await configStore.initConfigStore();

			// load called once only (second init is a no-op)
			expect(load).toHaveBeenCalledTimes(1);
		});
	});
});
