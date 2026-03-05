import { beforeEach, describe, expect, it } from "vitest";
import type { IndexResponse } from "$lib/types";
import { applyStatus, indexJob, resetJob } from "./indexJob.svelte";

function makeIndexResponse(overrides: Partial<IndexResponse> = {}): IndexResponse {
	return {
		job_id: "job-001",
		status: "running",
		mode: "incremental",
		files_scanned: 100,
		files_processed: 80,
		files_skipped: 15,
		files_skipped_unchanged: 10,
		files_skipped_other: 5,
		files_errored: 5,
		chunks_created: 200,
		vectors_stored: 200,
		duration_seconds: 12.5,
		dry_run: false,
		errors: [],
		collections: { main: 200 },
		...overrides,
	};
}

describe("indexJob.svelte", () => {
	beforeEach(() => {
		resetJob();
	});

	it("starts in idle state", () => {
		expect(indexJob.running).toBe(false);
		expect(indexJob.jobId).toBeNull();
		expect(indexJob.status).toBeNull();
		expect(indexJob.mode).toBeNull();
		expect(indexJob.filesScanned).toBe(0);
		expect(indexJob.filesProcessed).toBe(0);
		expect(indexJob.filesSkippedUnchanged).toBe(0);
		expect(indexJob.filesSkippedOther).toBe(0);
		expect(indexJob.filesErrored).toBe(0);
		expect(indexJob.chunksCreated).toBe(0);
		expect(indexJob.vectorsStored).toBe(0);
		expect(indexJob.durationSeconds).toBeNull();
		expect(indexJob.errors).toHaveLength(0);
		expect(indexJob.lastUpdated).toBeNull();
		expect(indexJob.error).toBeNull();
	});

	describe("applyStatus", () => {
		it("maps all fields from IndexResponse", () => {
			const response = makeIndexResponse();
			applyStatus(response);

			expect(indexJob.jobId).toBe("job-001");
			expect(indexJob.status).toBe("running");
			expect(indexJob.mode).toBe("incremental");
			expect(indexJob.filesScanned).toBe(100);
			expect(indexJob.filesProcessed).toBe(80);
			expect(indexJob.filesErrored).toBe(5);
			expect(indexJob.chunksCreated).toBe(200);
			expect(indexJob.vectorsStored).toBe(200);
			expect(indexJob.durationSeconds).toBe(12.5);
			expect(indexJob.lastUpdated).toBeInstanceOf(Date);
		});

		it("maps filesSkippedUnchanged from API response", () => {
			applyStatus(makeIndexResponse({ files_skipped_unchanged: 42 }));
			expect(indexJob.filesSkippedUnchanged).toBe(42);
		});

		it("maps filesSkippedOther from API response", () => {
			applyStatus(makeIndexResponse({ files_skipped_other: 7 }));
			expect(indexJob.filesSkippedOther).toBe(7);
		});

		it("sets running=false when status is completed", () => {
			indexJob.running = true;
			applyStatus(makeIndexResponse({ status: "completed" }));
			expect(indexJob.running).toBe(false);
		});

		it("sets running=false when status is failed", () => {
			indexJob.running = true;
			applyStatus(makeIndexResponse({ status: "failed" }));
			expect(indexJob.running).toBe(false);
		});

		it("keeps running=true when status is running", () => {
			indexJob.running = true;
			applyStatus(makeIndexResponse({ status: "running" }));
			expect(indexJob.running).toBe(true);
		});

		it("maps errors array from response", () => {
			const errors = [
				{ file_path: "/a.py", error_type: "parse", error_message: "syntax error" },
				{ file_path: "/b.py", error_type: "io", error_message: "permission denied" },
			];
			applyStatus(makeIndexResponse({ errors }));
			expect(indexJob.errors).toHaveLength(2);
			expect(indexJob.errors[0].file_path).toBe("/a.py");
			expect(indexJob.errors[1].error_message).toBe("permission denied");
		});

		it("replaces previous errors on new status", () => {
			applyStatus(
				makeIndexResponse({
					errors: [{ file_path: "/a.py", error_type: "e", error_message: "m" }],
				}),
			);
			expect(indexJob.errors).toHaveLength(1);
			applyStatus(makeIndexResponse({ errors: [] }));
			expect(indexJob.errors).toHaveLength(0);
		});
	});

	describe("resetJob", () => {
		it("resets all fields to defaults", () => {
			applyStatus(makeIndexResponse());
			indexJob.running = true;
			indexJob.error = "some error";
			resetJob();

			expect(indexJob.running).toBe(false);
			expect(indexJob.jobId).toBeNull();
			expect(indexJob.status).toBeNull();
			expect(indexJob.filesScanned).toBe(0);
			expect(indexJob.filesProcessed).toBe(0);
			expect(indexJob.filesSkippedUnchanged).toBe(0);
			expect(indexJob.filesSkippedOther).toBe(0);
			expect(indexJob.errors).toHaveLength(0);
			expect(indexJob.error).toBeNull();
		});
	});
});
