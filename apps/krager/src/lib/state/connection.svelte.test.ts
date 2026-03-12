import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	connection,
	getConnectionBaseUrl,
	initConnectionFromConfig,
	saveConnectionToConfig,
	setConnected,
	setConnectionError,
	setConnectionTarget,
	setDisconnected,
} from "./connection.svelte";

// Mock config store
vi.mock("$lib/services/config-store", () => ({
	configStoreGet: vi.fn(),
	configStoreSet: vi.fn(),
	isConfigStoreReady: vi.fn(() => true),
}));

import { configStoreGet, configStoreSet } from "$lib/services/config-store";

describe("connection.svelte", () => {
	beforeEach(() => {
		setConnectionTarget("localhost", 8742);
	});

	it("has correct default values", () => {
		expect(connection.host).toBe("localhost");
		expect(connection.port).toBe(8742);
		expect(connection.status).toBe("disconnected");
		expect(connection.lastCheck).toBeNull();
		expect(connection.errorMsg).toBeNull();
		expect(connection.version).toBeNull();
	});

	describe("getConnectionBaseUrl", () => {
		it("derives base URL from host and port", () => {
			expect(getConnectionBaseUrl()).toBe("http://localhost:8742");
		});

		it("updates when host/port change", () => {
			setConnectionTarget("myhost", 9999);
			expect(getConnectionBaseUrl()).toBe("http://myhost:9999");
		});
	});

	describe("setConnectionTarget", () => {
		it("updates host and port", () => {
			setConnectionTarget("192.168.1.100", 8080);
			expect(connection.host).toBe("192.168.1.100");
			expect(connection.port).toBe(8080);
		});

		it("resets status to disconnected", () => {
			setConnected("1.0.0");
			expect(connection.status).toBe("connected");
			setConnectionTarget("newhost", 1234);
			expect(connection.status).toBe("disconnected");
			expect(connection.version).toBeNull();
			expect(connection.errorMsg).toBeNull();
		});
	});

	describe("status transitions", () => {
		it("disconnected → connected", () => {
			expect(connection.status).toBe("disconnected");
			setConnected("2.0.0");
			expect(connection.status).toBe("connected");
			expect(connection.version).toBe("2.0.0");
			expect(connection.lastCheck).toBeInstanceOf(Date);
			expect(connection.errorMsg).toBeNull();
		});

		it("connected → disconnected", () => {
			setConnected("1.0.0");
			setDisconnected();
			expect(connection.status).toBe("disconnected");
			expect(connection.lastCheck).toBeInstanceOf(Date);
		});

		it("connected → error", () => {
			setConnected("1.0.0");
			setConnectionError("Connection refused");
			expect(connection.status).toBe("error");
			expect(connection.errorMsg).toBe("Connection refused");
			expect(connection.lastCheck).toBeInstanceOf(Date);
		});

		it("error → connected on successful health check", () => {
			setConnectionError("timeout");
			expect(connection.status).toBe("error");
			setConnected("1.0.0");
			expect(connection.status).toBe("connected");
			expect(connection.errorMsg).toBeNull();
		});
	});

	describe("config persistence", () => {
		beforeEach(() => {
			vi.clearAllMocks();
		});

		it("initConnectionFromConfig loads saved host/port", async () => {
			(configStoreGet as ReturnType<typeof vi.fn>).mockResolvedValue({
				host: "karch9",
				port: 9999,
			});

			await initConnectionFromConfig();

			expect(connection.host).toBe("karch9");
			expect(connection.port).toBe(9999);
			expect(configStoreGet).toHaveBeenCalledWith("connection");
		});

		it("initConnectionFromConfig falls back to defaults when no config", async () => {
			(configStoreGet as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

			setConnectionTarget("localhost", 8742);
			await initConnectionFromConfig();

			expect(connection.host).toBe("localhost");
			expect(connection.port).toBe(8742);
		});

		it("saveConnectionToConfig saves host/port on successful connect", async () => {
			setConnectionTarget("myhost", 5555);
			await saveConnectionToConfig();

			expect(configStoreSet).toHaveBeenCalledWith("connection", {
				host: "myhost",
				port: 5555,
			});
		});
	});
});
