/**
 * Notifications State Module
 *
 * Reactive toast notification state using Svelte 5 $state rune.
 */

import type { ToastEntry } from "$lib/types";

let nextId = 0;

/** Reactive notifications state. */
export const notifications = $state<{ toasts: ToastEntry[] }>({
	toasts: [],
});

/**
 * Add a toast notification.
 * Returns the toast ID for manual dismissal.
 */
export function addToast(message: string, type: ToastEntry["type"], duration = 5000): string {
	const id = `toast-${++nextId}`;
	notifications.toasts.push({ id, message, type, duration });
	return id;
}

/**
 * Dismiss a toast by ID.
 */
export function dismissToast(id: string): void {
	const idx = notifications.toasts.findIndex((t) => t.id === id);
	if (idx !== -1) {
		notifications.toasts.splice(idx, 1);
	}
}

/**
 * Clear all toasts.
 */
export function clearToasts(): void {
	notifications.toasts.length = 0;
}
