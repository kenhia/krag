/**
 * Connection State Module
 *
 * Reactive connection state using Svelte 5 $state rune.
 * Manages kragd server connection: host, port, status, health check data.
 * Loads/saves host+port from config store for persistence across restarts.
 */

import { configStoreGet, configStoreSet, isConfigStoreReady } from "$lib/services/config-store";
import type { ConnectionConfig, ConnectionStatus } from "$lib/types";

export interface ConnectionState {
	host: string;
	port: number;
	status: ConnectionStatus;
	lastCheck: Date | null;
	errorMsg: string | null;
	version: string | null;
}

/** Reactive connection state. */
export const connection = $state<ConnectionState>({
	host: "localhost",
	port: 8742,
	status: "disconnected",
	lastCheck: null,
	errorMsg: null,
	version: null,
});

/** Derive HTTP base URL from host and port. */
export function getConnectionBaseUrl(): string {
	return `http://${connection.host}:${connection.port}`;
}

/** Update connection target. Resets status to disconnected. */
export function setConnectionTarget(host: string, port: number): void {
	connection.host = host;
	connection.port = port;
	connection.status = "disconnected";
	connection.lastCheck = null;
	connection.errorMsg = null;
	connection.version = null;
}

/** Mark connection as connected with version info. */
export function setConnected(version: string): void {
	connection.status = "connected";
	connection.lastCheck = new Date();
	connection.errorMsg = null;
	connection.version = version;
}

/** Mark connection as disconnected. */
export function setDisconnected(): void {
	connection.status = "disconnected";
	connection.lastCheck = new Date();
	connection.errorMsg = null;
}

/** Mark connection as errored. */
export function setConnectionError(msg: string): void {
	connection.status = "error";
	connection.lastCheck = new Date();
	connection.errorMsg = msg;
}

/** Load initial host/port from config store. */
export async function initConnectionFromConfig(): Promise<void> {
	if (!isConfigStoreReady()) return;
	const saved = await configStoreGet<ConnectionConfig>("connection");
	if (saved?.host && saved?.port) {
		connection.host = saved.host;
		connection.port = saved.port;
	}
}

/** Save current host/port to config store. */
export async function saveConnectionToConfig(): Promise<void> {
	if (!isConfigStoreReady()) return;
	await configStoreSet("connection", {
		host: connection.host,
		port: connection.port,
	});
}
