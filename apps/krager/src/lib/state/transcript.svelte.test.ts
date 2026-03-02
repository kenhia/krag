import { describe, it, expect, beforeEach } from "vitest";
import {
	transcript,
	addEntry,
	updateEntry,
	clearTranscript,
} from "./transcript.svelte";
import type { TranscriptEntry } from "$lib/types";

function makeEntry(overrides: Partial<TranscriptEntry> = {}): TranscriptEntry {
	return {
		id: `entry-${Math.random().toString(36).slice(2)}`,
		timestamp: new Date(),
		type: "query",
		request: { query: "test" },
		response: null,
		durationMs: null,
		error: null,
		loading: true,
		...overrides,
	};
}

describe("transcript.svelte", () => {
	beforeEach(() => {
		clearTranscript();
		transcript.maxEntries = 500;
	});

	it("starts with empty entries", () => {
		expect(transcript.entries).toHaveLength(0);
	});

	it("has default maxEntries of 500", () => {
		expect(transcript.maxEntries).toBe(500);
	});

	describe("addEntry", () => {
		it("appends an entry", () => {
			const entry = makeEntry({ id: "e1" });
			addEntry(entry);
			expect(transcript.entries).toHaveLength(1);
			expect(transcript.entries[0].id).toBe("e1");
		});

		it("preserves order of entries", () => {
			addEntry(makeEntry({ id: "e1" }));
			addEntry(makeEntry({ id: "e2" }));
			addEntry(makeEntry({ id: "e3" }));
			expect(transcript.entries.map((e) => e.id)).toEqual(["e1", "e2", "e3"]);
		});

		it("trims oldest entries when exceeding maxEntries", () => {
			transcript.maxEntries = 3;
			addEntry(makeEntry({ id: "e1" }));
			addEntry(makeEntry({ id: "e2" }));
			addEntry(makeEntry({ id: "e3" }));
			addEntry(makeEntry({ id: "e4" }));
			expect(transcript.entries).toHaveLength(3);
			expect(transcript.entries[0].id).toBe("e2");
			expect(transcript.entries[2].id).toBe("e4");
		});

		it("handles maxEntries of 1", () => {
			transcript.maxEntries = 1;
			addEntry(makeEntry({ id: "e1" }));
			addEntry(makeEntry({ id: "e2" }));
			expect(transcript.entries).toHaveLength(1);
			expect(transcript.entries[0].id).toBe("e2");
		});
	});

	describe("updateEntry", () => {
		it("updates an existing entry by ID", () => {
			addEntry(makeEntry({ id: "e1", loading: true }));
			updateEntry("e1", { loading: false, response: { answer: "done" }, durationMs: 150 });
			expect(transcript.entries[0].loading).toBe(false);
			expect(transcript.entries[0].response).toEqual({ answer: "done" });
			expect(transcript.entries[0].durationMs).toBe(150);
		});

		it("does nothing if ID not found", () => {
			addEntry(makeEntry({ id: "e1" }));
			updateEntry("nonexistent", { loading: false });
			expect(transcript.entries[0].loading).toBe(true);
		});

		it("can set error on entry", () => {
			addEntry(makeEntry({ id: "e1" }));
			updateEntry("e1", { error: "Timeout", loading: false });
			expect(transcript.entries[0].error).toBe("Timeout");
			expect(transcript.entries[0].loading).toBe(false);
		});
	});

	describe("clearTranscript", () => {
		it("removes all entries", () => {
			addEntry(makeEntry());
			addEntry(makeEntry());
			clearTranscript();
			expect(transcript.entries).toHaveLength(0);
		});
	});
});
