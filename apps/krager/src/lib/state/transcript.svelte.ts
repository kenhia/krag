/**
 * Transcript State Module
 *
 * Reactive transcript state using Svelte 5 $state rune.
 * Append-only log of user interactions. Trims at maxEntries.
 */

import type { TranscriptEntry } from "$lib/types";

export interface TranscriptState {
	entries: TranscriptEntry[];
	maxEntries: number;
}

/** Reactive transcript state. */
export const transcript = $state<TranscriptState>({
	entries: [],
	maxEntries: 500,
});

/** Per-entry chunks-expanded toggle state. */
const expandedChunks = $state<Record<string, boolean>>({});

/**
 * Add a transcript entry. Trims oldest entries if over maxEntries.
 */
export function addEntry(entry: TranscriptEntry): void {
	transcript.entries.push(entry);
	while (transcript.entries.length > transcript.maxEntries) {
		transcript.entries.shift();
	}
}

/**
 * Update an existing transcript entry by ID.
 * Applies a partial patch to the matching entry.
 */
export function updateEntry(id: string, patch: Partial<TranscriptEntry>): void {
	const entry = transcript.entries.find((e) => e.id === id);
	if (entry) {
		Object.assign(entry, patch);
	}
}

/**
 * Clear all transcript entries.
 */
export function clearTranscript(): void {
	transcript.entries.length = 0;
	// Reset expanded state
	for (const key of Object.keys(expandedChunks)) {
		delete expandedChunks[key];
	}
}

/**
 * Check if chunks are expanded for a given entry.
 */
export function isChunksExpanded(entryId: string): boolean {
	return expandedChunks[entryId] ?? false;
}

/**
 * Toggle chunks expanded state for a given entry.
 */
export function toggleChunksExpanded(entryId: string): void {
	expandedChunks[entryId] = !isChunksExpanded(entryId);
}
