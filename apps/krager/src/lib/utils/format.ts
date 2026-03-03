/**
 * Formatting Utilities
 *
 * Pure functions for formatting durations, timestamps, file sizes, and uptime.
 */

/**
 * Format milliseconds into a human-readable duration string.
 *
 * Examples: "0ms", "150ms", "2.5s", "1m 30s", "2h 15m"
 */
export function formatDuration(ms: number): string {
	if (!Number.isFinite(ms) || ms < 0) return "0ms";
	if (ms < 1000) return `${Math.round(ms)}ms`;

	const seconds = ms / 1000;
	if (seconds < 60) return `${seconds.toFixed(1)}s`;

	const minutes = Math.floor(seconds / 60);
	const remainingSeconds = Math.round(seconds % 60);

	if (minutes < 60) {
		return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
	}

	const hours = Math.floor(minutes / 60);
	const remainingMinutes = minutes % 60;
	return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

/**
 * Format a Date into a locale-aware timestamp string.
 *
 * Example: "14:30:05" or "2:30:05 PM"
 */
export function formatTimestamp(d: Date | null | undefined): string {
	if (!d || !(d instanceof Date) || Number.isNaN(d.getTime())) return "—";
	return d.toLocaleTimeString();
}

/**
 * Format bytes into a human-readable file size.
 *
 * Examples: "0 B", "1.5 KB", "2.3 MB", "1.1 GB"
 */
export function formatFileSize(bytes: number): string {
	if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
	if (bytes === 0) return "0 B";

	const units = ["B", "KB", "MB", "GB", "TB"];
	const k = 1024;
	const i = Math.min(Math.max(Math.floor(Math.log(bytes) / Math.log(k)), 0), units.length - 1);
	const value = bytes / k ** i;

	return i === 0 ? `${bytes} B` : `${value.toFixed(1)} ${units[i]}`;
}

/**
 * Format seconds into a human-readable uptime string.
 *
 * Examples: "0s", "45s", "5m 30s", "2h 15m", "3d 12h"
 */
export function formatUptime(seconds: number): string {
	if (!Number.isFinite(seconds) || seconds < 0) return "0s";
	if (seconds < 60) return `${Math.round(seconds)}s`;

	const minutes = Math.floor(seconds / 60);
	const remainingSeconds = Math.round(seconds % 60);

	if (minutes < 60) {
		return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
	}

	const hours = Math.floor(minutes / 60);
	const remainingMinutes = minutes % 60;

	if (hours < 24) {
		return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
	}

	const days = Math.floor(hours / 24);
	const remainingHours = hours % 24;
	return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`;
}
