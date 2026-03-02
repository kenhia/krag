import { describe, it, expect, beforeEach } from "vitest";
import {
	connection,
	getConnectionBaseUrl,
	setConnectionTarget,
	setConnected,
	setDisconnected,
	setConnectionError,
} from "./connection.svelte";

describe("connection.svelte", () => {
	beforeEach(() => {
		setConnectionTarget("localhost", 11435);
	});

	it("has correct default values", () => {
		expect(connection.host).toBe("localhost");
		expect(connection.port).toBe(11435);
		expect(connection.status).toBe("disconnected");
		expect(connection.lastCheck).toBeNull();
		expect(connection.errorMsg).toBeNull();
		expect(connection.version).toBeNull();
	});

	describe("getConnectionBaseUrl", () => {
		it("derives base URL from host and port", () => {
			expect(getConnectionBaseUrl()).toBe("http://localhost:11435");
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
});
