/**
 * Error Handling Utilities
 *
 * Centralised error dispatch: inspects KragdError.status and
 * shows appropriate toast notifications with user-friendly copy.
 */

import { KragdError } from "$lib/types";
import { addToast } from "$lib/state/notifications.svelte";

/**
 * Handle a kragd API error by showing an appropriate toast notification.
 *
 * Inspects the error type and status code to produce human-readable messages.
 * Returns the error message string for callers that need it.
 */
export function handleKragdError(err: unknown): string {
	if (err instanceof KragdError) {
		const msg = kragdErrorMessage(err);
		addToast(msg, kragdErrorToastType(err.status));
		return msg;
	}

	if (err instanceof Error) {
		addToast(err.message, "error");
		return err.message;
	}

	const fallback = "An unexpected error occurred";
	addToast(fallback, "error");
	return fallback;
}

/**
 * Produce a user-friendly message from a KragdError based on status code.
 */
function kragdErrorMessage(err: KragdError): string {
	switch (err.status) {
		case 0:
			return "Cannot reach kragd — check that the server is running";
		case 422:
			return `Invalid request: ${err.message}`;
		case 409:
			return `Conflict: ${err.message}`;
		case 503:
			return "kragd is not ready — a model may still be loading";
		case 500:
			return "Internal server error — check kragd logs";
		default:
			return err.message || `HTTP error ${err.status}`;
	}
}

/**
 * Map HTTP status to toast severity.
 */
function kragdErrorToastType(status: number): "error" | "warning" {
	// Network unreachable and 503 are "warning" — may recover on retry
	if (status === 0 || status === 503) return "warning";
	return "error";
}

/**
 * Guard that connection is active before making a network call.
 * Returns true if connected, false (with toast) otherwise.
 */
export function requireConnection(status: string): boolean {
	if (status === "connected") return true;
	addToast("Not connected to kragd", "warning");
	return false;
}
