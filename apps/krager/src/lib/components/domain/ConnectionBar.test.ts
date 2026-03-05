import { render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { connection, setConnectionTarget } from "$lib/state/connection.svelte";
import ConnectionBar from "./ConnectionBar.svelte";

// Mock the kragd-client to prevent actual HTTP calls
vi.mock("$lib/services/kragd-client", () => ({
	getHealth: vi.fn(),
	setBaseUrl: vi.fn(),
	getModes: vi.fn(() => Promise.resolve({ modes: [] })),
}));

// Mock config store
vi.mock("$lib/services/config-store", () => ({
	configStoreGet: vi.fn(),
	configStoreSet: vi.fn(),
	isConfigStoreReady: vi.fn(() => true),
}));

describe("ConnectionBar", () => {
	beforeEach(() => {
		setConnectionTarget("localhost", 8742);
	});

	it("renders host and port inputs pre-filled from connection state", () => {
		render(ConnectionBar);

		const hostInput = screen.getByPlaceholderText("hostname");
		const portInput = screen.getByPlaceholderText("port");

		expect(hostInput).toHaveValue("localhost");
		expect(portInput).toHaveValue("8742");
	});

	it("renders pre-filled values when connection state has custom host/port", () => {
		setConnectionTarget("karch9", 9999);
		render(ConnectionBar);

		const hostInput = screen.getByPlaceholderText("hostname");
		const portInput = screen.getByPlaceholderText("port");

		expect(hostInput).toHaveValue("karch9");
		expect(portInput).toHaveValue("9999");
	});

	it("renders connect button", () => {
		render(ConnectionBar);
		expect(screen.getByText("Connect")).toBeInTheDocument();
	});

	it("shows disconnect button when connected", () => {
		connection.status = "connected";
		connection.version = "1.0.0";
		render(ConnectionBar);
		expect(screen.getByText("Disconnect")).toBeInTheDocument();
	});
});
