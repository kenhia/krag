/**
 * Index Job State Module
 *
 * Reactive index job state using Svelte 5 $state rune.
 * Tracks the state of in-progress or completed indexing operations.
 */

import type { IndexStatus, IndexMode, IndexingFileError, IndexResponse } from "$lib/types";

export interface IndexJobState {
	running: boolean;
	jobId: string | null;
	status: IndexStatus | null;
	mode: IndexMode | null;
	filesScanned: number;
	filesProcessed: number;
	filesSkippedUnchanged: number;
	filesSkippedOther: number;
	filesErrored: number;
	chunksCreated: number;
	vectorsStored: number;
	durationSeconds: number | null;
	errors: IndexingFileError[];
	lastUpdated: Date | null;
	error: string | null;
}

/** Reactive index job state. */
export const indexJob = $state<IndexJobState>({
	running: false,
	jobId: null,
	status: null,
	mode: null,
	filesScanned: 0,
	filesProcessed: 0,
	filesSkippedUnchanged: 0,
	filesSkippedOther: 0,
	filesErrored: 0,
	chunksCreated: 0,
	vectorsStored: 0,
	durationSeconds: null,
	errors: [],
	lastUpdated: null,
	error: null,
});

/** Reset job to idle state. */
export function resetJob(): void {
	indexJob.running = false;
	indexJob.jobId = null;
	indexJob.status = null;
	indexJob.mode = null;
	indexJob.filesScanned = 0;
	indexJob.filesProcessed = 0;
	indexJob.filesSkippedUnchanged = 0;
	indexJob.filesSkippedOther = 0;
	indexJob.filesErrored = 0;
	indexJob.chunksCreated = 0;
	indexJob.vectorsStored = 0;
	indexJob.durationSeconds = null;
	indexJob.errors.length = 0;
	indexJob.lastUpdated = null;
	indexJob.error = null;
}

/**
 * Apply an IndexResponse to the job state.
 * Maps API fields including filesSkippedUnchanged and filesSkippedOther.
 */
export function applyStatus(r: IndexResponse): void {
	indexJob.jobId = r.job_id;
	indexJob.status = r.status;
	indexJob.mode = r.mode;
	indexJob.filesScanned = r.files_scanned;
	indexJob.filesProcessed = r.files_processed;
	indexJob.filesSkippedUnchanged = r.files_skipped_unchanged;
	indexJob.filesSkippedOther = r.files_skipped_other;
	indexJob.filesErrored = r.files_errored;
	indexJob.chunksCreated = r.chunks_created;
	indexJob.vectorsStored = r.vectors_stored;
	indexJob.durationSeconds = r.duration_seconds;
	indexJob.errors.length = 0;
	indexJob.errors.push(...r.errors);
	indexJob.lastUpdated = new Date();

	// Stop running if status is terminal
	if (r.status === "completed" || r.status === "failed") {
		indexJob.running = false;
	}
}
